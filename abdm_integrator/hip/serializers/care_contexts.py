from rest_framework import serializers

from abdm_integrator.const import GENDER_CHOICES, HealthInformationType, IdentifierType
from abdm_integrator.hip.models import LinkCareContext
from abdm_integrator.serializers import GatewayCallbackResponseBaseSerializer
from abdm_integrator.utils import past_date_validator


class LinkCareContextRequestSerializer(serializers.Serializer):

    class PatientSerializer(serializers.Serializer):

        class CareContextSerializer(serializers.Serializer):
            class AdditionalInfoSerializer(serializers.Serializer):
                # represents project to which record belongs to. Send dummy value if not applicable.
                domain = serializers.CharField()
                record_date = serializers.DateTimeField(validators=[past_date_validator])

            referenceNumber = serializers.CharField()
            display = serializers.CharField()
            hiTypes = serializers.ListField(child=serializers.ChoiceField(choices=HealthInformationType.CHOICES))
            additionalInfo = AdditionalInfoSerializer()

        referenceNumber = serializers.CharField()
        display = serializers.CharField()
        careContexts = serializers.ListField(child=CareContextSerializer(), min_length=1)

    accessToken = serializers.CharField()
    hip_id = serializers.CharField()
    patient = PatientSerializer()


class GatewayOnAddContextsSerializer(GatewayCallbackResponseBaseSerializer):

    class AcknowledgementSerializer(serializers.Serializer):
        status = serializers.ChoiceField(choices=['SUCCESS'])

    acknowledgement = AcknowledgementSerializer(required=False, allow_null=True)


class LinkCareContextFetchSerializer(serializers.ModelSerializer):
    class Meta:
        model = LinkCareContext
        fields = '__all__'
        depth = 2


class GatewayCareContextsDiscoverSerializer(serializers.Serializer):

    class PatientSerializer(serializers.Serializer):

        class IdentifierSerializer(serializers.Serializer):
            type = serializers.ChoiceField(choices=IdentifierType.CHOICES)
            value = serializers.CharField(allow_null=True)

        id = serializers.CharField()
        name = serializers.CharField()
        gender = serializers.ChoiceField(choices=GENDER_CHOICES)
        yearOfBirth = serializers.IntegerField()
        verifiedIdentifiers = serializers.ListField(child=IdentifierSerializer(), min_length=1)
        unverifiedIdentifiers = serializers.ListField(child=IdentifierSerializer(), required=False,
                                                      allow_null=True)

    requestId = serializers.UUIDField()
    transactionId = serializers.UUIDField()
    patient = PatientSerializer()


class GatewayCareContextsLinkInitSerializer(serializers.Serializer):

    class PatientSerializer(serializers.Serializer):
        class CareContextSerializer(serializers.Serializer):
            referenceNumber = serializers.CharField()

        id = serializers.CharField()
        referenceNumber = serializers.CharField()
        careContexts = serializers.ListField(child=CareContextSerializer(), min_length=1)

    requestId = serializers.UUIDField()
    transactionId = serializers.UUIDField()
    patient = PatientSerializer()
