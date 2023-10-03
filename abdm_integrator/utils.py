import json
import time
import uuid
from datetime import datetime

import requests
from django.core.cache import cache
from django.utils.dateparse import parse_datetime
from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination

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
    default_timeout = 60

    def __init__(self):
        self.headers = {'Content-Type': "application/json", 'X-CM-ID': app_settings.X_CM_ID}

    def get_access_token(self):
        headers = {"Content-Type": "application/json; charset=UTF-8"}
        try:
            resp = requests.post(url=self.gateway_base_url + SESSIONS_PATH, data=json.dumps(self.token_payload),
                                 headers=headers, timeout=self.default_timeout)
            resp.raise_for_status()
        except requests.Timeout:
            raise ABDMServiceUnavailable()
        except requests.HTTPError as err:
            error = self.gateway_json_from_response(err.response).get('error', {})
            raise ABDMGatewayError(error.get('code'), error.get('message'))
        return resp.json().get("accessToken")

    def abha_get(self, api_path, additional_headers=None, params=None, timeout=None):
        self.headers.update({"Authorization": f"Bearer {self.get_access_token()}"})
        if additional_headers:
            self.headers.update(additional_headers)
        resp = requests.get(url=self.abha_base_url + api_path, headers=self.headers, params=params,
                            timeout=timeout or self.default_timeout)
        resp.raise_for_status()
        # ABHA APIS may not return 'application/json' content type in headers as per swagger doc
        return _get_json_from_resp(resp)

    def _post(self, url, payload, timeout=None):
        self.headers.update({"Authorization": f"Bearer {self.get_access_token()}"})
        resp = requests.post(url=url, headers=self.headers, data=json.dumps(payload),
                             timeout=timeout or self.default_timeout)
        resp.raise_for_status()
        return resp

    def abha_post(self, api_path, payload, timeout=None):
        resp = self._post(self.abha_base_url + api_path, payload, timeout)
        # ABHA APIS may not return 'application/json' content type in headers as per swagger doc
        return _get_json_from_resp(resp)

    def gateway_post(self, api_path, payload, timeout=None):
        try:
            resp = self._post(self.gateway_base_url + api_path, payload, timeout)
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


def abdm_iso_to_datetime(value):
    return parse_datetime(value).replace(tzinfo=None)


def json_from_file(file_path):
    with open(file_path) as file:
        return json.load(file)


class APIResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 1000


def poll_for_data_in_cache(cache_key, total_attempts=30, interval=2):
    attempt = 1
    while attempt <= total_attempts:
        time.sleep(interval)
        data = cache.get(cache_key)
        if data:
            cache.delete(cache_key)
            return data
        attempt += 1
    return None
