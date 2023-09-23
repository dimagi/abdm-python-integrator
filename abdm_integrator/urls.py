from django.conf import settings

from abdm_integrator.abha.urls import abha_urls
from abdm_integrator.hiu.urls import hiu_urls

urlpatterns = []

if 'abdm_integrator.abha' in settings.INSTALLED_APPS:
    urlpatterns += abha_urls
if 'abdm_integrator.hiu' in settings.INSTALLED_APPS:
    urlpatterns += hiu_urls
