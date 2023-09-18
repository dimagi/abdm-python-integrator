from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from abdm_python_integrator.settings import app_settings


class ABHABaseView(APIView):
    authentication_classes = [app_settings.AUTHENTICATION_CLASS]
    permission_classes = [IsAuthenticated]
