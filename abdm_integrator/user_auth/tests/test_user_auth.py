import json
import uuid
from datetime import datetime
from unittest.mock import patch

import requests
from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST
from rest_framework.test import APIClient, APITestCase

from abdm_integrator.exceptions import (
    ERROR_CODE_INVALID_CHOICE,
    ERROR_CODE_INVALID_CHOICE_MESSAGE,
    ERROR_CODE_REQUIRED,
    ERROR_CODE_REQUIRED_MESSAGE,
    STANDARD_ERRORS,
)
from abdm_integrator.tests.utils import APITestHelperMixin
from abdm_integrator.user_auth.exceptions import UserAuthError
from abdm_integrator.utils import cache_key_with_prefix


class TestUserAuthAPI(APITestCase, APITestHelperMixin):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_superuser(username='test_user', password='test')
        cls.token = Token.objects.create(user=cls.user)
        cls.fetch_auth_modes_url = reverse('fetch_auth_modes')
        cls.auth_init_url = reverse('auth_init')
        cls.auth_confirm_url = reverse('auth_confirm')

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token}')

    @classmethod
    def tearDownClass(cls):
        User.objects.all().delete()
        super().tearDownClass()

    @staticmethod
    def _fetch_auth_modes_sample_request_data():
        return {
            'id': 'test_user@sbx',
            'purpose': 'LINK',
            'requester': {
                'type': 'HIU',
                'id': 'TEST-HIU'
            }
        }

    @staticmethod
    def _auth_init_sample_request_data():
        return {
            'id': 'test_user@sbx',
            'purpose': 'LINK',
            "authMode": "MOBILE_OTP",
            'requester': {
                'type': 'HIU',
                'id': 'TEST-HIU'
            }
        }

    @staticmethod
    def _auth_confirm_sample_request_data():
        return {
            'transactionId': str(uuid.uuid4()),
            'credential': {
                'authCode': '123456'
            }
        }

    @staticmethod
    def _mock_callback_response_with_cache(gateway_request_id, response_data):
        cache_key = cache_key_with_prefix(gateway_request_id)
        mocked_callback_response = {
            'requestId': str(uuid.uuid4()),
            'timestamp': datetime.utcnow().isoformat(),
            'error': None,
            'resp': {
                'requestId': gateway_request_id
            }
        }
        mocked_callback_response.update(response_data)
        cache.set(cache_key, mocked_callback_response, 10)

    @patch('abdm_integrator.user_auth.views.ABDMRequestHelper.gateway_post', return_value={})
    @patch('abdm_integrator.user_auth.views.ABDMRequestHelper.common_request_data')
    def test_fetch_auth_modes_success(self, mocked_common_request_data, *args):
        mocked_common_request_data.return_value = {'requestId': str(uuid.uuid4()),
                                                   'timestamp': datetime.utcnow().isoformat()}
        callback_response = {
            'auth': {
                'purpose': 'LINK',
                'modes': [
                    'MOBILE_OTP',
                    'DEMOGRAPHICS'
                ]
            }
        }
        self._mock_callback_response_with_cache(mocked_common_request_data.return_value['requestId'],
                                                callback_response)
        request_data = self._fetch_auth_modes_sample_request_data()
        res = self.client.post(self.fetch_auth_modes_url, data=json.dumps(request_data),
                               content_type='application/json')
        self.assertEqual(res.status_code, HTTP_200_OK)
        self.assertEqual(res.json(), callback_response['auth'])

    def test_fetch_auth_modes_authentication_error(self, *args):
        client = APIClient()
        request_data = self._fetch_auth_modes_sample_request_data()
        res = client.post(self.fetch_auth_modes_url, data=json.dumps(request_data),
                          content_type='application/json')
        self.assert_for_authentication_error(res, UserAuthError.CODE_PREFIX)

    def test_fetch_auth_modes_validation_error(self, *args):
        request_data = self._fetch_auth_modes_sample_request_data()
        request_data['purpose'] = 'INVALID_CHOICE'
        res = self.client.post(self.fetch_auth_modes_url, data=json.dumps(request_data),
                               content_type='application/json')
        json_res = res.json()
        self.assertEqual(res.status_code, HTTP_400_BAD_REQUEST)
        self.assert_error(json_res['error'], int(f'{UserAuthError.CODE_PREFIX}{HTTP_400_BAD_REQUEST}'),
                          STANDARD_ERRORS.get(HTTP_400_BAD_REQUEST))
        self.assertEqual(len(json_res['error']['details']), 1)
        self.assert_error_details(json_res['error']['details'][0], ERROR_CODE_INVALID_CHOICE,
                                  ERROR_CODE_INVALID_CHOICE_MESSAGE.format(request_data['purpose']),
                                  'purpose')

    @patch('abdm_integrator.utils.requests.post')
    def test_fetch_auth_modes_gateway_error(self, mocked_post, *args):
        self.gateway_error_test(mocked_post, self.fetch_auth_modes_url,
                                self._fetch_auth_modes_sample_request_data())

    @patch('abdm_integrator.utils.requests.post', side_effect=requests.Timeout)
    def test_fetch_auth_modes_service_unavailable_error(self, *args):
        client = APIClient(raise_request_exception=False)
        client.credentials(HTTP_AUTHORIZATION=f'Token {self.token}')
        request_data = self._fetch_auth_modes_sample_request_data()
        res = client.post(self.fetch_auth_modes_url, data=json.dumps(request_data),
                          content_type='application/json')
        self.assert_for_abdm_service_unavailable_error(res, UserAuthError.CODE_PREFIX)

    @patch('abdm_integrator.user_auth.views.ABDMRequestHelper.gateway_post', return_value={})
    @patch('abdm_integrator.user_auth.views.ABDMRequestHelper.common_request_data')
    def test_auth_init_success(self, mocked_common_request_data, *args):
        mocked_common_request_data.return_value = {'requestId': str(uuid.uuid4()),
                                                   'timestamp': datetime.utcnow().isoformat()}
        callback_response = {
            'auth': {
                "transactionId": str(uuid.uuid4()),
                "mode": "MOBILE_OTP",
                "meta": {
                    "hint": None,
                    "expiry": "2023-09-13T13:52:50.385925695"
                }
            }
        }
        self._mock_callback_response_with_cache(mocked_common_request_data.return_value['requestId'],
                                                callback_response)
        request_data = self._auth_init_sample_request_data()
        res = self.client.post(self.auth_init_url, data=json.dumps(request_data),
                               content_type='application/json')
        self.assertEqual(res.status_code, HTTP_200_OK)
        self.assertEqual(res.json(), callback_response['auth'])

    def test_auth_init_authentication_error(self, *args):
        client = APIClient()
        request_data = self._auth_init_sample_request_data()
        res = client.post(self.auth_init_url, data=json.dumps(request_data),
                          content_type='application/json')
        self.assert_for_authentication_error(res, UserAuthError.CODE_PREFIX)

    def test_auth_init_validation_error(self, *args):
        request_data = self._auth_init_sample_request_data()
        del request_data['requester']['type']
        res = self.client.post(self.auth_init_url, data=json.dumps(request_data),
                               content_type='application/json')
        json_res = res.json()
        self.assertEqual(res.status_code, HTTP_400_BAD_REQUEST)
        self.assert_error(json_res['error'], int(f'{UserAuthError.CODE_PREFIX}{HTTP_400_BAD_REQUEST}'),
                          STANDARD_ERRORS.get(HTTP_400_BAD_REQUEST))
        self.assertEqual(len(json_res['error']['details']), 1)
        self.assert_error_details(json_res['error']['details'][0], ERROR_CODE_REQUIRED,
                                  ERROR_CODE_REQUIRED_MESSAGE, 'requester.type')

    @patch('abdm_integrator.utils.requests.post')
    def test_auth_init_gateway_error(self, mocked_post, *args):
        self.gateway_error_test(mocked_post, self.auth_init_url, self._auth_init_sample_request_data())

    @patch('abdm_integrator.utils.requests.post', side_effect=requests.Timeout)
    def test_auth_init_service_unavailable_error(self, *args):
        client = APIClient(raise_request_exception=False)
        client.credentials(HTTP_AUTHORIZATION=f'Token {self.token}')
        request_data = self._auth_init_sample_request_data()
        res = client.post(self.auth_init_url, data=json.dumps(request_data),
                          content_type='application/json')
        self.assert_for_abdm_service_unavailable_error(res, UserAuthError.CODE_PREFIX)

    @patch('abdm_integrator.user_auth.views.ABDMRequestHelper.gateway_post', return_value={})
    @patch('abdm_integrator.user_auth.views.ABDMRequestHelper.common_request_data')
    def test_auth_confirm_success(self, mocked_common_request_data, *args):
        mocked_common_request_data.return_value = {'requestId': str(uuid.uuid4()),
                                                   'timestamp': datetime.utcnow().isoformat()}
        callback_response = {
            'auth': {
                'accessToken': 'yajapsfycnallad',
                'patient': None
            }
        }
        self._mock_callback_response_with_cache(mocked_common_request_data.return_value['requestId'],
                                                callback_response)
        request_data = self._auth_confirm_sample_request_data()
        res = self.client.post(self.auth_confirm_url, data=json.dumps(request_data),
                               content_type='application/json')
        self.assertEqual(res.status_code, HTTP_200_OK)
        self.assertEqual(res.json(), callback_response['auth'])

    def test_auth_confirm_authentication_error(self, *args):
        client = APIClient()
        request_data = self._auth_confirm_sample_request_data()
        res = client.post(self.auth_confirm_url, data=json.dumps(request_data),
                          content_type='application/json')
        self.assert_for_authentication_error(res, UserAuthError.CODE_PREFIX)

    def test_auth_confirm_validation_error(self, *args):
        request_data = self._auth_confirm_sample_request_data()
        del request_data['transactionId']
        res = self.client.post(self.auth_confirm_url, data=json.dumps(request_data),
                               content_type='application/json')
        json_res = res.json()
        self.assertEqual(res.status_code, HTTP_400_BAD_REQUEST)
        self.assert_error(json_res['error'], int(f'{UserAuthError.CODE_PREFIX}{HTTP_400_BAD_REQUEST}'),
                          STANDARD_ERRORS.get(HTTP_400_BAD_REQUEST))
        self.assertEqual(len(json_res['error']['details']), 1)
        self.assert_error_details(json_res['error']['details'][0], ERROR_CODE_REQUIRED,
                                  ERROR_CODE_REQUIRED_MESSAGE, 'transactionId')

    @patch('abdm_integrator.utils.requests.post')
    def test_auth_confirm_gateway_error(self, mocked_post, *args):
        self.gateway_error_test(mocked_post, self.auth_confirm_url, self._auth_confirm_sample_request_data())

    @patch('abdm_integrator.utils.requests.post', side_effect=requests.Timeout)
    def test_auth_confirm_service_unavailable_error(self, *args):
        client = APIClient(raise_request_exception=False)
        client.credentials(HTTP_AUTHORIZATION=f'Token {self.token}')
        request_data = self._auth_confirm_sample_request_data()
        res = client.post(self.auth_confirm_url, data=json.dumps(request_data),
                          content_type='application/json')
        self.assert_for_abdm_service_unavailable_error(res, UserAuthError.CODE_PREFIX)
