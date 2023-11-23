from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from abdm_integrator.abha.exceptions import abha_error_response_handler
from abdm_integrator.settings import app_settings


class ABHABaseView(APIView):
    authentication_classes = [app_settings.AUTHENTICATION_CLASS]
    permission_classes = [IsAuthenticated]

    def get_exception_handler(self):
        return abha_error_response_handler.get_exception_handler()
