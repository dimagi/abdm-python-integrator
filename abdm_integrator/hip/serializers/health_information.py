from rest_framework import serializers

from abdm_integrator.serializers import DateRangeSerializer, GatewayIdSerializer, GatewayKeyMaterialSerializer


class GatewayHealthInformationRequestSerializer(serializers.Serializer):

    class HIRequestSerializer(serializers.Serializer):
        consent = GatewayIdSerializer()
        dateRange = DateRangeSerializer()
        dataPushUrl = serializers.CharField()
        keyMaterial = GatewayKeyMaterialSerializer()

    requestId = serializers.UUIDField()
    transactionId = serializers.UUIDField()
    hiRequest = HIRequestSerializer()
