from datetime import datetime
from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase

from abdm_integrator.exceptions import ABDMGatewayError
from abdm_integrator.utils import (
    ABDMCache,
    ABDMRequestHelper,
    abdm_iso_to_datetime,
    datetime_to_abdm_iso,
    poll_and_pop_data_from_cache,
    removes_prefix_for_abdm_mobile,
)


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
        with self.assertRaises(ABDMGatewayError):
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
        with self.assertRaises(ABDMGatewayError):
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


class TestUtils(SimpleTestCase):

    def test_poll_data_present_in_cache(self):
        ABDMCache.set('test_1', 101, 10)
        data = poll_and_pop_data_from_cache('test_1', 2, 0.1)
        self.assertEqual(data, 101)

    def test_poll_data_absent_in_cache(self):
        data = poll_and_pop_data_from_cache('test_2', 2, 0.1)
        self.assertIsNone(data)

    def test_removes_prefix_for_abdm_mobile(self):
        self.assertEqual(removes_prefix_for_abdm_mobile('+91-9988776655'), '9988776655')
        self.assertEqual(removes_prefix_for_abdm_mobile('+919988776655'), '9988776655')
        self.assertEqual(removes_prefix_for_abdm_mobile('9988776655'), '9988776655')

    def test_datetime_to_abdm_iso(self):
        date1 = datetime(year=2023, month=1, day=1, hour=1, minute=1, second=1, microsecond=123456)
        date2 = datetime(year=2023, month=1, day=1, hour=1, minute=1, second=1, microsecond=123)
        date3 = datetime(year=2023, month=1, day=1, hour=1, minute=1, second=1)
        self.assertEqual(datetime_to_abdm_iso(date1), '2023-01-01T01:01:01.123Z')
        self.assertEqual(datetime_to_abdm_iso(date2), '2023-01-01T01:01:01.000Z')
        self.assertEqual(datetime_to_abdm_iso(date3), '2023-01-01T01:01:01.000Z')

    def test_abdm_iso_to_datetime(self):
        expected_date = datetime(year=2023, month=1, day=1, hour=1, minute=1, second=1, microsecond=123000)
        self.assertEqual(abdm_iso_to_datetime('2023-01-01T01:01:01.123Z'), expected_date)
        self.assertEqual(abdm_iso_to_datetime('2023-01-01T01:01:01.123000Z'), expected_date)
        self.assertEqual(abdm_iso_to_datetime('2023-01-01T01:01:01.123000'), expected_date)
