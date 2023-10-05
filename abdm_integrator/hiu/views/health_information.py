import json
from datetime import datetime

from django.core.cache import cache
from django.http import QueryDict
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.status import HTTP_200_OK, HTTP_202_ACCEPTED

from abdm_integrator.const import HealthInformationStatus, HealthInformationType
from abdm_integrator.crypto import ABDMCrypto
from abdm_integrator.exceptions import CustomError
from abdm_integrator.hiu.const import HIUGatewayAPIPath
from abdm_integrator.hiu.exceptions import HealthDataReceiverException, HIUError
from abdm_integrator.hiu.fhir_ui_parser import generate_display_fields_for_bundle
from abdm_integrator.hiu.models import ConsentArtefact, HealthDataReceipt, HealthInformationRequest
from abdm_integrator.hiu.serializers.health_information import (
    GatewayHealthInformationOnRequestSerializer,
    HIUReceiveHealthInformationSerializer,
    HIURequestHealthInformationSerializer,
)
from abdm_integrator.hiu.views.base import HIUBaseView, HIUGatewayBaseView
from abdm_integrator.utils import ABDMRequestHelper, abdm_iso_to_datetime, poll_for_data_in_cache

# TODO Refine the use of django cache
# TODO Handle for Links


class RequestHealthInformation(HIUBaseView):

    def get(self, request, format=None):
        print('HIU: RequestHealthInformation', request.query_params)
        request_data = request.query_params
        HIURequestHealthInformationSerializer(data=request_data).is_valid(raise_exception=True)
        artefact = get_object_or_404(ConsentArtefact, artefact_id=request_data['artefact_id'])
        self.validate_artefact_expiry(artefact)

        # TODO Refactor below
        current_url = request.build_absolute_uri(reverse('request_health_information'))
        # TODO Check if want to Add some dynamic value at end of url
        health_info_url = request.build_absolute_uri(reverse('receive_health_information'))

        # Logic for subsequent pages
        if request_data.get('transaction_id') and request_data.get('page'):
            health_information_request = get_object_or_404(HealthInformationRequest,
                                                           transaction_id=request_data['transaction_id'])
            page_number = request_data['page']
            gateway_request_id = health_information_request.gateway_request_id
        else:
            # Logic for first page
            crypto = ABDMCrypto(x509=True)
            gateway_request_id = self.gateway_health_information_cm_request(artefact, health_info_url,
                                                                            crypto.transfer_material)
            self.save_health_info_request(artefact, gateway_request_id, crypto.key_material.as_dict())
            page_number = 1

        cache_key = f'{gateway_request_id}_{page_number}'
        data = poll_for_data_in_cache(cache_key, interval=4)
        if not data:
            raise CustomError(error_code=HIUError.CODE_HEALTH_INFO_TIMEOUT,
                              error_message=HIUError.CUSTOM_ERRORS[HIUError.CODE_HEALTH_INFO_TIMEOUT],
                              status_code=555)
        return Response(status=HTTP_200_OK, data=self.format_response_data(data, current_url,
                                                                           artefact.artefact_id))

    def validate_artefact_expiry(self, artefact):
        if artefact.consent_request.expiry_date <= datetime.utcnow():
            raise CustomError(
                error_code=HIUError.CODE_CONSENT_EXPIRED,
                error_message=HIUError.CUSTOM_ERRORS[HIUError.CODE_CONSENT_EXPIRED],
            )

    def gateway_health_information_cm_request(self, artefact, health_info_url, hiu_transfer_material):
        payload = ABDMRequestHelper.common_request_data()
        payload['hiRequest'] = {'consent': {'id': str(artefact.artefact_id)}}
        payload['hiRequest']['dateRange'] = artefact.details['permission']['dateRange']
        payload['hiRequest']['dataPushUrl'] = health_info_url
        payload['hiRequest']['keyMaterial'] = hiu_transfer_material
        ABDMRequestHelper().gateway_post(HIUGatewayAPIPath.HEALTH_INFO_REQUEST, payload)
        return payload['requestId']

    def save_health_info_request(self, artefact, gateway_request_id, key_material_dict):
        HealthInformationRequest.objects.create(consent_artefact=artefact,
                                                gateway_request_id=gateway_request_id,
                                                key_material=key_material_dict)

    def _get_next_query_params(self, response_data, artefact_id):
        params = QueryDict('', mutable=True)
        params['artefact_id'] = artefact_id
        params['transaction_id'] = response_data['transactionId']
        params['page'] = response_data['pageNumber'] + 1
        return params

    def format_response_data(self, response_data, current_url, artefact_id):
        # TODO Handle for parsing exception
        # TODO Specs in case of sending directly FHIR data
        # TODO Add a setting for this at the django app level with default to False
        entries = self.parse_fhir_bundle_for_ui(response_data['entries'])
        data = {
            'transaction_id': response_data['transactionId'],
            'page': response_data['pageNumber'],
            'page_count': response_data['pageCount'],
            'next': None,
            'results': entries
        }
        if response_data['pageNumber'] < response_data['pageCount']:
            data['next'] = f'{current_url}?{self._get_next_query_params(response_data, artefact_id).urlencode()}'
        return data

    def parse_fhir_bundle_for_ui(self, entries):
        parsed_entries = []
        for entry in entries:
            try:
                parsed_entry = generate_display_fields_for_bundle(entry['content'])
                parsed_entry['care_context_reference'] = entry['care_context_reference']
                parsed_entries.append(parsed_entry)
            except Exception as err:
                import traceback
                print(f'Parsing error occurred : {err}')
                print(traceback.format_exc())
        return parsed_entries


