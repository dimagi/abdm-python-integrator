import uuid
from copy import deepcopy
from datetime import datetime, timedelta
from unittest.mock import patch

import requests
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import NotFound
from rest_framework.reverse import reverse
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND
from rest_framework.test import APIClient, APITestCase

from abdm_integrator.const import ConsentPurpose, ConsentStatus, HealthInformationType
from abdm_integrator.exceptions import ERROR_CODE_INVALID, STANDARD_ERRORS, ABDMGatewayError
from abdm_integrator.hiu.exceptions import HIUError
from abdm_integrator.hiu.models import ConsentArtefact, ConsentRequest, HealthInformationRequest
from abdm_integrator.tests.utils import APITestHelperMixin, generate_mock_response
from abdm_integrator.utils import ABDMCache


class TestRequestHealthInformationAPI(APITestCase, APITestHelperMixin):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_superuser(username='test_user', password='test')
        cls.token = Token.objects.create(user=cls.user)
        cls.request_health_information_url = reverse('request_health_information')
        cls.consent_request_id_1 = str(uuid.uuid4())
        cls.artefact_id_1 = str(uuid.uuid4())
        cls.artefact_id_2 = str(uuid.uuid4())
        cls.patient_1 = 'test1@sbx'
        cls._add_consents_data()

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token}')

    def tearDown(self):
        HealthInformationRequest.objects.all().delete()

    @classmethod
    def tearDownClass(cls):
        ConsentArtefact.objects.all().delete()
        ConsentRequest.objects.all().delete()
        User.objects.all().delete()
        super().tearDownClass()

    @classmethod
    def _health_information_request_data(cls):
        return {'artefact_id': cls.artefact_id_1}

    @classmethod
    def _add_consents_data(cls):
        consent_data_1 = {
            'consent_request_id': cls.consent_request_id_1,
            'gateway_request_id': str(uuid.uuid4()),
            'status': ConsentStatus.GRANTED,
            'health_info_from_date': '2011-05-17T15:12:43.960000',
            'health_info_to_date': '2017-08-07T15:12:43.961000',
            'health_info_types': [
                HealthInformationType.DISCHARGE_SUMMARY,
                HealthInformationType.PRESCRIPTION,
                HealthInformationType.WELLNESS_RECORD
            ],
            'expiry_date': (datetime.utcnow() + timedelta(days=1)).isoformat(),
            'details': {
                'patient': {
                    'id': cls.patient_1
                }
            }
        }
        consent_request_1 = ConsentRequest.objects.create(**consent_data_1, user=cls.user)
        artefact_data_1 = {
            'artefact_id': cls.artefact_id_1,
            'gateway_request_id': str(uuid.uuid4()),
            'details': {
                'hip': {
                    'id': '6004',
                    'name': 'Test Eye Care Center '
                },
                'hiu': {
                    'id': 'Ashish-HIU-Registered',
                    'name': None
                },
                'hiTypes': [
                    HealthInformationType.PRESCRIPTION
                ],
                'patient': {
                    'id': cls.patient_1
                },
                'purpose': {
                    'code': ConsentPurpose.CARE_MANAGEMENT,
                    'text': 'Care Management',
                    'refUri': 'http://terminology.hl7.org/ValueSet/v3-PurposeOfUse'
                },
                'consentId': consent_data_1['consent_request_id'],
                'createdAt': datetime.utcnow().isoformat(),
                'requester': {
                    'name': 'Dr. Manju',
                    'identifier': {
                        'type': 'REGNO',
                        'value': 'MH1001',
                        'system': 'https://www.mciindia.org'
                    }
                },
                'permission': {
                    'dateRange': {
                        'to': consent_data_1['health_info_to_date'],
                        'from': consent_data_1['health_info_from_date']
                    },
                    'frequency': {
                        'unit': 'HOUR',
                        'value': 1,
                        'repeats': 0
                    },
                    'accessMode': 'VIEW',
                    'dataEraseAt': consent_data_1['expiry_date']
                },
                'careContexts': [
                    {
                        'patientReference': 'PT-101',
                        'careContextReference': 'CC-101'
                    },
                ]
            }
        }
        ConsentArtefact.objects.create(**artefact_data_1, consent_request=consent_request_1)
        consent_data_2 = deepcopy(consent_data_1)
        consent_data_2['consent_request_id'] = str(uuid.uuid4())
        consent_data_2['gateway_request_id'] = str(uuid.uuid4())
        consent_data_2['expiry_date'] = (datetime.utcnow() - timedelta(days=1)).isoformat()
        artefact_data_2 = deepcopy(artefact_data_1)
        artefact_data_2['artefact_id'] = cls.artefact_id_2
        artefact_data_2['gateway_request_id'] = str(uuid.uuid4())
        artefact_data_2['details']['consentId'] = consent_data_2['consent_request_id']
        artefact_data_2['details']['permission']['dataEraseAt'] = consent_data_2['expiry_date']
        consent_request_2 = ConsentRequest.objects.create(**consent_data_2, user=cls.user)
        ConsentArtefact.objects.create(**artefact_data_2, consent_request=consent_request_2)

    def _health_info_success_response(self):
        return {
            'page': 1,
            'page_count': 1,
            'transaction_id': '66a82e5e-0685-45a3-8993-8c729698b747',
            'entries': [
                {
                    'content': {'test': 1},
                    'care_context_reference': 'CC-101'
                }
            ],
        }

    @patch('abdm_integrator.hiu.views.health_information.ABDMRequestHelper.gateway_post')
    @patch('abdm_integrator.hiu.views.health_information.ABDMRequestHelper.common_request_data')
    def test_request_health_information_success(self, mocked_common_request_data, *args):
        mocked_common_request_data.return_value = {
            'requestId': str(uuid.uuid4()),
            'timestamp': datetime.utcnow().isoformat()
        }
        gateway_request_id = mocked_common_request_data.return_value['requestId']
        mocked_response_cache = self._health_info_success_response()
        ABDMCache.set(f"{gateway_request_id}_1", mocked_response_cache, 10)

        res = self.client.get(self.request_health_information_url, data=self._health_information_request_data())

        self.assertEqual(res.status_code, HTTP_200_OK)
        json_res = res.json()
        self.assertEqual(json_res['transaction_id'], mocked_response_cache['transaction_id'])
        self.assertEqual(json_res['page'], mocked_response_cache['page'])
        self.assertEqual(json_res['page_count'], mocked_response_cache['page_count'])
        self.assertIsNone(json_res['next'])
        self.assertEqual(json_res['results'], mocked_response_cache['entries'])
        self.assertEqual(HealthInformationRequest.objects.count(), 1)
        health_information_request = HealthInformationRequest.objects.get(gateway_request_id=gateway_request_id)
        self.assertIsNone(health_information_request.error)
        self.assertIsNotNone(health_information_request.key_material)
        self.assertEqual(str(health_information_request.consent_artefact.artefact_id), self.artefact_id_1)

    @patch('abdm_integrator.hiu.views.health_information.ABDMRequestHelper.gateway_post')
    @patch('abdm_integrator.hiu.views.health_information.app_settings.HIU_PARSE_FHIR_BUNDLE', return_value=True)
    @patch('abdm_integrator.hiu.views.health_information.parse_fhir_bundle')
    @patch('abdm_integrator.hiu.views.health_information.ABDMRequestHelper.common_request_data')
    def test_request_health_information_success_parsed_fhir_data(self, mocked_common_request_data,
                                                                 mocked_parse_fhir_bundle, *args):
        mocked_common_request_data.return_value = {
            'requestId': str(uuid.uuid4()),
            'timestamp': datetime.utcnow().isoformat()
        }
        mocked_parse_fhir_bundle.return_value = {
            'title': 'Prescription',
            'content': {'parsed_test': 1},
            'care_context_reference': 'CC-101'
        }
        gateway_request_id = mocked_common_request_data.return_value['requestId']
        mocked_response_cache = self._health_info_success_response()
        ABDMCache.set(f"{gateway_request_id}_1", mocked_response_cache, 10)

        res = self.client.get(self.request_health_information_url, data=self._health_information_request_data())

        self.assertEqual(res.status_code, HTTP_200_OK)
        json_res = res.json()
        self.assertEqual(json_res['transaction_id'], mocked_response_cache['transaction_id'])
        self.assertEqual(json_res['page'], mocked_response_cache['page'])
        self.assertEqual(json_res['page_count'], mocked_response_cache['page_count'])
        self.assertIsNone(json_res['next'])
        self.assertEqual(json_res['results'], [mocked_parse_fhir_bundle.return_value])
        self.assertEqual(HealthInformationRequest.objects.count(), 1)
        health_information_request = HealthInformationRequest.objects.get(gateway_request_id=gateway_request_id)
        self.assertIsNone(health_information_request.error)
        self.assertIsNotNone(health_information_request.key_material)
        self.assertEqual(str(health_information_request.consent_artefact.artefact_id), self.artefact_id_1)

    def test_request_health_information_authentication_error(self):
        res = APIClient().get(self.request_health_information_url)
        self.assert_for_authentication_error(res, HIUError.CODE_PREFIX)

    @patch('abdm_integrator.utils.requests.post')
    def test_request_health_information_gateway_error(self, mocked_post):
        gateway_error = {'error': {'code': 2500, 'message': 'Invalid request'}}
        mocked_post.return_value = generate_mock_response(HTTP_400_BAD_REQUEST, gateway_error)
        res = self.client.get(self.request_health_information_url, data=self._health_information_request_data())
        json_res = res.json()
        self.assertEqual(res.status_code, ABDMGatewayError.status_code)
        self.assert_error(json_res['error'], gateway_error['error']['code'], ABDMGatewayError.error_message)
        self.assert_error_details(
            json_res['error']['details'][0],
            ABDMGatewayError.detail_code,
            gateway_error['error']['message'],
        )
        self.assertEqual(HealthInformationRequest.objects.all().count(), 0)

    @patch('abdm_integrator.utils.requests.post', side_effect=requests.Timeout)
    def test_request_health_information_service_unavailable_error(self, mocked_post):
        client = APIClient(raise_request_exception=False)
        client.credentials(HTTP_AUTHORIZATION=f'Token {self.token}')
        res = client.get(self.request_health_information_url, data=self._health_information_request_data())
        self.assert_for_abdm_service_unavailable_error(res, HIUError.CODE_PREFIX)
        self.assertEqual(HealthInformationRequest.objects.all().count(), 0)

    def test_request_health_information_artefact_not_found(self, *args):
        res = self.client.get(self.request_health_information_url, data={'artefact_id': str(uuid.uuid4())})
        json_res = res.json()
        self.assertEqual(res.status_code, HTTP_404_NOT_FOUND)
        self.assert_error(
            json_res['error'],
            int(f'{HIUError.CODE_PREFIX}{HTTP_404_NOT_FOUND}'),
            STANDARD_ERRORS.get(HTTP_404_NOT_FOUND)
        )
        self.assert_error_details(
            json_res['error']['details'][0],
            NotFound.default_code,
            NotFound.default_detail,
        )
        self.assertEqual(HealthInformationRequest.objects.all().count(), 0)

    def test_request_health_information_artefact_expired(self):
        res = self.client.get(self.request_health_information_url, data={'artefact_id': self.artefact_id_2})
        json_res = res.json()
        self.assertEqual(res.status_code, HTTP_400_BAD_REQUEST)
        self.assert_error(
            json_res['error'], HIUError.CODE_CONSENT_EXPIRED,
            HIUError.CUSTOM_ERRORS[HIUError.CODE_CONSENT_EXPIRED]
        )
        self.assert_error_details(
            json_res['error']['details'][0], ERROR_CODE_INVALID,
            HIUError.CUSTOM_ERRORS[HIUError.CODE_CONSENT_EXPIRED],
            'artefact_id'
        )
        self.assertEqual(HealthInformationRequest.objects.all().count(), 0)

    @patch('abdm_integrator.hiu.views.health_information.ABDMRequestHelper.gateway_post')
    @patch('abdm_integrator.hiu.views.health_information.ABDMRequestHelper.common_request_data')
    def test_request_health_information_gateway_error_on_request(self, mocked_common_request_data, *args):
        mocked_common_request_data.return_value = {
            'requestId': str(uuid.uuid4()),
            'timestamp': datetime.utcnow().isoformat()
        }
        gateway_request_id = mocked_common_request_data.return_value['requestId']
        mocked_response_cache = {
            'error': {'code': '4500', 'message': 'gateway internal error'}
        }
        ABDMCache.set(f"{gateway_request_id}_1", mocked_response_cache, 10)

        res = self.client.get(self.request_health_information_url, data=self._health_information_request_data())

        json_res = res.json()
        self.assertEqual(res.status_code, ABDMGatewayError.status_code)
        self.assert_error(
            json_res['error'], mocked_response_cache['error']['code'],
            ABDMGatewayError.error_message
        )
        self.assert_error_details(
            json_res['error']['details'][0],
            ABDMGatewayError.detail_code,
            mocked_response_cache['error']['message'],
        )
        self.assertEqual(HealthInformationRequest.objects.all().count(), 1)

    @patch('abdm_integrator.hiu.views.health_information.ABDMRequestHelper.gateway_post')
    @patch('abdm_integrator.hiu.views.health_information.ABDMRequestHelper.common_request_data')
    def test_request_health_information_health_receiver_error_on_receipt(self, mocked_common_request_data, *args):
        mocked_common_request_data.return_value = {
            'requestId': str(uuid.uuid4()),
            'timestamp': datetime.utcnow().isoformat()
        }
        gateway_request_id = mocked_common_request_data.return_value['requestId']
        mocked_response_cache = {
            'error': {
                'code': HIUError.CODE_HEALTH_DATA_RECEIVER,
                'message': HIUError.CUSTOM_ERRORS[HIUError.CODE_HEALTH_DATA_RECEIVER]
            }
        }
        ABDMCache.set(f"{gateway_request_id}_1", mocked_response_cache, 10)

        res = self.client.get(self.request_health_information_url, data=self._health_information_request_data())

        json_res = res.json()
        self.assertEqual(res.status_code, 556)
        self.assert_error(
            json_res['error'],
            mocked_response_cache['error']['code'],
            mocked_response_cache['error']['message']
        )
        self.assert_error_details(
            json_res['error']['details'][0],
            ERROR_CODE_INVALID,
            mocked_response_cache['error']['message'], None
        )
        self.assertEqual(HealthInformationRequest.objects.all().count(), 1)
