from copy import deepcopy

from django.db import transaction
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_202_ACCEPTED

from abdm_integrator.const import LinkRequestInitiator, LinkRequestStatus
from abdm_integrator.exceptions import ABDMGatewayCallbackTimeout, ABDMGatewayError, CustomError
from abdm_integrator.hip.const import HIPGatewayAPIPath
from abdm_integrator.hip.exceptions import HIPError
from abdm_integrator.hip.models import HIPLinkRequest, LinkCareContext, LinkRequestDetails
from abdm_integrator.hip.serializers.care_contexts import (
    GatewayOnAddContextsSerializer,
    LinkCareContextRequestSerializer,
)
from abdm_integrator.hip.views.base import HIPBaseView, HIPGatewayBaseView
from abdm_integrator.utils import ABDMCache, ABDMRequestHelper, poll_and_pop_data_from_cache


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
        linked_care_contexts = list(LinkCareContext.objects.filter(
            reference__in=care_contexts_references,
            link_request_details__hip_id=request_data['hip_id'],
            link_request_details__patient_reference=request_data['patient']['referenceNumber'],
            link_request_details__status=LinkRequestStatus.SUCCESS
        ).values_list('reference', flat=True))

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
        # Store any additional info related to care context (* Do not store health data)
        additional_info = {'domain': getattr(user, 'domain', None)}
        link_care_contexts = [LinkCareContext(reference=care_context['referenceNumber'],
                                              display=care_context['display'],
                                              health_info_types=care_context['hiTypes'],
                                              additional_info=additional_info,
                                              link_request_details=link_request_details)
                              for care_context in request_data['patient']['careContexts']]
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
