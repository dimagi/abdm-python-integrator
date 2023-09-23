from django.urls import path

from abdm_integrator.const import GATEWAY_CALLBACK_URL_PREFIX
from abdm_integrator.hiu.views.consents import GatewayConsentRequestOnInit, GenerateConsent

hiu_urls = [
    path('api/hiu/generate_consent_request', GenerateConsent.as_view(), name='generate_consent_request'),
    # APIS that will be triggered by ABDM Gateway
    path(f'{GATEWAY_CALLBACK_URL_PREFIX}/consent-requests/on-init', GatewayConsentRequestOnInit.as_view(),
         name='gateway_consent_request_on_init'),
]
