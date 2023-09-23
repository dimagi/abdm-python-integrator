from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from abdm_integrator.hiu.exceptions import hiu_error_response_handler, hiu_gateway_error_response_handler
from abdm_integrator.settings import app_settings


class HIUBaseView(APIView):
    authentication_classes = [app_settings.AUTHENTICATION_CLASS]
    permission_classes = [IsAuthenticated]

    def get_exception_handler(self):
        return hiu_error_response_handler.get_exception_handler()


class HIUGatewayBaseView(APIView):

    def get_exception_handler(self):
        return hiu_gateway_error_response_handler.get_exception_handler()
