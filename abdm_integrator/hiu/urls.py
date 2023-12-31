from django.urls import path

from abdm_integrator.const import GATEWAY_CALLBACK_URL_PREFIX
from abdm_integrator.hiu.views.consents import (
    ConsentArtefactFetch,
    ConsentFetch,
    GatewayConsentRequestNotify,
    GatewayConsentRequestOnFetch,
    GatewayConsentRequestOnInit,
    GenerateConsent,
)
from abdm_integrator.hiu.views.health_information import (
    GatewayHealthInformationOnRequest,
    ReceiveHealthInformation,
    RequestHealthInformation,
)

hiu_urls = [
    path('api/hiu/generate_consent_request', GenerateConsent.as_view(), name='generate_consent_request'),
    path('api/hiu/consents', ConsentFetch.as_view({'get': 'list'}), name='consents_list'),
    path('api/hiu/consents/<int:pk>', ConsentFetch.as_view({'get': 'retrieve'}), name='consents_retrieve'),
    path('api/hiu/consent_artefacts', ConsentArtefactFetch.as_view({'get': 'list'}), name='artefacts_list'),
    path('api/hiu/consent_artefacts/<int:pk>', ConsentArtefactFetch.as_view({'get': 'retrieve'}),
         name='artefacts_retrieve'),
    path('api/hiu/health-information/request', RequestHealthInformation.as_view(),
         name='request_health_information'),
    path('api/hiu/health-information/receive', ReceiveHealthInformation.as_view(),
         name='receive_health_information'),
    # APIS that will be triggered by ABDM Gateway
    path(f'{GATEWAY_CALLBACK_URL_PREFIX}/consent-requests/on-init', GatewayConsentRequestOnInit.as_view(),
         name='gateway_consent_request_on_init'),
    path(f'{GATEWAY_CALLBACK_URL_PREFIX}/consents/hiu/notify', GatewayConsentRequestNotify.as_view(),
         name='gateway_consent_request_notify'),
    path(f'{GATEWAY_CALLBACK_URL_PREFIX}/consents/on-fetch', GatewayConsentRequestOnFetch.as_view(),
         name='gateway_consent_request_on_fetch'),
    path(f'{GATEWAY_CALLBACK_URL_PREFIX}/health-information/hiu/on-request',
         GatewayHealthInformationOnRequest.as_view(),
         name='gateway_health_information_on_request'),
]
