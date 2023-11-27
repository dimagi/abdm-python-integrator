from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from abdm_integrator.hip.exceptions import hip_error_response_handler, hip_gateway_error_response_handler
from abdm_integrator.settings import app_settings
from abdm_integrator.utils import ABDMGatewayAuthentication


class HIPBaseView(APIView):
    authentication_classes = [app_settings.AUTHENTICATION_CLASS]
    permission_classes = [IsAuthenticated]

    def get_exception_handler(self):
        return hip_error_response_handler.get_exception_handler()


class HIPGatewayBaseView(APIView):
    authentication_classes = [ABDMGatewayAuthentication]
    permission_classes = [IsAuthenticated]

    def get_exception_handler(self):
        return hip_gateway_error_response_handler.get_exception_handler()
