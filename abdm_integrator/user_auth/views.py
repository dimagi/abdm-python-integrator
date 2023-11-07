from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_202_ACCEPTED
from rest_framework.views import APIView

from abdm_integrator.const import AuthenticationMode
from abdm_integrator.exceptions import ABDMGatewayCallbackTimeout, ABDMGatewayError
from abdm_integrator.settings import app_settings
from abdm_integrator.user_auth.const import CALLBACK_RESPONSE_CACHE_TIMEOUT, UserAuthGatewayAPIPath
from abdm_integrator.user_auth.exceptions import (
    user_auth_error_response_handler,
    user_auth_gateway_error_response_handler,
)
from abdm_integrator.user_auth.serializers import (
    AuthConfirmSerializer,
    AuthFetchModesSerializer,
    AuthInitSerializer,
    GatewayAuthOnConfirmSerializer,
    GatewayAuthOnFetchModesSerializer,
    GatewayAuthOnInitSerializer,
)
from abdm_integrator.utils import (
    ABDMCache,
    ABDMGatewayAuthentication,
    ABDMRequestHelper,
    poll_and_pop_data_from_cache,
)


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
        return Response(status=HTTP_200_OK, data=response_data['auth'])


class UserAuthGatewayBaseView(APIView):
    authentication_classes = [ABDMGatewayAuthentication]
    serializer_class = None

    def get_exception_handler(self):
        return user_auth_gateway_error_response_handler.get_exception_handler()

    def post(self, request, format=None):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        ABDMCache.set(serializer.data['resp']['requestId'], serializer.data, CALLBACK_RESPONSE_CACHE_TIMEOUT)
        return Response(status=HTTP_202_ACCEPTED)


class AuthFetchModes(UserAuthBaseView):

    def post(self, request, format=None):
        serializer = AuthFetchModesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        gateway_request_id = self.gateway_auth_fetch_modes(serializer.data)
        response_data = poll_and_pop_data_from_cache(gateway_request_id)
        # Authentication Mode DIRECT is not yet supported.
        response_data = self.remove_direct_and_password_mode(response_data)
        return self.generate_response_from_callback(response_data)

    def gateway_auth_fetch_modes(self, request_data):
        payload = ABDMRequestHelper.common_request_data()
        payload['query'] = request_data
        ABDMRequestHelper().gateway_post(UserAuthGatewayAPIPath.FETCH_AUTH_MODES, payload)
        return payload['requestId']

    def remove_direct_and_password_mode(self, response_data):
        if response_data and response_data.get('auth'):
            if AuthenticationMode.DIRECT in response_data['auth']['modes']:
                response_data['auth']['modes'].remove(AuthenticationMode.DIRECT)
            # Invalid Password mode is being returned.
            # See https://devforum.abdm.gov.in/t/care-context-link-otp-not-received/8006/2?u=ayadav
            if AuthenticationMode.PASSWORD in response_data['auth']['modes']:
                response_data['auth']['modes'].remove(AuthenticationMode.PASSWORD)
        return response_data


class GatewayAuthOnFetchModes(UserAuthGatewayBaseView):
    serializer_class = GatewayAuthOnFetchModesSerializer


class AuthInit(UserAuthBaseView):

    def post(self, request, format=None):
        serializer = AuthInitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        gateway_request_id = self.gateway_auth_init(serializer.data)
        response_data = poll_and_pop_data_from_cache(gateway_request_id)
        return self.generate_response_from_callback(response_data)

    def gateway_auth_init(self, request_data):
        payload = ABDMRequestHelper.common_request_data()
        payload['query'] = request_data
        ABDMRequestHelper().gateway_post(UserAuthGatewayAPIPath.AUTH_INIT, payload)
        return payload['requestId']


class GatewayAuthOnInit(UserAuthGatewayBaseView):
    serializer_class = GatewayAuthOnInitSerializer


class AuthConfirm(UserAuthBaseView):

    def post(self, request, format=None):
        serializer = AuthConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        gateway_request_id = self.gateway_auth_confirm(serializer.data)
        response_data = poll_and_pop_data_from_cache(gateway_request_id)
        return self.generate_response_from_callback(response_data)

    def gateway_auth_confirm(self, request_data):
        payload = ABDMRequestHelper.common_request_data()
        payload['transactionId'] = request_data.pop('transactionId')
        payload['credential'] = request_data['credential']
        ABDMRequestHelper().gateway_post(UserAuthGatewayAPIPath.AUTH_CONFIRM, payload)
        return payload['requestId']


class GatewayAuthOnConfirm(UserAuthGatewayBaseView):
    serializer_class = GatewayAuthOnConfirmSerializer
