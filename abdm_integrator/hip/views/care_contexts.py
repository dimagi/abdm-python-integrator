import logging
from copy import deepcopy
from dataclasses import dataclass

from django.db import transaction
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_202_ACCEPTED

from abdm_integrator.const import (
    CALLBACK_RESPONSE_CACHE_TIMEOUT,
    AuthenticationMode,
    AuthFetchModesPurpose,
    Gender,
    IdentifierType,
    LinkRequestInitiator,
    LinkRequestStatus,
    RequesterType,
)
from abdm_integrator.exceptions import (
    ABDMGatewayCallbackTimeout,
    ABDMGatewayError,
    ABDMServiceUnavailable,
    CustomError,
)
from abdm_integrator.hip.const import HEADER_NAME_HIP_ID, HIPGatewayAPIPath, SMSOnNotifyStatus
from abdm_integrator.hip.exceptions import (
    DiscoveryMultiplePatientsFoundError,
    DiscoveryNoPatientFoundError,
    HIPError,
)
from abdm_integrator.hip.models import (
    HIPLinkRequest,
    LinkCareContext,
    LinkRequestDetails,
    PatientDiscoveryRequest,
    PatientLinkRequest,
)
from abdm_integrator.hip.serializers.care_contexts import (
    GatewayCareContextsDiscoverSerializer,
    GatewayCareContextsLinkConfirmSerializer,
    GatewayCareContextsLinkInitSerializer,
    GatewayOnAddContextsSerializer,
    GatewayPatientSMSOnNotifySerializer,
    LinkCareContextRequestSerializer,
    PatientSMSNotifySerializer,
)
from abdm_integrator.hip.tasks import (
    process_patient_care_context_discover_request,
    process_patient_care_context_link_confirm_request,
    process_patient_care_context_link_init_request,
)
from abdm_integrator.hip.views.base import HIPBaseView, HIPGatewayBaseView
from abdm_integrator.settings import app_settings
from abdm_integrator.user_auth.views import AuthConfirm, AuthInit
from abdm_integrator.utils import (
    ABDMCache,
    ABDMRequestHelper,
    poll_and_pop_data_from_cache,
    removes_prefix_for_abdm_mobile,
)

logger = logging.getLogger('abdm_integrator')


class LinkCareContextRequest(HIPBaseView):
    """
    API to perform linking of Care Context initiated by HIP. Ensures that care contexts are not already linked,
    makes a request to gateway, polls for callback response for a specific duration. The callback response is
    shared through cache and based on success or error, generates appropriate response to the client.
    """

    def post(self, request, format=None):
        serializer = LinkCareContextRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.ensure_not_already_linked(serializer.data)
        gateway_request_id = self.gateway_add_care_contexts(serializer.data)
        self.save_link_request(request.user, gateway_request_id, serializer.data)
        response_data = poll_and_pop_data_from_cache(gateway_request_id)
        return self.generate_response_from_callback(response_data)

    def ensure_not_already_linked(self, request_data):
        care_contexts_references = [care_context['referenceNumber']
                                    for care_context in request_data['patient']['careContexts']]
        linked_care_contexts = list(
            LinkCareContext.objects.filter(
                reference__in=care_contexts_references,
                link_request_details__hip_id=request_data['hip_id'],
                link_request_details__patient_reference=request_data['patient']['referenceNumber'],
                link_request_details__status=LinkRequestStatus.SUCCESS
            ).values_list('reference', flat=True)
        )
        if linked_care_contexts:
            code = HIPError.CODE_CARE_CONTEXT_ALREADY_LINKED
            message = HIPError.CUSTOM_ERRORS[code].format(linked_care_contexts)
            raise CustomError(
                error_code=code,
                error_message=message,
            )

    def gateway_add_care_contexts(self, request_data):
        payload = ABDMRequestHelper.common_request_data()
        payload['link'] = deepcopy(request_data)
        ABDMRequestHelper().gateway_post(HIPGatewayAPIPath.ADD_CARE_CONTEXTS, payload)
        return payload['requestId']

    @transaction.atomic()
    def save_link_request(self, user, gateway_request_id, request_data):
        link_request_details = LinkRequestDetails.objects.create(
            hip_id=request_data['hip_id'],
            patient_reference=request_data['patient']['referenceNumber'],
            patient_display=request_data['patient']['display'],
            initiated_by=LinkRequestInitiator.HIP
        )
        HIPLinkRequest.objects.create(user=user, gateway_request_id=gateway_request_id,
                                      link_request_details=link_request_details)
        link_care_contexts = [
            LinkCareContext(
                reference=care_context['referenceNumber'],
                display=care_context['display'],
                health_info_types=care_context['hiTypes'],
                additional_info=care_context['additionalInfo'],
                link_request_details=link_request_details
            )
            for care_context in request_data['patient']['careContexts']
        ]
        LinkCareContext.objects.bulk_create(link_care_contexts)
        return link_request_details

    def generate_response_from_callback(self, response_data):
        if not response_data:
            raise ABDMGatewayCallbackTimeout()
        if response_data.get('error'):
            error = response_data['error']
            raise ABDMGatewayError(error.get('code'), error.get('message'))
        return Response(status=HTTP_200_OK, data=response_data["acknowledgement"])


