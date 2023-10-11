from unittest.mock import patch

from django.test.utils import override_settings
from django.urls import path
from rest_framework import serializers
from rest_framework.exceptions import NotAuthenticated, NotFound
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.test import APIClient, APITestCase
from rest_framework.views import APIView

from abdm_integrator.exceptions import (
    ERROR_CODE_INVALID,
    ERROR_CODE_REQUIRED_MESSAGE,
    STANDARD_ERRORS,
    ABDMGatewayError,
    ABDMServiceUnavailable,
    APIErrorResponseHandler,
    CustomError,
)
from abdm_integrator.settings import app_settings
from abdm_integrator.tests.utils import APITestHelperMixin

TEST_ERROR_CODE_PREFIX = '9'
TEST_CUSTOM_ERRORS = {
    9407: "A custom error occurred",
}

test_error_handler = APIErrorResponseHandler(TEST_ERROR_CODE_PREFIX, TEST_CUSTOM_ERRORS)


class TestAPIView(APIView):
    authentication_classes = [app_settings.AUTHENTICATION_CLASS]

    def get_exception_handler(self):
        return test_error_handler.get_exception_handler()

    def post(self, request, format=None):
        return Response({})


urlpatterns = [
    path('test', TestAPIView.as_view(), name='test_view'),
]


@override_settings(
    ROOT_URLCONF='abdm_integrator.tests.test_exceptions',
    DRF_STANDARDIZED_ERRORS={
        "ENABLE_IN_DEBUG_FOR_UNHANDLED_EXCEPTIONS": True
    },
)
class TestAPIErrors(APITestCase, APITestHelperMixin):
    """Test that the error response obtained from ABDM APIs matches the desired format"""

    @patch('abdm_integrator.tests.test_exceptions.TestAPIView.post',
           side_effect=serializers.ValidationError({'field1': ERROR_CODE_REQUIRED_MESSAGE}))
    def test_400_error(self, mocked_object):
        res = self.client.post(reverse('test_view'))
        json_resp = res.json()
        self.assertEqual(res.status_code, 400)
        self.assert_error(json_resp['error'], int(f'{TEST_ERROR_CODE_PREFIX}400'), STANDARD_ERRORS.get(400))
        self.assert_error_details(json_resp['error']['details'][0], ERROR_CODE_INVALID,
                                  ERROR_CODE_REQUIRED_MESSAGE, 'field1')

    @patch('abdm_integrator.tests.test_exceptions.TestAPIView.post', side_effect=NotAuthenticated)
    def test_401_error(self, mocked_object):
        res = self.client.post(reverse('test_view'))
        self.assert_for_authentication_error(res, TEST_ERROR_CODE_PREFIX)

    @patch('abdm_integrator.tests.test_exceptions.TestAPIView.post', side_effect=NotFound)
    def test_404_error(self, mocked_object):
        res = self.client.post(reverse('test_view'))
        json_resp = res.json()
        self.assertEqual(res.status_code, 404)
        self.assert_error(json_resp['error'], int(f'{TEST_ERROR_CODE_PREFIX}404'), STANDARD_ERRORS.get(404))
        self.assert_error_details(json_resp['error']['details'][0], NotFound.default_code,
                                  NotFound.default_detail, None)

    @patch('abdm_integrator.tests.test_exceptions.TestAPIView.post',
           side_effect=Exception('Unhandled error'))
    def test_500_error(self, mocked_object):
        # Test Client catches unhandled error signal sent by drf_standardized_exception_handler and re raises it.
        client = APIClient(raise_request_exception=False)
        res = client.post(reverse('test_view'))
        json_resp = res.json()
        self.assertEqual(res.status_code, 500)
        self.assert_error(json_resp['error'], int(f'{TEST_ERROR_CODE_PREFIX}500'), STANDARD_ERRORS.get(500))
        self.assertIsNone(json_resp['error'].get('details'))

    @patch('abdm_integrator.tests.test_exceptions.TestAPIView.post', side_effect=ABDMServiceUnavailable)
    def test_abdm_service_unavailable_error(self, mocked_object):
        # Test Client catches unhandled error signal sent by drf_standardized_exception_handler and re raises it.
        client = APIClient(raise_request_exception=False)
        res = client.post(reverse('test_view'))
        self.assert_for_abdm_service_unavailable_error(res, TEST_ERROR_CODE_PREFIX)

    @patch('abdm_integrator.tests.test_exceptions.TestAPIView.post')
    def test_abdm_gateway_error(self, mocked_object):
        gateway_error = {'code': 1400, 'message': 'abha id not found.'}
        mocked_object.side_effect = ABDMGatewayError(error_code=gateway_error['code'],
                                                     detail_message=gateway_error['message'])
        res = self.client.post(reverse('test_view'))
        json_resp = res.json()
        self.assertEqual(res.status_code, ABDMGatewayError.status_code)
        self.assert_error(json_resp['error'], gateway_error['code'], ABDMGatewayError.error_message)
        self.assert_error_details(json_resp['error']['details'][0], ABDMGatewayError.detail_code,
                                  gateway_error['message'], None)

    @patch('abdm_integrator.tests.test_exceptions.TestAPIView.post')
    def test_abdm_custom_error(self, mocked_object):
        custom_error = {'status': 407, 'code': 9407, 'details_message': 'Custom error', 'details_attr': 'patient'}
        mocked_object.side_effect = CustomError(status_code=custom_error['status'],
                                                error_code=custom_error['code'],
                                                error_message=TEST_CUSTOM_ERRORS.get(custom_error['code']),
                                                detail_message=custom_error['details_message'],
                                                detail_attr=custom_error['details_attr'])
        res = self.client.post(reverse('test_view'))
        json_resp = res.json()
        self.assertEqual(res.status_code, custom_error['status'])
        self.assert_error(json_resp['error'], custom_error['code'], TEST_CUSTOM_ERRORS.get(custom_error['code']))
        self.assert_error_details(json_resp['error']['details'][0], ERROR_CODE_INVALID,
                                  custom_error['details_message'], custom_error['details_attr'])
