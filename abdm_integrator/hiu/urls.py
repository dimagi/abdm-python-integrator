from django.urls import path

from abdm_integrator.hiu.views.consents import GenerateConsent

hiu_urls = [
    path('api/hiu/generate_consent_request', GenerateConsent.as_view(), name='generate_consent_request'),
]
