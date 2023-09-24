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
    GATEWAY_ERROR_DETAIL_CODE,
    GATEWAY_ERROR_MESSAGE,
    GATEWAY_ERROR_STATUS,
    STANDARD_ERRORS,
    ABDMGatewayError,
    ABDMServiceUnavailable,
    APIErrorResponseHandler,
    CustomError,
)
from abdm_integrator.settings import app_settings

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
class TestAPIErrors(APITestCase):
    """Test that the error response obtained from ABDM APIs matches the desired format"""

    @patch('abdm_integrator.tests.test_exceptions.TestAPIView.post',
           side_effect=serializers.ValidationError({'field1': 'This is required.'}))
    def test_400_error(self, mocked_object):
        res = self.client.post(reverse('test_view'))
        json_resp = res.json()
        self.assertEqual(res.status_code, 400)
        self.assertEqual(json_resp['error']['code'], 9400)
        self.assertEqual(json_resp['error']['message'], STANDARD_ERRORS.get(400))
        self.assertEqual(json_resp['error']['details'][0],
                         {'code': 'invalid', 'detail': 'This is required.', 'attr': 'field1'})

    @patch('abdm_integrator.tests.test_exceptions.TestAPIView.post', side_effect=NotAuthenticated)
    def test_401_error(self, mocked_object):
        res = self.client.post(reverse('test_view'))
        json_resp = res.json()
        self.assertEqual(res.status_code, 401)
        self.assertEqual(json_resp['error']['code'], 9401)
        self.assertEqual(json_resp['error']['message'], STANDARD_ERRORS.get(401))
        self.assertEqual(json_resp['error']['details'][0],
                         {'code': 'not_authenticated',
                          'detail': 'Authentication credentials were not provided.', 'attr': None})

    @patch('abdm_integrator.tests.test_exceptions.TestAPIView.post', side_effect=NotFound)
    def test_404_error(self, mocked_object):
        res = self.client.post(reverse('test_view'))
        json_resp = res.json()
        self.assertEqual(res.status_code, 404)
        self.assertEqual(json_resp['error']['code'], 9404)
        self.assertEqual(json_resp['error']['message'], STANDARD_ERRORS.get(404))
        self.assertEqual(json_resp['error']['details'][0],
                         {'code': 'not_found', 'detail': 'Not found.', 'attr': None})

    @patch('abdm_integrator.tests.test_exceptions.TestAPIView.post',
           side_effect=Exception('Unhandled error'))
    def test_500_error(self, mocked_object):
        # Test Client catches unhandled error signal sent by drf_standardized_exception_handler and re raises it.
        client = APIClient(raise_request_exception=False)
        res = client.post(reverse('test_view'))
        json_resp = res.json()
        self.assertEqual(res.status_code, 500)
        self.assertEqual(json_resp['error']['code'], 9500)
        self.assertEqual(json_resp['error']['message'], STANDARD_ERRORS.get(500))
        self.assertIsNone(json_resp['error'].get('details'))

    @patch('abdm_integrator.tests.test_exceptions.TestAPIView.post', side_effect=ABDMServiceUnavailable)
    def test_abdm_service_unavailable_error(self, mocked_object):
        # Test Client catches unhandled error signal sent by drf_standardized_exception_handler and re raises it.
        client = APIClient(raise_request_exception=False)
        res = client.post(reverse('test_view'))
        json_resp = res.json()
        self.assertEqual(res.status_code, ABDMServiceUnavailable.status_code)
        self.assertEqual(json_resp['error']['code'], 9503)
        self.assertEqual(json_resp['error']['message'], STANDARD_ERRORS.get(503))
        self.assertEqual(json_resp['error']['details'][0],
                         {'code': ABDMServiceUnavailable.default_code,
                          'detail': ABDMServiceUnavailable.default_detail, 'attr': None})

    @patch('abdm_integrator.tests.test_exceptions.TestAPIView.post')
    def test_abdm_gateway_error(self, mocked_object):
        gateway_error = {'code': 1400, 'message': 'abha id not found.'}
        mocked_object.side_effect = ABDMGatewayError(error_code=gateway_error['code'],
                                                     detail_message=gateway_error['message'])
        res = self.client.post(reverse('test_view'))
        json_resp = res.json()
        self.assertEqual(res.status_code, GATEWAY_ERROR_STATUS)
        self.assertEqual(json_resp['error']['code'], gateway_error['code'])
        self.assertEqual(json_resp['error']['message'], GATEWAY_ERROR_MESSAGE)
        self.assertEqual(json_resp['error']['details'][0],
                         {'code': GATEWAY_ERROR_DETAIL_CODE, 'detail': gateway_error['message'], 'attr': None})

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
        self.assertEqual(json_resp['error']['code'], custom_error['code'])
        self.assertEqual(json_resp['error']['message'], TEST_CUSTOM_ERRORS.get(custom_error['code']))
        self.assertEqual(res.status_code, custom_error['status'])
        self.assertEqual(json_resp['error']['details'][0],
                         {'code': ERROR_CODE_INVALID, 'detail': custom_error['details_message'],
                          'attr': custom_error['details_attr']})
