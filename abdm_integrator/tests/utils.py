from unittest.mock import Mock

import requests
from rest_framework.exceptions import NotAuthenticated
from rest_framework.status import HTTP_200_OK

from abdm_integrator.exceptions import STANDARD_ERRORS, ABDMServiceUnavailable


class ErrorResponseAssertMixin:
    """Helper mixin for APITestCase to assert error response from API """

    def assert_error(self, actual_error, expected_code, expected_message):
        self.assertEqual(actual_error['code'], expected_code)
        self.assertEqual(actual_error['message'], expected_message)

    def assert_error_details(self, actual_error_details, expected_code, expected_detail, expected_attr):
        self.assertEqual(actual_error_details['code'], expected_code)
        self.assertEqual(actual_error_details['detail'], expected_detail)
        self.assertEqual(actual_error_details['attr'], expected_attr)

    def assert_for_authentication_error(self, response, error_code_prefix):
        json_res = response.json()
        self.assertEqual(response.status_code, NotAuthenticated.status_code)
        self.assert_error(json_res['error'], int(f'{error_code_prefix}{NotAuthenticated.status_code}'),
                          STANDARD_ERRORS.get(NotAuthenticated.status_code))
        self.assert_error_details(json_res['error']['details'][0], NotAuthenticated.default_code,
                                  NotAuthenticated.default_detail, None)

    def assert_for_abdm_service_unavailable_error(self, response, error_code_prefix):
        json_res = response.json()
        self.assertEqual(response.status_code, ABDMServiceUnavailable.status_code)
        self.assert_error(json_res['error'], int(f'{error_code_prefix}{ABDMServiceUnavailable.status_code}'),
                          STANDARD_ERRORS.get(ABDMServiceUnavailable.status_code))
        self.assert_error_details(json_res['error']['details'][0], ABDMServiceUnavailable.default_code,
                                  ABDMServiceUnavailable.default_detail, None)


def generate_mock_response(status_code=HTTP_200_OK, json_response=None):
    mock_response = requests.Response()
    mock_response.status_code = status_code
    mock_response.json = Mock(return_value=json_response)
    mock_response.headers = {'content-type': 'application/json'}
    return mock_response
