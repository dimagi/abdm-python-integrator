import json
import uuid
from datetime import datetime

import requests
from rest_framework import serializers

from abdm_integrator.const import SESSIONS_PATH
from abdm_integrator.exceptions import (
    ERROR_FUTURE_DATE_MESSAGE,
    ERROR_PAST_DATE_MESSAGE,
    ABDMGatewayError,
    ABDMServiceUnavailable,
)
from abdm_integrator.settings import app_settings


class ABDMRequestHelper:
    gateway_base_url = app_settings.GATEWAY_URL
    abha_base_url = app_settings.ABHA_URL
    token_payload = {"clientId": app_settings.CLIENT_ID, "clientSecret": app_settings.CLIENT_SECRET}

    def __init__(self):
        self.headers = {'Content-Type': "application/json", 'X-CM-ID': app_settings.X_CM_ID}

    def get_access_token(self):
        headers = {"Content-Type": "application/json; charset=UTF-8"}
        try:
            resp = requests.post(url=self.gateway_base_url + SESSIONS_PATH, data=json.dumps(self.token_payload),
                                 headers=headers)
            resp.raise_for_status()
        except requests.Timeout:
            raise ABDMServiceUnavailable()
        except requests.HTTPError as err:
            error = self.gateway_json_from_response(err.response).get('error', {})
            raise ABDMGatewayError(error.get('code'), error.get('message'))
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
        try:
            resp = self._post(self.gateway_base_url + api_path, payload)
        except requests.Timeout:
            raise ABDMServiceUnavailable()
        except requests.HTTPError as err:
            error = self.gateway_json_from_response(err.response).get('error', {})
            raise ABDMGatewayError(error.get('code'), error.get('message'))
        return self.gateway_json_from_response(resp)

    @staticmethod
    def gateway_json_from_response(resp):
        """Gets JSON Response if 'application/json' is in 'content_type' of headers. """
        resp_json = {}
        content_type = resp.headers.get('content-type')
        if content_type and 'application/json' in content_type:
            resp_json = _get_json_from_resp(resp)
        return resp_json

    @staticmethod
    def common_request_data():
        return {'requestId': str(uuid.uuid4()), 'timestamp': datetime.utcnow().isoformat()}


def _get_json_from_resp(resp):
    try:
        return resp.json()
    except ValueError:
        return {}


def future_date_validator(value):
    if value <= datetime.utcnow():
        raise serializers.ValidationError(ERROR_FUTURE_DATE_MESSAGE)


def past_date_validator(value):
    if value > datetime.utcnow():
        raise serializers.ValidationError(ERROR_PAST_DATE_MESSAGE)