class GatewayOnAddContexts(HIPGatewayBaseView):

    def post(self, request, format=None):
        serializer = GatewayOnAddContextsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.update_linking_status(serializer.data)
        ABDMCache.set(serializer.data['resp']['requestId'], serializer.data, 10)
        return Response(status=HTTP_202_ACCEPTED)

    def update_linking_status(self, request_data):
        link_request_details = HIPLinkRequest.objects.get(
            gateway_request_id=request_data['resp']['requestId']
        ).link_request_details
        if request_data.get('error'):
            link_request_details.status = LinkRequestStatus.ERROR
            link_request_details.error = request_data['error']
        else:
            link_request_details.status = LinkRequestStatus.SUCCESS
        link_request_details.save()


@dataclass
class PatientDetails:
    id: str
    name: str
    gender: str
    year_of_birth: int
    mobile: str = None
    health_id: str = None
    abha_number: str = None


def patient_details_from_request(patient_data):
    patient_details = PatientDetails(
        id=patient_data['id'],
        name=patient_data['name'],
        gender=Gender.TEXT_MAP.get(patient_data['gender']),
        year_of_birth=patient_data['yearOfBirth'],
    )
    for identifier in patient_data['verifiedIdentifiers']:
        if identifier['type'] == IdentifierType.MOBILE:
            patient_details.mobile = removes_prefix_for_abdm_mobile(identifier['value'])
        elif identifier['type'] == IdentifierType.HEALTH_ID:
            patient_details.health_id = identifier['value']
        elif identifier['type'] == IdentifierType.NDHM_HEALTH_NUMBER:
            patient_details.abha_number = identifier['value']
    return patient_details


class GatewayCareContextsDiscover(HIPGatewayBaseView):

    def post(self, request, format=None):
        GatewayCareContextsDiscoverSerializer(data=request.data).is_valid(raise_exception=True)
        request.data['hip_id'] = request.META.get(HEADER_NAME_HIP_ID)
        process_patient_care_context_discover_request.delay(request.data)
        return Response(status=HTTP_202_ACCEPTED)


