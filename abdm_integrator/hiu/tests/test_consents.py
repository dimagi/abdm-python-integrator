import json
import os
from copy import deepcopy
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import requests
from django.contrib.auth.models import User
from rest_framework.exceptions import NotAuthenticated
from rest_framework.reverse import reverse
from rest_framework.status import HTTP_200_OK, HTTP_201_CREATED, HTTP_400_BAD_REQUEST
from rest_framework.test import APIClient, APITestCase

from abdm_integrator.const import ConsentStatus
from abdm_integrator.exceptions import (
    ERROR_CODE_INVALID,
    ERROR_CODE_REQUIRED,
    ERROR_CODE_REQUIRED_MESSAGE,
    ERROR_FUTURE_DATE_MESSAGE,
    STANDARD_ERRORS,
    ABDMGatewayError,
    ABDMServiceUnavailable,
)
from abdm_integrator.hiu.exceptions import HIUError
from abdm_integrator.hiu.models import ConsentRequest
from abdm_integrator.utils import abdm_iso_to_datetime, json_from_file


class TestGenerateConsentRequestAPI(APITestCase):
    dir_path = os.path.dirname(os.path.abspath(__file__))
    consent_sample_json_path = os.path.join(dir_path, 'data/generate_consent_request_sample.json')

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_superuser(username='test_user', password='test')
        cls.consent_request_sample = json_from_file(cls.consent_sample_json_path)

    def setUp(self):
        self.client.force_authenticate(user=self.user)

    def tearDown(self):
        ConsentRequest.objects.all().delete()

    @classmethod
    def tearDownClass(cls):
        User.objects.all().delete()
        super().tearDownClass()

    @staticmethod
    def _mock_response(status_code=HTTP_200_OK, json_response=None):
        mock_response = requests.Response()
        mock_response.status_code = status_code
        mock_response.json = Mock(return_value=json_response)
        mock_response.headers = {'content-type': 'application/json'}
        return mock_response

    def _assert_error(self, actual_error, expected_code, expected_message):
        self.assertEqual(actual_error['code'], expected_code)
        self.assertEqual(actual_error['message'], expected_message)

    def _assert_error_details(self, actual_error_details, expected_code, expected_detail, expected_attr):
        self.assertEqual(actual_error_details['code'], expected_code)
        self.assertEqual(actual_error_details['detail'], expected_detail)
        self.assertEqual(actual_error_details['attr'], expected_attr)

    @classmethod
    def _sample_generate_consent_data(cls):
        consent_data = deepcopy(cls.consent_request_sample)
        consent_data['permission']['dataEraseAt'] = (datetime.utcnow() + timedelta(days=1)).isoformat()
        return consent_data

    @patch('abdm_integrator.utils.ABDMRequestHelper.gateway_post', return_value={})
    @patch('abdm_integrator.utils.ABDMRequestHelper.abha_post', return_value={'status': True})
    def test_generate_consent_request_success(self, *args):
        request_data = self._sample_generate_consent_data()
        res = self.client.post(reverse('generate_consent_request'), data=json.dumps(request_data),
                               content_type='application/json')
        self.assertEqual(res.status_code, HTTP_201_CREATED)
        self.assertEqual(ConsentRequest.objects.all().count(), 1)
        consent_request = ConsentRequest.objects.get(id=res.json()['id'])
        self.assertEqual(consent_request.status, ConsentStatus.PENDING)
        self.assertEqual(consent_request.health_info_from_date,
                         abdm_iso_to_datetime(request_data['permission']['dateRange']['from']))
        self.assertEqual(consent_request.health_info_to_date,
                         abdm_iso_to_datetime(request_data['permission']['dateRange']['to']))
        self.assertEqual(consent_request.expiry_date,
                         abdm_iso_to_datetime(request_data['permission']['dataEraseAt']))
        self.assertEqual(consent_request.health_info_types, request_data['hiTypes'])
        self.assertEqual(consent_request.user, self.user)

    def test_generate_consent_request_authentication_error(self, *args):
        client = APIClient()
        request_data = self._sample_generate_consent_data()
        res = client.post(reverse('generate_consent_request'), data=json.dumps(request_data),
                          content_type='application/json')
        json_res = res.json()
        self.assertEqual(res.status_code, NotAuthenticated.status_code)
        self._assert_error(json_res['error'], int(f'{HIUError.CODE_PREFIX}{NotAuthenticated.status_code}'),
                           STANDARD_ERRORS.get(NotAuthenticated.status_code))
        self._assert_error_details(json_res['error']['details'][0], NotAuthenticated.default_code,
                                   NotAuthenticated.default_detail, None)
        self.assertEqual(ConsentRequest.objects.all().count(), 0)

    def test_generate_consent_request_validation_error(self, *args):
        request_data = self._sample_generate_consent_data()
        request_data['patient'] = {}
        request_data['permission']['dataEraseAt'] = (datetime.utcnow() - timedelta(days=1)).isoformat()
        res = self.client.post(reverse('generate_consent_request'), data=json.dumps(request_data),
                               content_type='application/json')
        json_res = res.json()
        self.assertEqual(res.status_code, HTTP_400_BAD_REQUEST)
        self._assert_error(json_res['error'], int(f'{HIUError.CODE_PREFIX}{HTTP_400_BAD_REQUEST}'),
                           STANDARD_ERRORS.get(HTTP_400_BAD_REQUEST))
        self.assertEqual(len(json_res['error']['details']), 2)
        self._assert_error_details(json_res['error']['details'][0], ERROR_CODE_REQUIRED,
                                   ERROR_CODE_REQUIRED_MESSAGE, 'patient.id')
        self._assert_error_details(json_res['error']['details'][1], ERROR_CODE_INVALID,
                                   ERROR_FUTURE_DATE_MESSAGE, 'permission.dataEraseAt')
        self.assertEqual(ConsentRequest.objects.all().count(), 0)

    @patch('abdm_integrator.utils.ABDMRequestHelper.abha_post', return_value={'status': False})
    def test_generate_consent_request_patient_not_found(self, *args):
        request_data = self._sample_generate_consent_data()
        res = self.client.post(reverse('generate_consent_request'), data=json.dumps(request_data),
                               content_type='application/json')
        self.assertEqual(res.status_code, HTTP_400_BAD_REQUEST)
        json_res = res.json()
        self._assert_error(json_res['error'], HIUError.CODE_PATIENT_NOT_FOUND,
                           HIUError.CUSTOM_ERRORS[HIUError.CODE_PATIENT_NOT_FOUND])
        self._assert_error_details(json_res['error']['details'][0], ERROR_CODE_INVALID,
                                   HIUError.CUSTOM_ERRORS[HIUError.CODE_PATIENT_NOT_FOUND], 'patient.id')
        self.assertEqual(ConsentRequest.objects.all().count(), 0)

    @patch('abdm_integrator.utils.requests.post')
    def test_generate_consent_request_gateway_error(self, mocked_post):
        gateway_error = {'error': {'code': 2500, 'message': 'Invalid request'}}
        mocked_post.return_value = self._mock_response(HTTP_400_BAD_REQUEST, gateway_error)
        request_data = self._sample_generate_consent_data()
        res = self.client.post(reverse('generate_consent_request'), data=json.dumps(request_data),
                               content_type='application/json')
        json_res = res.json()
        self.assertEqual(res.status_code, ABDMGatewayError.status_code)
        self._assert_error(json_res['error'], gateway_error['error']['code'], ABDMGatewayError.error_message)
        self._assert_error_details(json_res['error']['details'][0], ABDMGatewayError.detail_code,
                                   gateway_error['error']['message'], None)
        self.assertEqual(ConsentRequest.objects.all().count(), 0)

    @patch('abdm_integrator.utils.requests.post', side_effect=requests.Timeout)
    def test_generate_consent_request_service_unavailable_error(self, mocked_post):
        client = APIClient(raise_request_exception=False)
        client.force_authenticate(self.user)
        request_data = self._sample_generate_consent_data()
        res = client.post(reverse('generate_consent_request'), data=json.dumps(request_data),
                          content_type='application/json')
        json_res = res.json()
        self.assertEqual(res.status_code, ABDMServiceUnavailable.status_code)
        self._assert_error(json_res['error'], int(f'{HIUError.CODE_PREFIX}{ABDMServiceUnavailable.status_code}'),
                           STANDARD_ERRORS.get(ABDMServiceUnavailable.status_code))
        self._assert_error_details(json_res['error']['details'][0], ABDMServiceUnavailable.default_code,
                                   ABDMServiceUnavailable.default_detail, None)
        self.assertEqual(ConsentRequest.objects.all().count(), 0)
