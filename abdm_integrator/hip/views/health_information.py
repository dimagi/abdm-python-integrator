import json
import math
from datetime import datetime

import requests
from rest_framework.response import Response
from rest_framework.status import HTTP_202_ACCEPTED

from abdm_integrator.const import HEALTH_INFORMATION_MEDIA_TYPE, HealthInformationStatus, LinkRequestStatus
from abdm_integrator.crypto import ABDMCrypto
from abdm_integrator.exceptions import ABDMGatewayError, ABDMServiceUnavailable
from abdm_integrator.hip.const import HIPGatewayAPIPath
from abdm_integrator.hip.exceptions import HealthDataTransferException, HIPError
from abdm_integrator.hip.models import (
    ConsentArtefact,
    HealthDataTransfer,
    HealthInformationRequest,
    LinkCareContext,
)
from abdm_integrator.hip.serializers.care_contexts import LinkCareContextFetchSerializer
from abdm_integrator.hip.serializers.health_information import GatewayHealthInformationRequestSerializer
from abdm_integrator.hip.tasks import process_hip_health_information_request
from abdm_integrator.hip.views.base import HIPGatewayBaseView
from abdm_integrator.settings import app_settings
from abdm_integrator.utils import ABDMRequestHelper, abdm_iso_to_datetime


class GatewayHealthInformationRequest(HIPGatewayBaseView):

    def post(self, request, format=None):
        GatewayHealthInformationRequestSerializer(data=request.data).is_valid(raise_exception=True)
        process_hip_health_information_request.delay(request.data)
        return Response(status=HTTP_202_ACCEPTED)


