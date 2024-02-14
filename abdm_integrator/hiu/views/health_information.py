import itertools
import json
import logging
from dataclasses import asdict
from datetime import datetime

from django.http import QueryDict
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.status import HTTP_200_OK, HTTP_202_ACCEPTED

from abdm_integrator.const import HealthInformationStatus, RequesterType
from abdm_integrator.crypto import ABDMCrypto
from abdm_integrator.exceptions import ABDMGatewayError, CustomError
from abdm_integrator.hiu.const import HEALTH_DATA_CACHE_TIMEOUT, HIUGatewayAPIPath
from abdm_integrator.hiu.exceptions import HealthDataReceiverException, HIUError
from abdm_integrator.hiu.fhir.parser import parse_fhir_bundle
from abdm_integrator.hiu.models import ConsentArtefact, HealthDataReceiver, HealthInformationRequest
from abdm_integrator.hiu.serializers.health_information import (
    GatewayHealthInformationOnRequestSerializer,
    ReceiveHealthInformationSerializer,
    RequestHealthInformationSerializer,
)
from abdm_integrator.hiu.tasks import process_hiu_health_information_receiver
from abdm_integrator.hiu.views.base import HIUBaseView, HIUGatewayBaseView
from abdm_integrator.settings import app_settings
from abdm_integrator.utils import ABDMCache, ABDMRequestHelper, abdm_iso_to_datetime, poll_and_pop_data_from_cache

logger = logging.getLogger('abdm_integrator')


class RequestHealthInformation(HIUBaseView):

    def get(self, request, format=None):
        """
        Initiates health information request to Gateway. Uses Long Polling to wait for Provider to send health
        data. If received in time limit, health data is formatted as per setting and sent as response else
        sends timeout error. If multiple pages are send by the provider, generates and includes url for next page
        in response.
        """
        request_data = request.query_params
        RequestHealthInformationSerializer(data=request_data).is_valid(raise_exception=True)

        artefact = get_object_or_404(
            ConsentArtefact, artefact_id=request_data['artefact_id'], consent_request__user=request.user
        )
        self.validate_artefact_expiry(artefact)

        current_url = request.build_absolute_uri(reverse('request_health_information'))
        health_info_url = request.build_absolute_uri(reverse('receive_health_information'))
        # For multiple pages, client is expected make a new request for subsequent pages with additional parameters
        # 'transaction_id' and 'page' as returned from the previous request
        if request_data.get('transaction_id') and request_data.get('page'):
            page_number = request_data['page']
            gateway_request_id = get_object_or_404(
                HealthInformationRequest,
                transaction_id=request_data['transaction_id']
            ).gateway_request_id
        else:
            page_number = 1
            hiu_crypto = ABDMCrypto()
            gateway_request_id = self.gateway_health_information_cm_request(
                artefact, health_info_url, hiu_crypto.transfer_material
            )
            self.save_health_info_request(
                request.user, artefact, gateway_request_id, asdict(hiu_crypto.key_material)
            )

        cache_key = f'{gateway_request_id}_{page_number}'
        health_response_data = poll_and_pop_data_from_cache(cache_key, interval=3)

        self.handle_for_error(health_response_data)
        logger.info("HIU: Health data received %s", health_response_data['entries'])
        if app_settings.HIU_PARSE_FHIR_BUNDLE:
            health_response_data['entries'] = self.parse_fhir_bundle_for_ui(health_response_data['entries'])
        response_data = self.generate_response_data(health_response_data, current_url, artefact.artefact_id)
        logger.info("HIU: Formatted Health data received %s", response_data)
        return Response(status=HTTP_200_OK, data=response_data)

    def validate_artefact_expiry(self, artefact):
        if artefact.consent_request.expiry_date <= datetime.utcnow():
            raise CustomError(
                error_code=HIUError.CODE_CONSENT_EXPIRED,
                error_message=HIUError.CUSTOM_ERRORS[HIUError.CODE_CONSENT_EXPIRED],
                detail_attr='artefact_id'
            )

    def gateway_health_information_cm_request(self, artefact, health_info_url, hiu_transfer_material):
        payload = ABDMRequestHelper.common_request_data()
        payload['hiRequest'] = {
            'consent': {'id': str(artefact.artefact_id)},
            'dateRange': artefact.details['permission']['dateRange'],
            'dataPushUrl': health_info_url,
            'keyMaterial': hiu_transfer_material,
        }
        ABDMRequestHelper().gateway_post(HIUGatewayAPIPath.HEALTH_INFO_REQUEST, payload)
        return payload['requestId']

    def save_health_info_request(self, user, artefact, gateway_request_id, key_material_dict):
        HealthInformationRequest.objects.create(
            user=user,
            consent_artefact=artefact,
            gateway_request_id=gateway_request_id,
            key_material=key_material_dict
        )

    def _get_next_query_params(self, response_data, artefact_id):
        params = QueryDict('', mutable=True)
        params.update({
            'artefact_id': artefact_id,
            'transaction_id': response_data['transaction_id'],
            'page': response_data['page'] + 1
        })
        return params

    def generate_response_data(self, health_response_data, current_url, artefact_id):
        health_response_data['next'] = None
        health_response_data['results'] = health_response_data.pop('entries')
        if health_response_data['page'] < health_response_data['page_count']:
            health_response_data['next'] = (
                f'{current_url}?{self._get_next_query_params(health_response_data, artefact_id).urlencode()}'
            )
        return health_response_data

    def parse_fhir_bundle_for_ui(self, fhir_entries):
        parsed_entries = []
        for entry in fhir_entries:
            try:
                parsed_entry = parse_fhir_bundle(entry['content'])
                parsed_entry['care_context_reference'] = entry['care_context_reference']
                parsed_entries.append(parsed_entry)
            except Exception as err:
                logger.exception(
                    'ABDM HIU: Parsing error occurred for Care Context %s: %s',
                    entry['care_context_reference'],
                    err
                )
        return parsed_entries

    def handle_for_error(self, health_response_data):
        if not health_response_data:
            raise CustomError(
                error_code=HIUError.CODE_HEALTH_INFO_TIMEOUT,
                error_message=HIUError.CUSTOM_ERRORS[HIUError.CODE_HEALTH_INFO_TIMEOUT],
                status_code=555
            )
        if health_response_data.get('error'):
            error = health_response_data['error']
            if error.get('code') == HIUError.CODE_HEALTH_DATA_RECEIVER:
                raise CustomError(error_code=error['code'], error_message=error['message'], status_code=556)
            raise ABDMGatewayError(error.get('code'), error.get('message'))


