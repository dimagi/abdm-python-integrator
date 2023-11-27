import json
import time
import uuid
from datetime import datetime

import jwt
import requests
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.utils.dateparse import parse_datetime
from rest_framework import serializers
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.pagination import PageNumberPagination

from abdm_integrator.const import GatewayAPIPath
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
            resp = requests.post(url=self.gateway_base_url + GatewayAPIPath.SESSIONS_PATH,
                                 data=json.dumps(self.token_payload),
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


class ABDMCache:
    """Wrapper class around Django's default cache for ABDM related cache operations"""
    _cache = cache
    prefix = 'abdm_'

    @classmethod
    def set(cls, key, value, timeout):
        key = cls._key_with_prefix(key)
        return cls._cache.set(key, value, timeout)

    @classmethod
    def get(cls, key):
        key = cls._key_with_prefix(key)
        return cls._cache.get(key)

    @classmethod
    def delete(cls, key):
        key = cls._key_with_prefix(key)
        return cls._cache.delete(key)

    @classmethod
    def _key_with_prefix(cls, key):
        return f'{cls.prefix}{key}'


def poll_and_pop_data_from_cache(cache_key, total_attempts=30, interval=2):
    attempt = 1
    while attempt <= total_attempts:
        time.sleep(interval)
        data = ABDMCache.get(cache_key)
        if data:
            ABDMCache.delete(cache_key)
            return data
        attempt += 1
    return None


def fetch_gateway_jwks_cert():
    resp = requests.get(app_settings.GATEWAY_URL + GatewayAPIPath.CERTS_PATH)
    resp.raise_for_status()
    return resp.json()


def gateway_jwks_cert():
    jwks_cert = ABDMCache.get('JWKS_CERT')
    if not jwks_cert:
        jwks_cert = fetch_gateway_jwks_cert()
        ABDMCache.set('JWKS_CERT', jwks_cert, timeout=60 * 180)
    return jwks_cert


def validate_jwt_access_token(authorisation_token):
    jwks_cert = gateway_jwks_cert()
    jwks_keys = jwt.api_jwk.PyJWKSet(jwks_cert['keys'])
    kid = jwt.get_unverified_header(authorisation_token)['kid']
    algorithms = [key['alg'] for key in jwks_cert['keys'] if key['kid'] == kid]
    return jwt.decode(authorisation_token, key=jwks_keys[kid].key, algorithms=algorithms,
                      options={'verify_aud': False})


class ABDMGatewayUser(AnonymousUser):
    """Dummy user used for ABDM Gateway JWKS authentication"""
    username = 'gateway_user'


class ABDMGatewayAuthentication(TokenAuthentication):
    keyword = 'Bearer'

    def authenticate_credentials(self, token):
        try:
            validate_jwt_access_token(authorisation_token=token)
        except jwt.exceptions.InvalidTokenError:
            raise AuthenticationFailed('Token validation failed')
        except Exception:
            raise AuthenticationFailed('Error occurred while validating token')
        # Returns Django ABDMGatewayUser after successful token validation as authentication expects a user
        return ABDMGatewayUser, token


def removes_prefix_for_abdm_mobile(value):
    if value.startswith('+91-'):
        return value[4:]
    elif value.startswith('+91'):
        return value[3:]
    return value