class GatewayCareContextsDiscoverProcessor:

    def __init__(self, request_data):
        self.request_data = request_data

    def process_request(self):
        discovery_result, error = self.discover_patient_care_contexts()
        if discovery_result and discovery_result['careContexts']:
            discovery_result = self.filter_already_linked_care_contexts(discovery_result)
        self.save_discovery_request(discovery_result, error)
        self.gateway_care_contexts_on_discover(discovery_result, error)

    def discover_patient_care_contexts(self):
        discovery_result = None
        error = None
        try:
            patient_details = patient_details_from_request(self.request_data['patient'])
            discovery_result = (
                app_settings.HRP_INTEGRATION_CLASS().discover_patient_and_care_contexts(
                    patient_details, self.request_data['hip_id']
                )
            )
        except DiscoveryNoPatientFoundError:
            error = {
                'code': HIPError.CODE_PATIENT_NOT_FOUND,
                'message': HIPError.CUSTOM_ERRORS[HIPError.CODE_PATIENT_NOT_FOUND]
            }
        except DiscoveryMultiplePatientsFoundError:
            error = {
                'code': HIPError.CODE_MULTIPLE_PATIENTS_FOUND,
                'message': HIPError.CUSTOM_ERRORS[HIPError.CODE_MULTIPLE_PATIENTS_FOUND]
            }
        except Exception as err:
            logger.exception('ABDM : Error occurred while discovering patient : %s', err)
            error = {
                'code': HIPError.CODE_INTERNAL_ERROR,
                'message': HIPError.CUSTOM_ERRORS[HIPError.CODE_INTERNAL_ERROR]
            }
        return discovery_result, error

    def filter_already_linked_care_contexts(self, discovery_result):
        linked_care_context_references = list(
            LinkCareContext.objects.filter(
                link_request_details__hip_id=self.request_data['hip_id'],
                link_request_details__patient_reference=discovery_result['referenceNumber'],
                link_request_details__status=LinkRequestStatus.SUCCESS,
            ).values_list('reference', flat=True)
        )
        if linked_care_context_references:
            discovery_result['careContexts'] = [
                care_context for care_context in discovery_result['careContexts']
                if care_context['referenceNumber'] not in linked_care_context_references
            ]
        return discovery_result

    def save_discovery_request(self, discovery_result, error=None):
        patient_discovery_request = PatientDiscoveryRequest(
            transaction_id=self.request_data['transactionId'],
            hip_id=self.request_data['hip_id'],
            error=error
        )
        if discovery_result:
            patient_discovery_request.patient_reference_number = discovery_result['referenceNumber']
            patient_discovery_request.patient_display = discovery_result['display']
            patient_discovery_request.care_contexts = discovery_result['careContexts']
        patient_discovery_request.save()

    def gateway_care_contexts_on_discover(self, discovery_result, error=None):
        payload = ABDMRequestHelper.common_request_data()
        payload['transactionId'] = self.request_data['transactionId']
        if discovery_result:
            patient_discovery_result = deepcopy(discovery_result)
            for care_context in patient_discovery_result['careContexts']:
                del care_context['additionalInfo']
                del care_context['hiTypes']
            payload['patient'] = patient_discovery_result
        else:
            payload['error'] = error
        payload['resp'] = {'requestId': self.request_data['requestId']}
        ABDMRequestHelper().gateway_post(HIPGatewayAPIPath.CARE_CONTEXTS_ON_DISCOVER, payload)
        return payload['requestId']


class GatewayCareContextsLinkInit(HIPGatewayBaseView):

    def post(self, request, format=None):
        GatewayCareContextsLinkInitSerializer(data=request.data).is_valid(raise_exception=True)
        request.data['hip_id'] = request.META.get(HEADER_NAME_HIP_ID)
        process_patient_care_context_link_init_request.delay(request.data)
        return Response(status=HTTP_202_ACCEPTED)


