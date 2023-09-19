from django.conf import settings

from abdm_integrator.abha.urls import abha_urls

urlpatterns = []

if 'abdm_integrator.abha' in settings.INSTALLED_APPS:
    urlpatterns += abha_urls
