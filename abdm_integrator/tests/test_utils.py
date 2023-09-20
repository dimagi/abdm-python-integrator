from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase

from abdm_integrator.exceptions import ABDMGatewayError
from abdm_integrator.utils import ABDMRequestHelper


class TestABDMRequestHelper(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        cls.sample_success_json = {'test': '1001'}

    @staticmethod
    def _mock_response(status_code=200, json_response=None):
        mock_response = requests.Response()
        mock_response.status_code = status_code
        mock_response.json = Mock(return_value=json_response)
        return mock_response

    @patch('abdm_integrator.utils.requests.post')
    def test_get_access_token_success(self, mocked_post):
        mocked_post.return_value = self._mock_response(json_response={'accessToken': 'test'})
        token = ABDMRequestHelper().get_access_token()
        self.assertEqual(token, 'test')

    @patch('abdm_integrator.utils.requests.post')
    def test_get_access_token_failure(self, mocked_post):
        mocked_post.return_value = self._mock_response(status_code=400)
        with self.assertRaises(ABDMGatewayError):
            ABDMRequestHelper().get_access_token()

    @patch('abdm_integrator.utils.ABDMRequestHelper.get_access_token')
    @patch('abdm_integrator.utils.requests.get')
    def test_abha_get_success(self, mocked_get, *args):
        mocked_get.return_value = self._mock_response(json_response=self.sample_success_json)
        actual_json_resp = ABDMRequestHelper().abha_get(api_path='')
        self.assertEqual(actual_json_resp, self.sample_success_json)

    @patch('abdm_integrator.utils.ABDMRequestHelper.get_access_token')
    @patch('abdm_integrator.utils.requests.get')
    def test_abha_get_failure(self, mocked_get,  *args):
        mocked_get.return_value = self._mock_response(status_code=400)
        with self.assertRaises(requests.HTTPError):
            ABDMRequestHelper().abha_get(api_path='')

    @patch('abdm_integrator.utils.ABDMRequestHelper.get_access_token')
    @patch('abdm_integrator.utils.requests.post')
    def test_abha_post_success(self, mocked_post, *args):
        mocked_post.return_value = self._mock_response(json_response=self.sample_success_json)
        actual_json_resp = ABDMRequestHelper().abha_post(api_path='', payload={})
        self.assertEqual(actual_json_resp, self.sample_success_json)

    @patch('abdm_integrator.utils.ABDMRequestHelper.get_access_token')
    @patch('abdm_integrator.utils.requests.post')
    def test_abha_post_failure(self, mocked_post, *args):
        mocked_post.return_value = self._mock_response(status_code=400)
        with self.assertRaises(requests.HTTPError):
            ABDMRequestHelper().abha_post(api_path='', payload={})

    @patch('abdm_integrator.utils.ABDMRequestHelper.get_access_token')
    @patch('abdm_integrator.utils.requests.post')
    def test_gateway_post_success(self, mocked_post, *args):
        mock_response = self._mock_response(json_response=self.sample_success_json)
        mock_response.headers = {'content-type': 'application/json'}
        mocked_post.return_value = mock_response
        actual_json_resp = ABDMRequestHelper().gateway_post(api_path='', payload={})
        self.assertEqual(actual_json_resp, self.sample_success_json)

    @patch('abdm_integrator.utils.ABDMRequestHelper.get_access_token')
    @patch('abdm_integrator.utils.requests.post')
    def test_gateway_post_failure(self, mocked_post, *args):
        mocked_post.return_value = self._mock_response(status_code=400)
        with self.assertRaises(ABDMGatewayError):
            ABDMRequestHelper().gateway_post(api_path='', payload={})
