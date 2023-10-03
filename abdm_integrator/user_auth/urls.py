from django.urls import path

from abdm_integrator.const import GATEWAY_CALLBACK_URL_PREFIX
from abdm_integrator.user_auth.views import AuthFetchModes, GatewayAuthOnFetchModes

user_auth_urls = [
    path('api/user_auth/fetch_auth_modes', AuthFetchModes.as_view(), name='fetch_auth_modes'),

    # APIS that will be triggered by ABDM Gateway
    path(f'{GATEWAY_CALLBACK_URL_PREFIX}/users/auth/on-fetch-modes', GatewayAuthOnFetchModes.as_view(),
         name='gateway_auth_on_fetch_modes'),
]
