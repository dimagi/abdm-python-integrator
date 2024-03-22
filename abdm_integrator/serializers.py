from rest_framework import serializers

from abdm_integrator.const import ConsentPurpose, DataAccessMode, TimeUnit
from abdm_integrator.utils import datetime_to_abdm_iso


class ABDMDateTimeField(serializers.DateTimeField):
    """Serializer Date time field with serialized value as iso 8601 in milliseconds and Z appended at the end"""

    def to_representation(self, value):
        if not value:
            return None
        if isinstance(value, str):
            return value
        value = self.enforce_timezone(value)
        return datetime_to_abdm_iso(value)


class GatewayIdSerializer(serializers.Serializer):
    id = serializers.CharField()


class GatewayIdNameSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField(required=False, allow_null=True)


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
    vars()['from'] = ABDMDateTimeField()
    to = ABDMDateTimeField()


class GatewayPermissionSerializer(serializers.Serializer):

    class FrequencySerializer(serializers.Serializer):
        unit = serializers.ChoiceField(choices=TimeUnit.CHOICES)
        value = serializers.IntegerField()
        repeats = serializers.IntegerField()

    accessMode = serializers.ChoiceField(choices=DataAccessMode.CHOICES)
    dateRange = DateRangeSerializer()
    dataEraseAt = ABDMDateTimeField()
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
        expiry = ABDMDateTimeField()
        parameters = serializers.CharField()
        keyValue = serializers.CharField()

    cryptoAlg = serializers.CharField()
    curve = serializers.CharField()
    dhPublicKey = DHPublicKeySerializer()
    nonce = serializers.CharField()
