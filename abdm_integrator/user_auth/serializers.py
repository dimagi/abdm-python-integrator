from rest_framework import serializers

from abdm_integrator.const import AuthenticationMode, AuthFetchModesPurpose, Gender, IdentifierType, RequesterType
from abdm_integrator.serializers import ABDMDateTimeField, GatewayCallbackResponseBaseSerializer


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
    id = serializers.CharField(required=False)


class AuthInitSerializer(serializers.Serializer):

    id = serializers.CharField()
    purpose = serializers.ChoiceField(choices=AuthFetchModesPurpose.CHOICES)
    requester = AuthRequesterSerializer()
    authMode = serializers.ChoiceField(choices=AuthenticationMode.CHOICES, required=False)

    def validate_authMode(self, data):
        if data == AuthenticationMode.DIRECT:
            raise serializers.ValidationError(f"'{AuthenticationMode.DIRECT}' Auth mode is not supported!")
        return data


class GatewayAuthOnInitSerializer(GatewayCallbackResponseBaseSerializer):

    class AuthSerializer(serializers.Serializer):

        class MetaSerializer(serializers.Serializer):
            hint = serializers.CharField(allow_null=True)
            expiry = serializers.CharField()

        transactionId = serializers.CharField()
        mode = serializers.ChoiceField(choices=AuthenticationMode.CHOICES)
        meta = MetaSerializer(required=False)

    auth = AuthSerializer(required=False, allow_null=True)


class AuthConfirmSerializer(serializers.Serializer):

    class CredentialSerializer(serializers.Serializer):

        class DemographicSerializer(serializers.Serializer):

            class IdentifierSerializer(serializers.Serializer):
                type = serializers.ChoiceField(choices=['MOBILE'])
                value = serializers.CharField()

            name = serializers.CharField()
            gender = serializers.ChoiceField(choices=Gender.CHOICES)
            dateOfBirth = serializers.CharField()
            identifier = IdentifierSerializer(required=False)

        authCode = serializers.CharField(required=False)
        demographic = DemographicSerializer(required=False)

    transactionId = serializers.CharField()
    credential = CredentialSerializer()


class GatewayAuthOnConfirmSerializer(GatewayCallbackResponseBaseSerializer):

    class AuthSerializer(serializers.Serializer):

        class TokenValiditySerializer(serializers.Serializer):
            purpose = serializers.ChoiceField(choices=AuthFetchModesPurpose.CHOICES)
            requester = AuthRequesterSerializer()
            expiry = ABDMDateTimeField()
            limit = serializers.IntegerField()

        class PatientDemographicSerializer(serializers.Serializer):

            class IdentifierSerializer(serializers.Serializer):
                type = serializers.ChoiceField(choices=IdentifierType.CHOICES)
                value = serializers.CharField()

            class AddressSerializer(serializers.Serializer):
                line = serializers.CharField(required=False)
                district = serializers.CharField(required=False)
                state = serializers.CharField(required=False)
                pincode = serializers.CharField(required=False)

            id = serializers.CharField()
            name = serializers.CharField()
            gender = serializers.ChoiceField(choices=Gender.CHOICES)
            yearOfBirth = serializers.IntegerField()
            address = AddressSerializer(required=False, allow_null=True)
            identifier = IdentifierSerializer(required=False, allow_null=True)

        accessToken = serializers.CharField(required=False, allow_null=True)
        validity = TokenValiditySerializer(required=False, allow_null=True)
        patient = PatientDemographicSerializer(required=False, allow_null=True)

    auth = AuthSerializer(required=False, allow_null=True)
