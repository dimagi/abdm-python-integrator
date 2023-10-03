from django.core.cache import cache
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_202_ACCEPTED
from rest_framework.views import APIView

from abdm_integrator.const import AuthenticationMode
from abdm_integrator.exceptions import ABDMGatewayCallbackTimeout, ABDMGatewayError
from abdm_integrator.settings import app_settings
from abdm_integrator.user_auth.const import UserAuthGatewayAPIPath
from abdm_integrator.user_auth.exceptions import (
    user_auth_error_response_handler,
    user_auth_gateway_error_response_handler,
)
from abdm_integrator.user_auth.serializers import AuthFetchModesSerializer, GatewayAuthOnFetchModesSerializer
from abdm_integrator.utils import ABDMRequestHelper, poll_for_data_in_cache


class UserAuthBaseView(APIView):
    authentication_classes = [app_settings.AUTHENTICATION_CLASS]
    permission_classes = [IsAuthenticated]

    def get_exception_handler(self):
        return user_auth_error_response_handler.get_exception_handler()

    @staticmethod
    def generate_response_from_callback(response_data):
        if not response_data:
            raise ABDMGatewayCallbackTimeout()
        if response_data.get('error'):
            error = response_data['error']
            raise ABDMGatewayError(error.get('code'), error.get('message'))
        return Response(status=200, data=response_data['auth'])


class UserAuthGatewayBaseView(APIView):

    def get_exception_handler(self):
        return user_auth_gateway_error_response_handler.get_exception_handler()


class AuthFetchModes(UserAuthBaseView):

    def post(self, request, format=None):
        serializer = AuthFetchModesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        gateway_request_id = self.gateway_auth_fetch_modes(serializer.data)
        response_data = poll_for_data_in_cache(gateway_request_id)
        # Authentication Mode DIRECT is not yet supported.
        response_data = self.remove_direct_mode(response_data)
        return self.generate_response_from_callback(response_data)

    def gateway_auth_fetch_modes(self, request_data):
        payload = ABDMRequestHelper.common_request_data()
        payload['query'] = request_data
        ABDMRequestHelper().gateway_post(UserAuthGatewayAPIPath.FETCH_AUTH_MODES, payload)
        return payload["requestId"]

    def remove_direct_mode(self, response_data):
        if (response_data and response_data.get('auth')
                and AuthenticationMode.DIRECT in response_data['auth']['modes']):
            response_data['auth']['modes'].remove(AuthenticationMode.DIRECT)
        return response_data


class GatewayAuthOnFetchModes(UserAuthGatewayBaseView):

    def post(self, request, format=None):
        serializer = GatewayAuthOnFetchModesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cache.set(serializer.data['resp']['requestId'], serializer.data, 10)
        return Response(status=HTTP_202_ACCEPTED)
