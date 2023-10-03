from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from abdm_integrator.settings import app_settings
from abdm_integrator.user_auth.exceptions import (
    user_auth_error_response_handler,
    user_auth_gateway_error_response_handler,
)


class UserAuthBaseView(APIView):
    authentication_classes = [app_settings.AUTHENTICATION_CLASS]
    permission_classes = [IsAuthenticated]

    def get_exception_handler(self):
        return user_auth_error_response_handler.get_exception_handler()


class UserAuthGatewayBaseView(APIView):

    def get_exception_handler(self):
        return user_auth_gateway_error_response_handler.get_exception_handler()