class GatewayCareContextsLinkInitProcessor:

    def __init__(self, request_data):
        self.request_data = request_data

    def process_request(self):
        discovery_request = self.get_discovery_request()
        error = self.validate_request(discovery_request)
        if error:
            self.gateway_care_contexts_link_on_init(None, None, error)
            return error

        otp_response = self.send_otp_to_patient()
        if not otp_response or otp_response.get('error'):
            error = self._generate_error_from_otp_response(otp_response)
        link_reference = self.save_link_request(discovery_request, otp_response, error).link_reference
        self.gateway_care_contexts_link_on_init(otp_response, link_reference, error)

    def get_discovery_request(self):
        try:
            return PatientDiscoveryRequest.objects.get(transaction_id=self.request_data['transactionId'])
        except PatientDiscoveryRequest.DoesNotExist:
            return None

    def validate_request(self, discovery_request):
        error_code = None
        if not discovery_request:
            error_code = HIPError.CODE_DISCOVERY_REQUEST_NOT_FOUND
        elif not self._validate_patient_reference_number(discovery_request):
            error_code = HIPError.CODE_LINK_INIT_REQUEST_PATIENT_MISMATCH
        elif not self._validate_requested_care_contexts(discovery_request):
            error_code = HIPError.CODE_LINK_INIT_REQUEST_CARE_CONTEXTS_MISMATCH
        return {'code': error_code, 'message': HIPError.CUSTOM_ERRORS.get(error_code)} if error_code else None

    def _validate_patient_reference_number(self, discovery_request):
        return self.request_data['patient']['referenceNumber'] == discovery_request.patient_reference_number

    def _validate_requested_care_contexts(self, discovery_request):
        requested_care_contexts_references = {
            care_context['referenceNumber'] for care_context in self.request_data['patient']['careContexts']
        }
        discovered_care_context_references = {
            care_context['referenceNumber'] for care_context in discovery_request.care_contexts
        }
        return requested_care_contexts_references.issubset(discovered_care_context_references)

    def send_otp_to_patient(self):
        request_data = {
            'id': self.request_data['patient']['id'],
            'purpose': AuthFetchModesPurpose.LINK,
            'authMode': AuthenticationMode.MOBILE_OTP,
            'requester': {
                'type': RequesterType.HIP,
                'id': self.request_data['hip_id']
            }
        }
        gateway_request_id = AuthInit().gateway_auth_init(request_data)
        response_data = poll_and_pop_data_from_cache(gateway_request_id)
        return response_data

    @staticmethod
    def _generate_error_from_otp_response(otp_response):
        error = {
            'code': HIPError.CODE_LINK_INIT_REQUEST_OTP_GENERATION_FAILED,
            'message': HIPError.CUSTOM_ERRORS.get(HIPError.CODE_LINK_INIT_REQUEST_OTP_GENERATION_FAILED)
        }
        if not otp_response:
            error['message'] += ': Callback response not received in time.'
        elif otp_response.get('error'):
            error['message'] += f": {otp_response['error'].get('message')}"
        return error

    @transaction.atomic()
    def save_link_request(self, discovery_request, otp_response, error=None):
        link_request_details = LinkRequestDetails.objects.create(
            patient_reference=self.request_data['patient']['referenceNumber'],
            patient_display=discovery_request.patient_display,
            hip_id=self.request_data['hip_id'],
            initiated_by=LinkRequestInitiator.PATIENT,
            status=LinkRequestStatus.ERROR if error else LinkRequestStatus.PENDING,
            error=error
        )
        otp_transaction_id = otp_response['auth']['transactionId'] if not error else None
        PatientLinkRequest.objects.create(
            discovery_request=discovery_request,
            otp_transaction_id=otp_transaction_id,
            link_request_details=link_request_details
        )
        LinkCareContext.objects.bulk_create(
            self._get_link_care_contexts_to_insert(discovery_request, link_request_details)
        )
        return link_request_details

    def _get_link_care_contexts_to_insert(self, discovery_request, link_request_details):
        link_care_contexts = []
        for care_context in self.request_data['patient']['careContexts']:
            care_contexts_details = self._get_care_context_details(
                discovery_request.care_contexts,
                care_context['referenceNumber']
            )
            link_care_contexts.append(
                LinkCareContext(
                    reference=care_contexts_details['referenceNumber'],
                    display=care_contexts_details['display'],
                    health_info_types=care_contexts_details['hiTypes'],
                    additional_info=care_contexts_details['additionalInfo'],
                    link_request_details=link_request_details
                )
            )
        return link_care_contexts

    @staticmethod
    def _get_care_context_details(discovered_care_contexts, care_context_reference):
        return next(
            care_context for care_context in discovered_care_contexts
            if care_context['referenceNumber'] == care_context_reference
        )

    def gateway_care_contexts_link_on_init(self, otp_response, link_reference, error=None):
        payload = ABDMRequestHelper.common_request_data()
        payload['transactionId'] = self.request_data['transactionId']
        if error:
            payload['error'] = error
        else:
            payload['link'] = self._generate_link_payload_from_otp_response(otp_response, link_reference)
        payload['resp'] = {'requestId': self.request_data['requestId']}
        ABDMRequestHelper().gateway_post(HIPGatewayAPIPath.CARE_CONTEXTS_LINK_ON_INIT, payload)
        return payload['requestId']

    @staticmethod
    def _generate_link_payload_from_otp_response(otp_response, link_reference):
        return {
            'referenceNumber': str(link_reference),
            'authenticationType': AuthenticationMode.MOBILE_OTP,
            'meta': {
                'communicationMedium': 'MOBILE',
                'communicationHint': otp_response['auth']['meta']['hint'],
                'communicationExpiry': otp_response['auth']['meta']['expiry']
            }
        }


class GatewayCareContextsLinkConfirm(HIPGatewayBaseView):

    def post(self, request, format=None):
        GatewayCareContextsLinkConfirmSerializer(data=request.data).is_valid(raise_exception=True)
        request.data['hip_id'] = request.META.get(HEADER_NAME_HIP_ID)
        process_patient_care_context_link_confirm_request.delay(request.data)
        return Response(status=HTTP_202_ACCEPTED)