class GatewayHealthInformationOnRequest(HIUGatewayBaseView):

    def post(self, request, format=None):
        print('HIU: Callback: GatewayHealthInformationOnRequest', request.data)
        GatewayHealthInformationOnRequestSerializer(data=request.data).is_valid(raise_exception=True)
        self.process_request(request.data)
        return Response(status=HTTP_202_ACCEPTED)

    def process_request(self, request_data):
        health_information_request = HealthInformationRequest.objects.get(
            gateway_request_id=request_data['resp']['requestId'])
        if request_data.get('hiRequest'):
            health_information_request.transaction_id = request_data['hiRequest']['transactionId']
            health_information_request.status = request_data['hiRequest']['sessionStatus']
        elif request_data.get('error'):
            health_information_request.error = request_data['error']
            health_information_request.status = HealthInformationStatus.ERROR
        health_information_request.save()


class ReceiveHealthInformation(HIUBaseView):
    permission_classes = []

    def post(self, request, format=None):
        print(f"HIU: Receive Health Information {request.data['transactionId']} and page: {request.data['pageNumber']}")
        print(f"HIU: Receive Health Information {request.data.get('pageCount')} and page: {request.data.get('pageNumber')}")
        print(request.data.get('entries'))
        HIUReceiveHealthInformationSerializer(data=request.data).is_valid(raise_exception=True)
        ReceiveHealthInformationProcessor(request.data).process_request()
        return Response(status=HTTP_202_ACCEPTED)


class ReceiveHealthInformationProcessor:
    # TODO Decide if we need to run this in background

    def __init__(self, request_data):
        self.request_data = request_data

    def process_request(self):
        health_information_request = HealthInformationRequest.objects.get(
            transaction_id=self.request_data['transactionId'])
        error = self.validate_request(health_information_request.consent_artefact)
        print('ReceiveHealthInformationProcessor: Error is', error)
        if not error:  # If background raise Custom Error
            try:
                hiu_crypto = ABDMCrypto(key_material_json=health_information_request.key_material)
                decrypted_entries = self.process_entries(health_information_request, hiu_crypto)
                self.request_data['entries'] = decrypted_entries
            except Exception as err:
                error = err
        self.save_health_data_receipt(health_information_request, error)
        # TODO Handle for the error case
        cache_key = f"{health_information_request.gateway_request_id}_{self.request_data['pageNumber']}"
        cache.set(cache_key, self.request_data, 60)

    def validate_request(self, artefact):
        error_code = None
        if artefact is None:
            error_code = HIUError.CODE_ARTEFACT_NOT_FOUND
        elif not self._validate_key_material_expiry():
            error_code = HIUError.CODE_KEY_PAIR_EXPIRED
        elif not self._validate_consent_expiry(artefact):
            error_code = HIUError.CODE_CONSENT_EXPIRED
        return {'code': error_code, 'message': HIUError.CUSTOM_ERRORS.get(error_code)} if error_code else None

    def _validate_key_material_expiry(self):
        key_material_expiry = self.request_data['keyMaterial']['dhPublicKey']['expiry']
        return abdm_iso_to_datetime(key_material_expiry) > datetime.utcnow()

    def _validate_consent_expiry(self, artefact):
        return abdm_iso_to_datetime(artefact.details['permission']['dataEraseAt']) > datetime.utcnow()

    def process_entries(self, health_information_request, hiu_crypto):
        decrypted_entries = []
        try:
            for entry in self.request_data['entries']:
                data = {'care_context_reference': entry['careContextReference']}
                decrypted_data_str = hiu_crypto.decrypt(entry['content'],  self.request_data['keyMaterial'])
                if not hiu_crypto.generate_checksum(decrypted_data_str) == entry['checksum']:
                    raise HealthDataReceiverException('Error occurred while decryption process: Checksum failed')
                data['content'] = json.loads(decrypted_data_str)
                decrypted_entries.append(data)
        except Exception as err:
            raise HealthDataReceiverException(f'Error occurred while decryption process: {err}')
        return decrypted_entries

    def save_health_data_receipt(self, health_information_request, error=None):
        status = bool(error)
        care_contexts = [{'care_context_reference': entry['care_context_reference']}
                         for entry in self.request_data['entries']]
        HealthDataReceipt.objects.create(health_information_request=health_information_request,
                                         page_number=self.request_data['pageNumber'],
                                         care_contexts=care_contexts,
                                         status=status,
                                         error=error)

    # TODO Inform to gateway when transfer is complete
