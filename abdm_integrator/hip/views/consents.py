from django.db import transaction
from rest_framework.response import Response
from rest_framework.status import HTTP_202_ACCEPTED

from abdm_integrator.const import ConsentStatus
from abdm_integrator.hip.const import HIPGatewayAPIPath
from abdm_integrator.hip.models import ConsentArtefact
from abdm_integrator.hip.serializers.consents import GatewayConsentRequestNotifySerializer
from abdm_integrator.hip.tasks import process_hip_consent_notification_request
from abdm_integrator.hip.views.base import HIPGatewayBaseView
from abdm_integrator.utils import ABDMRequestHelper


class GatewayConsentRequestNotify(HIPGatewayBaseView):

    def post(self, request, format=None):
        GatewayConsentRequestNotifySerializer(data=request.data).is_valid(raise_exception=True)
        process_hip_consent_notification_request.delay(request.data)
        return Response(status=HTTP_202_ACCEPTED)


class GatewayConsentRequestNotifyProcessor:

    def __init__(self, request_data):
        self.request_data = request_data

    @transaction.atomic
    def process_request(self):
        artefact_id = self.request_data['notification']['consentId']
        if self.request_data['notification']['status'] in (ConsentStatus.REVOKED, ConsentStatus.EXPIRED):
            ConsentArtefact.objects.get(artefact_id=artefact_id).delete()
        else:
            consent_artefact = ConsentArtefact(
                artefact_id=artefact_id,
                signature=self.request_data['notification']['signature'],
                details=self.request_data['notification']['consentDetail'],
                grant_acknowledgement=self.request_data['notification']['grantAcknowledgement']
            )
            consent_artefact.save()
        self.gateway_consents_on_notify(artefact_id)

    def gateway_consents_on_notify(self, artefact_id):
        payload = ABDMRequestHelper.common_request_data()
        payload['acknowledgement'] = {'status': 'OK', 'consentId': artefact_id}
        payload['resp'] = {'requestId': self.request_data['requestId']}
        ABDMRequestHelper().gateway_post(HIPGatewayAPIPath.CONSENT_REQUEST_ON_NOTIFY_PATH, payload)
        return payload['requestId']
