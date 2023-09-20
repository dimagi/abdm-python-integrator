from rest_framework import serializers

from abdm_integrator.const import DataAccessMode, TimeUnit


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


class GatewayPermissionSerializer(serializers.Serializer):

    class DateRangeSerializer(serializers.Serializer):
        vars()['from'] = serializers.DateTimeField()
        to = serializers.DateTimeField()

    class FrequencySerializer(serializers.Serializer):
        unit = serializers.ChoiceField(choices=TimeUnit.CHOICES)
        value = serializers.IntegerField()
        repeats = serializers.IntegerField()

    accessMode = serializers.ChoiceField(choices=DataAccessMode.CHOICES)
    dateRange = DateRangeSerializer()
    dataEraseAt = serializers.DateTimeField()
    frequency = FrequencySerializer()