class GatewayCareContextsLinkConfirmProcessor:

    def __init__(self, request_data):
        self.request_data = request_data

    def process_request(self):
        link_request_details = self.get_link_request_details()
        error = self.validate_request(link_request_details)
        if error:
            self.gateway_care_contexts_link_on_confirm(link_request_details, error)
            return error

        otp_transaction_id = link_request_details.patient_link_request.otp_transaction_id
        verify_otp_response = self.verify_otp_from_patient(otp_transaction_id)
        if not verify_otp_response or not verify_otp_response.get('auth'):
            error = self._generate_error_from_verify_otp_response(verify_otp_response)

        try:
            self.gateway_care_contexts_link_on_confirm(link_request_details, error)
        except (ABDMServiceUnavailable, ABDMGatewayError) as err:
            error = err.error
        self.update_linking_status(link_request_details, error)

    def get_link_request_details(self):
        try:
            return LinkRequestDetails.objects.get(
                link_reference=self.request_data['confirmation']['linkRefNumber']
            )
        except LinkRequestDetails.DoesNotExist:
            return None

    def validate_request(self, link_request_details):
        if not link_request_details:
            error_code = HIPError.CODE_LINK_REQUEST_NOT_FOUND
            return {'code': error_code, 'message': HIPError.CUSTOM_ERRORS.get(error_code)}

    def verify_otp_from_patient(self, otp_transaction_id):
        request_data = {
            'transactionId': str(otp_transaction_id),
            'credential': {
                'authCode': self.request_data['confirmation']['token']
            }
        }
        gateway_request_id = AuthConfirm().gateway_auth_confirm(request_data)
        response_data = poll_and_pop_data_from_cache(gateway_request_id)
        return response_data

    @staticmethod
    def _generate_error_from_verify_otp_response(verify_otp_response):
        error = {
            'code': HIPError.CODE_LINK_CONFIRM_OTP_VERIFICATION_FAILED,
            'message': HIPError.CUSTOM_ERRORS.get(HIPError.CODE_LINK_CONFIRM_OTP_VERIFICATION_FAILED)
        }
        if not verify_otp_response:
            error['message'] += ': Callback response not received in time.'
        elif verify_otp_response.get('error'):
            error['message'] += f": {verify_otp_response['error'].get('message')}"
        return error

    def gateway_care_contexts_link_on_confirm(self, link_request_details, error=None):
        payload = ABDMRequestHelper.common_request_data()
        if error:
            payload['error'] = error
        else:
            payload['patient'] = self.get_patient_linking_details(link_request_details)
        payload['resp'] = {'requestId': self.request_data['requestId']}
        ABDMRequestHelper().gateway_post(HIPGatewayAPIPath.CARE_CONTEXTS_LINK_ON_CONFIRM, payload)
        return payload['requestId']

    def get_patient_linking_details(self, link_request_details):
        return {
            'referenceNumber': link_request_details.patient_reference,
            'display': link_request_details.patient_display,
            'careContexts': self._get_care_context_details(link_request_details)
        }

    def _get_care_context_details(self, link_request_details):
        return [
            {
                'referenceNumber': care_context.reference,
                'display': care_context.display
            }
            for care_context in link_request_details.care_contexts.all()
        ]

    def update_linking_status(self, link_request_details, error=None):
        if error:
            link_request_details.status = LinkRequestStatus.ERROR
            link_request_details.error = error
        else:
            link_request_details.status = LinkRequestStatus.SUCCESS
        link_request_details.save()


class PatientSMSNotify(HIPBaseView):

    def post(self, request, format=None):
        serializer = PatientSMSNotifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        gateway_request_id = self.gateway_patient_sms_notify(serializer.data)
        response_data = poll_and_pop_data_from_cache(gateway_request_id)
        return self.generate_response_from_callback(response_data)

    def gateway_patient_sms_notify(self, request_data):
        payload = ABDMRequestHelper.common_request_data()
        payload['notification'] = request_data
        ABDMRequestHelper().gateway_post(HIPGatewayAPIPath.PATIENT_SMS_NOTIFY_PATH, payload)
        return payload['requestId']

    @staticmethod
    def generate_response_from_callback(response_data):
        if not response_data:
            raise ABDMGatewayCallbackTimeout()
        if response_data.get('error'):
            error = response_data['error']
            raise ABDMGatewayError(error.get('code'), error.get('message'))
        if response_data.get('status') and response_data['status'] == SMSOnNotifyStatus.ACKNOWLEDGED:
            status = True
        else:
            status = False
        return Response(status=HTTP_200_OK, data={'status': status})


class GatewayPatientSMSOnNotify(HIPGatewayBaseView):

    def post(self, request, format=None):
        serializer = GatewayPatientSMSOnNotifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ABDMCache.set(serializer.data['resp']['requestId'], serializer.data, CALLBACK_RESPONSE_CACHE_TIMEOUT)
        return Response(status=HTTP_202_ACCEPTED)
