from copy import deepcopy
from dataclasses import dataclass

from django.db import transaction
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_202_ACCEPTED

from abdm_integrator.const import IdentifierType, LinkRequestInitiator, LinkRequestStatus
from abdm_integrator.exceptions import ABDMGatewayCallbackTimeout, ABDMGatewayError, CustomError
from abdm_integrator.hip.const import HIPGatewayAPIPath
from abdm_integrator.hip.exceptions import (
    DiscoveryMultiplePatientsFoundError,
    DiscoveryNoPatientFoundError,
    HIPError,
)
from abdm_integrator.hip.models import HIPLinkRequest, LinkCareContext, LinkRequestDetails, PatientDiscoveryRequest
from abdm_integrator.hip.serializers.care_contexts import (
    GatewayCareContextsDiscoverSerializer,
    GatewayOnAddContextsSerializer,
    LinkCareContextRequestSerializer,
)
from abdm_integrator.hip.tasks import process_patient_care_context_discover_request
from abdm_integrator.hip.views.base import HIPBaseView, HIPGatewayBaseView
from abdm_integrator.settings import app_settings
from abdm_integrator.utils import (
    ABDMCache,
    ABDMRequestHelper,
    poll_and_pop_data_from_cache,
    removes_prefix_for_abdm_mobile,
)


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
        gender=patient_data['gender'],
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
        request.data['hip_id'] = request.META.get('HTTP_X_HIP_ID')
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
            # TODO Use logging instead
            print(f'Error occurred while discovering patient : {err}')
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
