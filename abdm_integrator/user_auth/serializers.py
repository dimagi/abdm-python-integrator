from rest_framework import serializers

from abdm_integrator.const import AuthenticationMode, AuthFetchModesPurpose, RequesterType
from abdm_integrator.serializers import GatewayCallbackResponseBaseSerializer


class AuthFetchModesSerializer(serializers.Serializer):

    class RequesterSerializer(serializers.Serializer):
        type = serializers.ChoiceField(choices=RequesterType.CHOICES)
        id = serializers.CharField()

    id = serializers.CharField()
    purpose = serializers.ChoiceField(choices=AuthFetchModesPurpose.CHOICES)
    requester = RequesterSerializer()


class GatewayAuthOnFetchModesSerializer(GatewayCallbackResponseBaseSerializer):

    class AuthSerializer(serializers.Serializer):
        purpose = serializers.ChoiceField(choices=AuthFetchModesPurpose.CHOICES)
        modes = serializers.ListField(child=serializers.ChoiceField(choices=AuthenticationMode.CHOICES))

    auth = AuthSerializer(required=False, allow_null=True)
