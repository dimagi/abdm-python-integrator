from rest_framework import serializers

from abdm_integrator.const import ConsentStatus, HealthInformationType
from abdm_integrator.serializers import (
    GatewayCareContextSerializer,
    GatewayIdSerializer,
    GatewayPermissionSerializer,
    GatewayPurposeSerializer,
)


class GatewayConsentRequestNotifySerializer(serializers.Serializer):

    class NotificationSerializer(serializers.Serializer):

        class ConsentDetailSerializer(serializers.Serializer):
            schemaVersion = serializers.CharField(required=False)
            consentId = serializers.UUIDField()
            createdAt = serializers.DateTimeField()
            patient = GatewayIdSerializer()
            careContexts = serializers.ListField(child=GatewayCareContextSerializer(), min_length=1)
            purpose = GatewayPurposeSerializer()
            hip = GatewayIdSerializer()
            consentManager = GatewayIdSerializer()
            hiTypes = serializers.ListField(child=serializers.ChoiceField(choices=HealthInformationType.CHOICES),
                                            min_length=1)
            permission = GatewayPermissionSerializer()

        consentId = serializers.CharField()
        status = serializers.ChoiceField(choices=ConsentStatus.HIP_GATEWAY_CHOICES)
        consentDetail = ConsentDetailSerializer(required=False)
        signature = serializers.CharField()
        grantAcknowledgement = serializers.BooleanField()

    requestId = serializers.UUIDField()
    notification = NotificationSerializer()
