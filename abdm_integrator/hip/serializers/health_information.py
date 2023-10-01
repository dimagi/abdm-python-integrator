from rest_framework import serializers

from abdm_integrator.serializers import (
    GatewayIdSerializer,
    GatewayKeyMaterialSerializer,
    GatewayPermissionSerializer,
)


class GatewayHealthInformationRequestSerializer(serializers.Serializer):

    class HIRequestSerializer(serializers.Serializer):
        consent = GatewayIdSerializer()
        dateRange = GatewayPermissionSerializer.DateRangeSerializer()
        dataPushUrl = serializers.CharField()
        keyMaterial = GatewayKeyMaterialSerializer()

    requestId = serializers.UUIDField()
    transactionId = serializers.UUIDField()
    hiRequest = HIRequestSerializer()
