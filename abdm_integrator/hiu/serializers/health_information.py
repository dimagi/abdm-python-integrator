from rest_framework import serializers

from abdm_integrator.const import HEALTH_INFORMATION_MEDIA_TYPE
from abdm_integrator.serializers import GatewayCallbackResponseBaseSerializer, GatewayKeyMaterialSerializer


class RequestHealthInformationSerializer(serializers.Serializer):
    artefact_id = serializers.UUIDField()


class ReceiveHealthInformationSerializer(serializers.Serializer):
    pageNumber = serializers.IntegerField()
    pageCount = serializers.IntegerField()
    transactionId = serializers.UUIDField()
    entries = serializers.ListField(min_length=1)
    keyMaterial = GatewayKeyMaterialSerializer()

    def validate_entries(self, value):
        for entry in value:
            if entry.get('content'):
                EntryContentSerializer(data=entry).is_valid(raise_exception=True)
            elif entry.get('link'):
                EntryLinkSerializer(data=entry).is_valid(raise_exception=True)
            else:
                raise serializers.ValidationError("Entry should contain either 'content' or link'")
        return value


class EntrySerializer(serializers.Serializer):
    media = serializers.ChoiceField(choices=[HEALTH_INFORMATION_MEDIA_TYPE])
    checksum = serializers.CharField()
    careContextReference = serializers.CharField()


class EntryContentSerializer(EntrySerializer):
    content = serializers.CharField()


class EntryLinkSerializer(EntrySerializer):
    link = serializers.CharField()


class GatewayHealthInformationOnRequestSerializer(GatewayCallbackResponseBaseSerializer):
    class HiRequestSerializer(serializers.Serializer):
        transactionId = serializers.UUIDField()
        sessionStatus = serializers.ChoiceField(choices=['REQUESTED', 'ACKNOWLEDGED'])

    hiRequest = HiRequestSerializer(required=False, allow_null=True)
