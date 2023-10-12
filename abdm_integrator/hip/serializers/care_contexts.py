from rest_framework import serializers

from abdm_integrator.const import HealthInformationType
from abdm_integrator.hip.models import LinkCareContext
from abdm_integrator.serializers import GatewayCallbackResponseBaseSerializer


class LinkCareContextRequestSerializer(serializers.Serializer):

    class PatientSerializer(serializers.Serializer):

        class CareContextSerializer(serializers.Serializer):
            referenceNumber = serializers.CharField()
            display = serializers.CharField()
            hiTypes = serializers.ListField(child=serializers.ChoiceField(choices=HealthInformationType.CHOICES))

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