class GatewayHealthInformationRequestProcessor:

    def __init__(self, request_data):
        self.request_data = request_data
        self.health_information_request = HealthInformationRequest.objects.create(
            transaction_id=self.request_data['transactionId'])

    def process_request(self):
        artefact = self.fetch_artefact()
        self.update_health_information_request_artefact(artefact)
        error = self.validate_request(artefact)
        try:
            self.gateway_health_information_on_request(error)
        except (ABDMServiceUnavailable, ABDMGatewayError) as err:
            error = err.error
        if error:
            self.update_health_information_request_error(error)
            return error
        overall_transfer_status, care_contexts_status = HealthDataTransferProcessor(
            self.health_information_request, self.request_data['hiRequest']).process()
        self.update_transfer_status(overall_transfer_status)
        self.gateway_health_information_on_transfer(overall_transfer_status, care_contexts_status)

    def fetch_artefact(self):
        artefact_id = self.request_data['hiRequest']['consent']['id']
        try:
            return ConsentArtefact.objects.get(artefact_id=artefact_id)
        except ConsentArtefact.DoesNotExist:
            return None

    def update_health_information_request_artefact(self, artefact):
        if artefact:
            self.health_information_request.consent_artefact = artefact
            self.health_information_request.save()

    def validate_request(self, artefact):
        error_code = None
        if artefact is None:
            error_code = HIPError.CODE_ARTEFACT_NOT_FOUND
        elif not self._validate_key_material_expiry():
            error_code = HIPError.CODE_KEY_PAIR_EXPIRED
        elif not self._validate_consent_expiry(artefact):
            error_code = HIPError.CODE_CONSENT_EXPIRED
        elif not self._validate_requested_date_range(artefact):
            error_code = HIPError.CODE_INVALID_DATE_RANGE
        return {'code': error_code, 'message': HIPError.CUSTOM_ERRORS.get(error_code)} if error_code else None

    def _validate_key_material_expiry(self):
        key_material_expiry = self.request_data['hiRequest']['keyMaterial']['dhPublicKey']['expiry']
        return abdm_iso_to_datetime(key_material_expiry) > datetime.utcnow()

    def _validate_consent_expiry(self, artefact):
        return abdm_iso_to_datetime(artefact.details['permission']['dataEraseAt']) > datetime.utcnow()

    def _validate_requested_date_range(self, artefact):
        artefact_from_date = abdm_iso_to_datetime(artefact.details['permission']['dateRange']['from'])
        artefact_to_date = abdm_iso_to_datetime(artefact.details['permission']['dateRange']['to'])
        requested_from_date = abdm_iso_to_datetime(self.request_data['hiRequest']['dateRange']['from'])
        if not (artefact_from_date <= requested_from_date <= artefact_to_date):
            return False
        requested_to_date = abdm_iso_to_datetime(self.request_data['hiRequest']['dateRange']['to'])
        if not (artefact_from_date <= requested_to_date <= artefact_to_date):
            return False
        return True

    def update_health_information_request_error(self, error):
        self.health_information_request.error = error
        self.health_information_request.status = HealthInformationStatus.ERROR
        self.health_information_request.save()

    def gateway_health_information_on_request(self, error=None):
        payload = ABDMRequestHelper.common_request_data()
        if error:
            payload['error'] = error
        else:
            payload['hiRequest'] = {'transactionId': self.request_data['transactionId'],
                                    'sessionStatus': HealthInformationStatus.ACKNOWLEDGED}
        payload['resp'] = {'requestId': self.request_data['requestId']}
        ABDMRequestHelper().gateway_post(HIPGatewayAPIPath.HEALTH_INFO_ON_REQUEST, payload)
        return payload['requestId']

    def update_transfer_status(self, overall_transfer_status):
        self.health_information_request.status = (HealthInformationStatus.TRANSFERRED
                                                  if overall_transfer_status else HealthInformationStatus.FAILED)
        self.health_information_request.save()

    def gateway_health_information_on_transfer(self, transfer_status, care_contexts_status):
        artefact = self.health_information_request.consent_artefact
        payload = ABDMRequestHelper.common_request_data()
        payload['notification'] = {'consent_id': str(artefact.artefact_id),
                                   'transaction_id': self.request_data['transactionId'],
                                   'doneAt': datetime.utcnow().isoformat()}
        payload['notification']['notifier'] = {'type': 'HIP', 'id': artefact.details['hip']['id']}
        session_status = HealthInformationStatus.TRANSFERRED if transfer_status else HealthInformationStatus.FAILED
        payload['notification']['statusNotification'] = {'sessionStatus': session_status,
                                                         'hipId': artefact.details['hip']['id']}
        # Avoids sending description for care context as optional and could possibly
        # contain internal error details. Could be included in case a need/use case arises later on.
        for care_context_status in care_contexts_status:
            del care_context_status['description']
        payload['notification']['statusNotification']['statusResponses'] = care_contexts_status
        ABDMRequestHelper().gateway_post(HIPGatewayAPIPath.HEALTH_INFO_NOTIFY, payload)
        return payload['requestId']


