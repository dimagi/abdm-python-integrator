from rest_framework.response import Response
from rest_framework.status import HTTP_201_CREATED

from abdm_integrator.hiu.const import HIUGatewayAPIPath
from abdm_integrator.hiu.models import ConsentRequest
from abdm_integrator.hiu.serializers.consents import ConsentRequestSerializer, GenerateConsentSerializer
from abdm_integrator.hiu.views.base import HIUBaseView
from abdm_integrator.utils import ABDMRequestHelper


class GenerateConsent(HIUBaseView):

    def post(self, request, format=None):
        serializer = GenerateConsentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        consent_data = serializer.data
        # TODO Add Check for Health ID is existing
        gateway_request_id = self.gateway_consent_request_init(consent_data)
        consent_request = self.save_consent_request(gateway_request_id, consent_data, request.user)
        return Response(status=HTTP_201_CREATED,
                        data=ConsentRequestSerializer(consent_request).data)

    def gateway_consent_request_init(self, consent_data):
        request_data = ABDMRequestHelper.common_request_data()
        request_data['consent'] = consent_data
        ABDMRequestHelper().gateway_post(HIUGatewayAPIPath.CONSENT_REQUEST_INIT, request_data)
        return request_data["requestId"]

    def save_consent_request(self, gateway_request_id, consent_data, user):
        consent_request = ConsentRequest(user=user, gateway_request_id=gateway_request_id, details=consent_data)
        consent_request.update_user_amendable_details(consent_data['permission'], consent_data['hiTypes'])
        return consent_request