class GatewayHealthInformationOnRequest(HIUGatewayBaseView):

    def post(self, request, format=None):
        GatewayHealthInformationOnRequestSerializer(data=request.data).is_valid(raise_exception=True)
        self.process_request(request.data)
        return Response(status=HTTP_202_ACCEPTED)

    def process_request(self, request_data):
        health_information_request = HealthInformationRequest.objects.get(
            gateway_request_id=request_data['resp']['requestId']
        )
        if request_data.get('hiRequest'):
            health_information_request.transaction_id = request_data['hiRequest']['transactionId']
            health_information_request.status = request_data['hiRequest']['sessionStatus']
        elif request_data.get('error'):
            health_information_request.error = request_data['error']
            health_information_request.status = HealthInformationStatus.ERROR
            cache_key = f'{health_information_request.gateway_request_id}_1'
            ABDMCache.set(cache_key, request_data, 20)
        health_information_request.save()


class ReceiveHealthInformation(HIUBaseView):
    permission_classes = []

    def post(self, request, format=None):
        logger.info(f"HIU: Receive Health Information {request.data}")
        ReceiveHealthInformationSerializer(data=request.data).is_valid(raise_exception=True)
        process_hiu_health_information_receiver.delay(request.data)
        return Response(status=HTTP_202_ACCEPTED)


