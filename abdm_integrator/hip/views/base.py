from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from abdm_integrator.hip.exceptions import hip_error_response_handler, hip_gateway_error_response_handler
from abdm_integrator.settings import app_settings


class HIPBaseView(APIView):
    authentication_classes = [app_settings.AUTHENTICATION_CLASS]
    permission_classes = [IsAuthenticated]

    def get_exception_handler(self):
        return hip_error_response_handler.get_exception_handler()


class HIPGatewayBaseView(APIView):

    def get_exception_handler(self):
        return hip_gateway_error_response_handler.get_exception_handler()
