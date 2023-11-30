from django.utils.decorators import method_decorator
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from abdm_integrator._api_logger import log_api
from abdm_integrator.hiu.exceptions import hiu_error_response_handler, hiu_gateway_error_response_handler
from abdm_integrator.settings import app_settings
from abdm_integrator.utils import ABDMGatewayAuthentication


class HIUBaseView(APIView):
    authentication_classes = [app_settings.AUTHENTICATION_CLASS]
    permission_classes = [IsAuthenticated]

    def get_exception_handler(self):
        return hiu_error_response_handler.get_exception_handler()


@method_decorator(log_api, name='dispatch')
class HIUGatewayBaseView(APIView):
    authentication_classes = [ABDMGatewayAuthentication]
    permission_classes = [IsAuthenticated]

    def get_exception_handler(self):
        return hiu_gateway_error_response_handler.get_exception_handler()
