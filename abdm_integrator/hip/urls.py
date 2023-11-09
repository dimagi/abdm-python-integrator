from django.urls import path

from abdm_integrator.const import GATEWAY_CALLBACK_URL_PREFIX
from abdm_integrator.hip.views.care_contexts import (
    GatewayCareContextsDiscover,
    GatewayCareContextsLinkConfirm,
    GatewayCareContextsLinkInit,
    GatewayOnAddContexts,
    LinkCareContextRequest,
)
from abdm_integrator.hip.views.consents import GatewayConsentRequestNotify
from abdm_integrator.hip.views.health_information import GatewayHealthInformationRequest

hip_urls = [
    path('api/hip/link_care_context', LinkCareContextRequest.as_view(), name='link_care_context'),
    # APIS that will be triggered by ABDM Gateway
    path(f'{GATEWAY_CALLBACK_URL_PREFIX}/consents/hip/notify', GatewayConsentRequestNotify.as_view(),
         name='gateway_consent_request_notify_hip'),
    path(f'{GATEWAY_CALLBACK_URL_PREFIX}/links/link/on-add-contexts', GatewayOnAddContexts.as_view(),
         name='gateway_on_add_contexts'),
    path(f'{GATEWAY_CALLBACK_URL_PREFIX}/health-information/hip/request',
         GatewayHealthInformationRequest.as_view(), name='gateway_health_information_request_hip'),
    path(f'{GATEWAY_CALLBACK_URL_PREFIX}/care-contexts/discover', GatewayCareContextsDiscover.as_view(),
         name='gateway_care_contexts_discover'),
    path(f'{GATEWAY_CALLBACK_URL_PREFIX}/links/link/init', GatewayCareContextsLinkInit.as_view(),
         name='gateway_care_contexts_link_init'),
    path(f'{GATEWAY_CALLBACK_URL_PREFIX}/links/link/confirm', GatewayCareContextsLinkConfirm.as_view(),
         name='gateway_care_contexts_link_confirm'),
]
