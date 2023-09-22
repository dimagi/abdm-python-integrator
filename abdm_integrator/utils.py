import functools
import json

import requests

from abdm_integrator.const import SESSIONS_PATH
from abdm_integrator.exceptions import ABDMAccessTokenException, ABDMConfigurationError
from abdm_integrator.settings import app_settings


class ABDMRequestHelper:
    REQUIRED_CONFIGS = ['ABHA_URL', 'GATEWAY_URL', 'CLIENT_ID', 'CLIENT_SECRET', 'X_CM_ID']
    gateway_base_url = None
    abha_base_url = None
    token_payload = None

    @classmethod
    @functools.cache
    def _check_configs(cls):
        if any(not hasattr(app_settings, config) for config in cls.REQUIRED_CONFIGS):
            raise ABDMConfigurationError("Missing required configurations for ABDM!")
        cls.gateway_base_url = app_settings.GATEWAY_URL
        cls.abha_base_url = app_settings.ABHA_URL
        cls.token_payload = {"clientId": app_settings.CLIENT_ID, "clientSecret": app_settings.CLIENT_SECRET}

    def __init__(self):
        self._check_configs()
        self.headers = {'Content-Type': "application/json", 'X-CM-ID': app_settings.X_CM_ID}

    def get_access_token(self):
        headers = {"Content-Type": "application/json; charset=UTF-8"}
        try:
            resp = requests.post(url=self.gateway_base_url + SESSIONS_PATH, data=json.dumps(self.token_payload),
                                 headers=headers)
            resp.raise_for_status()
        except Exception:
            raise ABDMAccessTokenException
        return resp.json().get("accessToken")

    def abha_get(self, api_path, additional_headers=None, params=None):
        self.headers.update({"Authorization": f"Bearer {self.get_access_token()}"})
        if additional_headers:
            self.headers.update(additional_headers)
        resp = requests.get(url=self.abha_base_url + api_path, headers=self.headers, params=params)
        resp.raise_for_status()
        # ABHA APIS may not return 'application/json' content type in headers as per swagger doc
        return _get_json_from_resp(resp)

    def _post(self, url, payload):
        self.headers.update({"Authorization": f"Bearer {self.get_access_token()}"})
        resp = requests.post(url=url, headers=self.headers, data=json.dumps(payload))
        resp.raise_for_status()
        return resp

    def abha_post(self, api_path, payload):
        resp = self._post(self.abha_base_url + api_path, payload)
        # ABHA APIS may not return 'application/json' content type in headers as per swagger doc
        return _get_json_from_resp(resp)

    def gateway_post(self, api_path, payload):
        resp = self._post(self.gateway_base_url + api_path, payload)
        return self.gateway_json_from_response(resp)

    @staticmethod
    def gateway_json_from_response(resp):
        """Gets JSON Response if 'application/json' is in 'content_type' of headers. """
        resp_json = {}
        content_type = resp.headers.get('content-type')
        if content_type and 'application/json' in content_type:
            resp_json = _get_json_from_resp(resp)
        return resp_json


def _get_json_from_resp(resp):
    try:
        return resp.json()
    except ValueError:
        return {}