class HealthDataTransferProcessor:
    media_type = HEALTH_INFORMATION_MEDIA_TYPE
    entries_per_page = 10

    def __init__(self, health_information_request, hi_request):
        self.health_information_request = health_information_request
        self.hi_request = hi_request
        self.care_contexts = health_information_request.consent_artefact.details['careContexts']
        self.crypto = ABDMCrypto(use_x509_for_transfer=True)

    def process(self):
        care_contexts_status = []
        for index, care_contexts_chunks in enumerate(self._generate_chunks(self.care_contexts,
                                                                           self.entries_per_page)):
            care_contexts_chunks_status = self._process_page(index + 1, care_contexts_chunks)
            care_contexts_status.extend(care_contexts_chunks_status)
        overall_transfer_status = not any(status['hiStatus'] == HealthInformationStatus.ERRORED
                                          for status in care_contexts_status)
        return overall_transfer_status, care_contexts_status

    @property
    def page_count(self):
        return int(math.ceil(len(self.care_contexts) / self.entries_per_page))

    def _process_page(self, page_number, care_contexts):
        payload = {'pageCount': self.page_count, 'transactionId': self.health_information_request.transaction_id,
                   'keyMaterial': self.crypto.transfer_material, 'pageNumber': page_number, 'entries': []}
        care_contexts_status = []
        care_contexts_transfer = []

        for care_context in care_contexts:
            try:
                payload['entries'].extend(self._process_care_context(care_context))
                care_contexts_transfer.append(care_context)
            except Exception as err:
                care_contexts_status.extend(self._generate_care_contexts_status([care_context], str(err)))

        # In case no data is available, sends empty entries so that HIU is aware of that.
        error = None
        try:
            self.send_data_to_hiu(payload)
        except Exception as err:
            error = str(err)
        if care_contexts_transfer:
            care_contexts_status.extend(self._generate_care_contexts_status(care_contexts_transfer, error))

        self.save_health_data_transfer(page_number, care_contexts_status)
        return care_contexts_status

    def _process_care_context(self, care_context):
        entries = []
        linked_care_context = self.fetch_linked_care_context(care_context)
        health_info_types = self.check_health_information_types(linked_care_context)
        fhir_data = self.fetch_fhir_data_hrp(linked_care_context, health_info_types)
        for bundle in fhir_data:
            encrypted_entry = self.get_encrypted_entry(care_context['careContextReference'], bundle)
            entries.append(encrypted_entry)
        return entries

    def save_health_data_transfer(self, page_number, care_contexts_status):
        HealthDataTransfer.objects.create(health_information_request=self.health_information_request,
                                          page_number=page_number, care_contexts_status=care_contexts_status)

    def fetch_linked_care_context(self, care_context):
        hip_id = self.health_information_request.consent_artefact.details['hip']['id']
        try:
            return LinkCareContext.objects.get(
                reference=care_context['careContextReference'],
                link_request_details__hip_id=hip_id,
                link_request_details__patient_reference=care_context['patientReference'],
                link_request_details__status=LinkRequestStatus.SUCCESS
            )
        except LinkCareContext.DoesNotExist:
            raise HealthDataTransferException(f"Linked Care Context not found for "
                                              f"{care_context['careContextReference']}")

    def check_health_information_types(self, linked_care_context):
        consented_health_info_types = self.health_information_request.consent_artefact.details['hiTypes']
        health_info_types = list(set(consented_health_info_types).intersection(
            linked_care_context.health_info_types))
        if not health_info_types:
            raise HealthDataTransferException(f'Validation failed for HI Types for care context: '
                                              f'{linked_care_context.reference}')
        return health_info_types

    def fetch_fhir_data_hrp(self, linked_care_context, health_info_types):
        linked_care_context_serialized = LinkCareContextFetchSerializer(linked_care_context).data
        try:
            fhir_data = (app_settings.HRP_INTEGRATION_CLASS().
                         fetch_health_data(linked_care_context.reference,
                                           health_info_types,
                                           linked_care_context_serialized))
        except Exception as err:
            raise HealthDataTransferException(f'Error occurred while fetching health data from HRP: {err}')
        return fhir_data

    def get_encrypted_entry(self, care_context_reference, content):
        entry = {'media': self.media_type, 'careContextReference': care_context_reference}
        try:
            content_str = json.dumps(content)
            entry['checksum'] = self.crypto.generate_checksum(content_str)
            entry['content'] = self.crypto.encrypt(content_str, self.hi_request['keyMaterial'])
        except Exception as err:
            raise HealthDataTransferException(f'Error occurred while encryption process: {err}')
        return entry

    def send_data_to_hiu(self, payload):
        try:
            resp = requests.post(url=self.hi_request['dataPushUrl'], data=json.dumps(payload),
                                 headers={'Content-Type': 'application/json'}, timeout=60)
            resp.raise_for_status()
        except Exception as err:
            raise HealthDataTransferException(f'Error occurred while sending health data to HIU: {err}')

    def _generate_chunks(self, data, count):
        assert type(data) is list
        for i in range(0, len(data), count):
            yield data[i:i + count]

    def _generate_care_contexts_status(self, care_contexts, error=None):
        hi_status = HealthInformationStatus.ERRORED if error else HealthInformationStatus.DELIVERED
        description = error if error else 'Delivered'
        return [{'careContextReference': care_context['careContextReference'], 'hiStatus': hi_status,
                'description': description} for care_context in care_contexts]