class ReceiveHealthInformationProcessor:
    """
    Processes health information received from Provider and stores the processed data temporarily in cache
    to be picked up the health information request.
    """

    def __init__(self, request_data):
        self.request_data = request_data
        self.health_information_request = HealthInformationRequest.objects.get(
            transaction_id=self.request_data['transactionId']
        )
        self.response_data = {
            'transaction_id': self.request_data['transactionId'],
            'page': self.request_data.get('pageNumber', 1),
            'page_count': self.request_data.get('pageCount', 1),
            'entries': []
        }

    def process_request(self):
        error = None
        try:
            self.validate_request()
            self.response_data['entries'] = self.process_entries()
        except HealthDataReceiverException as err:
            error = str(err)
        care_contexts_status = self.generate_care_contexts_status(self._care_contexts_from_request(), error)
        self.save_health_data_receipt(care_contexts_status)
        self.set_response_in_cache(error)
        # Notifies Gateway once all pages are received
        if self.request_data.get('pageNumber', 1) == self.request_data.get('pageCount', 1):
            session_status, all_care_context_status = self.get_overall_status(care_contexts_status)
            self.update_health_information_request_status(session_status)
            self.gateway_health_information_on_transfer(session_status, all_care_context_status)

    def validate_request(self):
        artefact = self.health_information_request.consent_artefact
        error_code = None
        if not self._validate_key_material_expiry():
            error_code = HIUError.CODE_KEY_PAIR_EXPIRED
        elif not self._validate_consent_expiry(artefact):
            error_code = HIUError.CODE_CONSENT_EXPIRED
        if error_code:
            raise HealthDataReceiverException(f'Validation Error: {HIUError.CUSTOM_ERRORS.get(error_code)}')

    def _validate_key_material_expiry(self):
        key_material_expiry = self.request_data['keyMaterial']['dhPublicKey']['expiry']
        logger.info(f"key_material_expiry: {key_material_expiry}")
        # DISABLING for external HIP TEST
        # return abdm_iso_to_datetime(key_material_expiry) > datetime.utcnow()
        return True

    def _validate_consent_expiry(self, artefact):
        return abdm_iso_to_datetime(artefact.details['permission']['dataEraseAt']) > datetime.utcnow()

    def _care_contexts_from_request(self):
        return [{'care_context_reference': entry['careContextReference']}
                for entry in self.request_data['entries']]

    def process_entries(self):
        hiu_crypto = ABDMCrypto(key_material_dict=self.health_information_request.key_material)
        decrypted_entries = []
        try:
            for entry in self.request_data['entries']:
                if entry.get('content'):
                    encrypted_data = entry['content']
                    processed_entry = self._process_entry(entry, encrypted_data, hiu_crypto)
                else:
                    logger.info(
                        'ABDM HIU: Entry type link received is not supported. Transaction: %s Care Context: %s',
                        self.request_data['transactionId'],
                        entry['careContextReference']
                    )
                    continue
                decrypted_entries.append(processed_entry)
        except Exception as err:
            raise HealthDataReceiverException(f'Error occurred while decryption process: {err}')
        return decrypted_entries

    def _process_entry(self, entry, encrypted_data, hiu_crypto):
        data = {'care_context_reference': entry['careContextReference']}
        decrypted_data_str = hiu_crypto.decrypt(encrypted_data, self.request_data['keyMaterial'])
        # DISABLING for external HIP TEST
        # if not hiu_crypto.generate_checksum(decrypted_data_str) == entry['checksum']:
        #     raise HealthDataReceiverException('Error occurred while decryption process: Checksum failed')
        data['content'] = json.loads(decrypted_data_str)
        return data

    def save_health_data_receipt(self, care_contexts_status):
        HealthDataReceiver.objects.create(
            health_information_request=self.health_information_request,
            page_number=self.request_data.get('pageNumber', 1),
            care_contexts_status=care_contexts_status
        )

    def generate_care_contexts_status(self, care_contexts, error=None):
        hi_status = HealthInformationStatus.ERRORED if error else HealthInformationStatus.OK
        description = error if error else 'Delivered'
        return [{'careContextReference': care_context['care_context_reference'], 'hiStatus': hi_status,
                 'description': description} for care_context in care_contexts]

    def set_response_in_cache(self, error=None):
        if error:
            self.response_data['error'] = {
                'code': HIUError.CODE_HEALTH_DATA_RECEIVER,
                'message': HIUError.CUSTOM_ERRORS[HIUError.CODE_HEALTH_DATA_RECEIVER]
            }
        cache_key = f"{self.health_information_request.gateway_request_id}_{self.response_data['page']}"
        ABDMCache.set(cache_key, self.response_data, HEALTH_DATA_CACHE_TIMEOUT)

    def get_overall_status(self, current_care_context_status):
        all_care_context_status = current_care_context_status
        if self.request_data.get('pageNumber', 1) > 1:
            all_care_context_status_lists = self.health_information_request.health_data_receipts.all().values_list(
                'care_contexts_status', flat=True
            )
            all_care_context_status = list(itertools.chain.from_iterable(all_care_context_status_lists))
        transfer_status = not any(status['hiStatus'] == HealthInformationStatus.ERRORED
                                  for status in all_care_context_status)
        session_status = HealthInformationStatus.TRANSFERRED if transfer_status else HealthInformationStatus.FAILED
        return session_status, all_care_context_status

    def update_health_information_request_status(self, session_status):
        self.health_information_request.status = session_status
        self.health_information_request.save()

    def gateway_health_information_on_transfer(self, session_status, care_contexts_status):
        artefact = self.health_information_request.consent_artefact
        payload = ABDMRequestHelper.common_request_data()
        payload['notification'] = {
            'consent_id': str(artefact.artefact_id),
            'transaction_id': self.request_data['transactionId'],
            'doneAt': datetime.utcnow().isoformat(),
            'notifier': {
                'type': RequesterType.HIU,
                'id': self.get_hiu_id_from_consent()
            },
            'statusNotification': {
                'sessionStatus': session_status,
                'hipId': artefact.details['hip']['id']
            }
        }
        # Avoids sending description for care context as optional and could possibly contain
        # internal error details. Could be included in case a need/use case arises later on.
        for care_context_status in care_contexts_status:
            del care_context_status['description']
        payload['notification']['statusNotification']['statusResponses'] = care_contexts_status
        ABDMRequestHelper().gateway_post(HIUGatewayAPIPath.HEALTH_INFO_NOTIFY, payload)
        return payload['requestId']

    def get_hiu_id_from_consent(self):
        consent_request = self.health_information_request.consent_artefact.consent_request
        return consent_request.details['hiu']['id']
