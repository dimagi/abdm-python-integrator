from rest_framework import serializers

from abdm_integrator.const import ConsentPurpose, DataAccessMode, TimeUnit


class GatewayIdSerializer(serializers.Serializer):
    id = serializers.CharField()


class GatewayCareContextSerializer(serializers.Serializer):
    patientReference = serializers.CharField()
    careContextReference = serializers.CharField()


class GatewayRequesterSerializer(serializers.Serializer):

    class IdentifierSerializer(serializers.Serializer):
        type = serializers.CharField()
        value = serializers.CharField()
        system = serializers.CharField(required=False, allow_null=True)

    name = serializers.CharField()
    identifier = IdentifierSerializer(required=False)


class DateRangeSerializer(serializers.Serializer):
    vars()['from'] = serializers.DateTimeField()
    to = serializers.DateTimeField()


class GatewayPermissionSerializer(serializers.Serializer):

    class FrequencySerializer(serializers.Serializer):
        unit = serializers.ChoiceField(choices=TimeUnit.CHOICES)
        value = serializers.IntegerField()
        repeats = serializers.IntegerField()

    accessMode = serializers.ChoiceField(choices=DataAccessMode.CHOICES)
    dateRange = DateRangeSerializer()
    dataEraseAt = serializers.DateTimeField()
    frequency = FrequencySerializer()


class GatewayRequestIdSerializer(serializers.Serializer):
    requestId = serializers.UUIDField()


class GatewayCallbackResponseBaseSerializer(serializers.Serializer):
    class GatewayResponseErrorSerializer(serializers.Serializer):
        code = serializers.IntegerField()
        message = serializers.CharField()

    requestId = serializers.UUIDField()
    error = GatewayResponseErrorSerializer(required=False, allow_null=True)
    resp = GatewayRequestIdSerializer()


class GatewayPurposeSerializer(serializers.Serializer):
    code = serializers.ChoiceField(choices=ConsentPurpose.CHOICES)
    text = serializers.CharField()
    refUri = serializers.CharField(required=False, allow_null=True)


class GatewayKeyMaterialSerializer(serializers.Serializer):

    class DHPublicKeySerializer(serializers.Serializer):
        expiry = serializers.DateTimeField()
        parameters = serializers.CharField()
        keyValue = serializers.CharField()

    cryptoAlg = serializers.CharField()
    curve = serializers.CharField()
    dhPublicKey = DHPublicKeySerializer()
    nonce = serializers.CharField()
