import json
import uuid
from datetime import datetime
from unittest.mock import patch

import requests
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST
from rest_framework.test import APIClient, APITestCase

from abdm_integrator.const import LinkRequestStatus
from abdm_integrator.exceptions import (
    ERROR_CODE_INVALID,
    ERROR_CODE_REQUIRED,
    ERROR_CODE_REQUIRED_MESSAGE,
    STANDARD_ERRORS,
)
from abdm_integrator.hip.exceptions import HIPError
from abdm_integrator.hip.models import LinkCareContext, LinkRequest
from abdm_integrator.tests.utils import APITestHelperMixin
from abdm_integrator.utils import ABDMCache


class TestHIPLinkCareContextAPI(APITestCase, APITestHelperMixin):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_superuser(username='test_user', password='test')
        cls.token = Token.objects.create(user=cls.user)
        cls.link_care_context_url = reverse('link_care_context')

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token}')

    def tearDown(self):
        LinkCareContext.objects.all().delete()
        LinkRequest.objects.all().delete()

    @classmethod
    def tearDownClass(cls):
        User.objects.all().delete()
        super().tearDownClass()

    @staticmethod
    def _link_care_context_sample_request_data():
        return {
            'accessToken': 'abcdefghi',
            'hip_id': '1001',
            'patient': {
                'referenceNumber': 'Test_001',
                'display': 'Test User',
                'careContexts': [
                    {
                        'referenceNumber': str(uuid.uuid4()),
                        'display': 'Made a Test Visit',
                        'hiTypes': [
                            'Prescription', 'WellnessRecord'
                        ]
                    }
                ]
            }
        }

    @staticmethod
    def _insert_link_request(request_data, user, gateway_request_id):
        link_request = LinkRequest.objects.create(user=user,
                                                  gateway_request_id=gateway_request_id,
                                                  hip_id=request_data['hip_id'],
                                                  patient_reference=request_data['patient']['referenceNumber'],
                                                  status=LinkRequestStatus.SUCCESS
                                                  )
        for care_context in request_data['patient']['careContexts']:
            LinkCareContext.objects.create(care_context_number=care_context['referenceNumber'],
                                           health_info_types=care_context['hiTypes'],
                                           link_request=link_request)

    @staticmethod
    def _mock_callback_response_with_cache(gateway_request_id, response_data):
        mocked_callback_response = {
            'requestId': str(uuid.uuid4()),
            'timestamp': datetime.utcnow().isoformat(),
            'error': None,
            'resp': {
                'requestId': gateway_request_id
            }
        }
        mocked_callback_response.update(response_data)
        ABDMCache.set(gateway_request_id, mocked_callback_response, 10)

    @patch('abdm_integrator.hip.views.care_contexts.ABDMRequestHelper.gateway_post', return_value={})
    @patch('abdm_integrator.hip.views.care_contexts.ABDMRequestHelper.common_request_data')
    def test_link_care_context_success(self, mocked_common_request_data, *args):
        mocked_common_request_data.return_value = {'requestId': str(uuid.uuid4()),
                                                   'timestamp': datetime.utcnow().isoformat()}
        callback_response = {
            'acknowledgement': {
                'status': 'SUCCESS'
            }
        }
        self._mock_callback_response_with_cache(mocked_common_request_data.return_value['requestId'],
                                                callback_response)
        request_data = self._link_care_context_sample_request_data()
        res = self.client.post(self.link_care_context_url, data=json.dumps(request_data),
                               content_type='application/json')
        self.assertEqual(res.status_code, HTTP_200_OK)
        self.assertEqual(res.json(), callback_response['acknowledgement'])
        self.assertEqual(LinkRequest.objects.all().count(), 1)
        self.assertEqual(LinkCareContext.objects.all().count(), 1)
        linked_request = LinkRequest.objects.all()[0]
        self.assertEqual(linked_request.patient_reference, request_data['patient']['referenceNumber'])
        self.assertEqual(linked_request.hip_id, request_data['hip_id'])
        self.assertEqual(str(linked_request.gateway_request_id),
                         mocked_common_request_data.return_value['requestId'])
        linked_care_context = LinkCareContext.objects.all()[0]
        self.assertEqual(linked_care_context.care_context_number,
                         request_data['patient']['careContexts'][0]['referenceNumber'])
        self.assertEqual(linked_care_context.link_request, linked_request)
        self.assertEqual(linked_care_context.health_info_types,
                         request_data['patient']['careContexts'][0]['hiTypes'])

    def test_link_care_context_authentication_error(self, *args):
        client = APIClient()
        request_data = self._link_care_context_sample_request_data()
        res = client.post(self.link_care_context_url, data=json.dumps(request_data),
                          content_type='application/json')
        self.assert_for_authentication_error(res, HIPError.CODE_PREFIX)
        self.assertEqual(LinkRequest.objects.all().count(), 0)
        self.assertEqual(LinkCareContext.objects.all().count(), 0)

    def test_link_care_context_validation_error(self, *args):
        request_data = self._link_care_context_sample_request_data()
        del request_data['patient']['referenceNumber']
        res = self.client.post(self.link_care_context_url, data=json.dumps(request_data),
                               content_type='application/json')
        json_res = res.json()
        self.assertEqual(res.status_code, HTTP_400_BAD_REQUEST)
        self.assert_error(json_res['error'], int(f'{HIPError.CODE_PREFIX}{HTTP_400_BAD_REQUEST}'),
                          STANDARD_ERRORS.get(HTTP_400_BAD_REQUEST))
        self.assertEqual(len(json_res['error']['details']), 1)
        self.assert_error_details(json_res['error']['details'][0], ERROR_CODE_REQUIRED,
                                  ERROR_CODE_REQUIRED_MESSAGE, 'patient.referenceNumber')
        self.assertEqual(LinkRequest.objects.all().count(), 0)
        self.assertEqual(LinkCareContext.objects.all().count(), 0)

    @patch('abdm_integrator.hip.views.care_contexts.ABDMRequestHelper.common_request_data')
    def test_link_care_context_already_linked(self, mocked_common_request_data, *args):
        mocked_common_request_data.return_value = {'requestId': str(uuid.uuid4()),
                                                   'timestamp': datetime.utcnow().isoformat()}
        request_data = self._link_care_context_sample_request_data()
        self._insert_link_request(request_data, self.user, mocked_common_request_data.return_value['requestId'])
        res = self.client.post(self.link_care_context_url, data=json.dumps(request_data),
                               content_type='application/json')
        json_res = res.json()
        self.assertEqual(res.status_code, HTTP_400_BAD_REQUEST)
        expected_error_code = HIPError.CODE_CARE_CONTEXT_ALREADY_LINKED
        expected_error_message = HIPError.CUSTOM_ERRORS[expected_error_code].format(
            [request_data['patient']['careContexts'][0]['referenceNumber']])
        self.assert_error(json_res['error'], expected_error_code, expected_error_message)
        self.assertEqual(len(json_res['error']['details']), 1)
        self.assert_error_details(json_res['error']['details'][0], ERROR_CODE_INVALID,
                                  expected_error_message, None)
        self.assertEqual(LinkRequest.objects.all().count(), 1)
        self.assertEqual(LinkCareContext.objects.all().count(), 1)

    @patch('abdm_integrator.utils.requests.post')
    def test_link_care_context_gateway_error(self, mocked_post, *args):
        self.gateway_error_test(mocked_post, self.link_care_context_url,
                                self._link_care_context_sample_request_data())
        self.assertEqual(LinkRequest.objects.all().count(), 0)
        self.assertEqual(LinkCareContext.objects.all().count(), 0)

    @patch('abdm_integrator.utils.requests.post', side_effect=requests.Timeout)
    def test_link_care_context_service_unavailable_error(self, *args):
        client = APIClient(raise_request_exception=False)
        client.credentials(HTTP_AUTHORIZATION=f'Token {self.token}')
        request_data = self._link_care_context_sample_request_data()
        res = client.post(self.link_care_context_url, data=json.dumps(request_data),
                          content_type='application/json')
        self.assert_for_abdm_service_unavailable_error(res, HIPError.CODE_PREFIX)
        self.assertEqual(LinkRequest.objects.all().count(), 0)
        self.assertEqual(LinkCareContext.objects.all().count(), 0)
