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


class AuthRequesterSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=RequesterType.CHOICES)
    id = serializers.CharField()


class AuthInitSerializer(serializers.Serializer):

    id = serializers.CharField()
    purpose = serializers.ChoiceField(choices=AuthFetchModesPurpose.CHOICES)
    requester = AuthRequesterSerializer()
    authMode = serializers.ChoiceField(choices=AuthenticationMode.CHOICES, required=False)

    def validate_authMode(self, data):
        if data == AuthenticationMode.DIRECT:
            raise serializers.ValidationError(f"'{AuthenticationMode.DIRECT}' Auth mode is not supported!")


class GatewayAuthOnInitSerializer(GatewayCallbackResponseBaseSerializer):

    class AuthSerializer(serializers.Serializer):

        class MetaSerializer(serializers.Serializer):
            hint = serializers.CharField(allow_null=True)
            expiry = serializers.CharField()

        transactionId = serializers.CharField()
        mode = serializers.ChoiceField(choices=AuthenticationMode.CHOICES)
        meta = MetaSerializer(required=False)

    auth = AuthSerializer(required=False, allow_null=True)
