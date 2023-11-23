import json
import os
import uuid
from copy import deepcopy
from datetime import datetime, timedelta
from unittest.mock import patch

import requests
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils.dateparse import parse_date
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.status import HTTP_200_OK, HTTP_201_CREATED, HTTP_400_BAD_REQUEST
from rest_framework.test import APIClient, APITestCase

from abdm_integrator.const import ConsentStatus, HealthInformationType
from abdm_integrator.exceptions import (
    ERROR_CODE_INVALID,
    ERROR_CODE_REQUIRED,
    ERROR_CODE_REQUIRED_MESSAGE,
    ERROR_FUTURE_DATE_MESSAGE,
    STANDARD_ERRORS,
)
from abdm_integrator.hiu.exceptions import HIUError
from abdm_integrator.hiu.models import ConsentArtefact, ConsentRequest
from abdm_integrator.hiu.tasks import _process_hiu_expired_consents
from abdm_integrator.tests.utils import APITestHelperMixin
from abdm_integrator.utils import abdm_iso_to_datetime, json_from_file


class TestGenerateConsentRequestAPI(APITestCase, APITestHelperMixin):
    dir_path = os.path.dirname(os.path.abspath(__file__))
    consent_sample_json_path = os.path.join(dir_path, 'data/generate_consent_request_sample.json')

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_superuser(username='test_user', password='test')
        cls.consent_request_sample = json_from_file(cls.consent_sample_json_path)
        cls.token = Token.objects.create(user=cls.user)

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token}')

    def tearDown(self):
        ConsentRequest.objects.all().delete()

    @classmethod
    def tearDownClass(cls):
        User.objects.all().delete()
        super().tearDownClass()

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
        self.assert_for_authentication_error(res, HIUError.CODE_PREFIX)
        self.assertEqual(ConsentRequest.objects.all().count(), 0)

    def test_generate_consent_request_validation_error(self, *args):
        request_data = self._sample_generate_consent_data()
        request_data['patient'] = {}
        request_data['permission']['dataEraseAt'] = (datetime.utcnow() - timedelta(days=1)).isoformat()
        res = self.client.post(reverse('generate_consent_request'), data=json.dumps(request_data),
                               content_type='application/json')
        json_res = res.json()
        self.assertEqual(res.status_code, HTTP_400_BAD_REQUEST)
        self.assert_error(json_res['error'], int(f'{HIUError.CODE_PREFIX}{HTTP_400_BAD_REQUEST}'),
                          STANDARD_ERRORS.get(HTTP_400_BAD_REQUEST))
        self.assertEqual(len(json_res['error']['details']), 2)
        self.assert_error_details(json_res['error']['details'][0], ERROR_CODE_REQUIRED,
                                  ERROR_CODE_REQUIRED_MESSAGE, 'patient.id')
        self.assert_error_details(json_res['error']['details'][1], ERROR_CODE_INVALID,
                                  ERROR_FUTURE_DATE_MESSAGE, 'permission.dataEraseAt')
        self.assertEqual(ConsentRequest.objects.all().count(), 0)

    @patch('abdm_integrator.utils.ABDMRequestHelper.abha_post', return_value={'status': False})
    def test_generate_consent_request_patient_not_found(self, *args):
        request_data = self._sample_generate_consent_data()
        res = self.client.post(reverse('generate_consent_request'), data=json.dumps(request_data),
                               content_type='application/json')
        self.assertEqual(res.status_code, HTTP_400_BAD_REQUEST)
        json_res = res.json()
        self.assert_error(json_res['error'], HIUError.CODE_PATIENT_NOT_FOUND,
                          HIUError.CUSTOM_ERRORS[HIUError.CODE_PATIENT_NOT_FOUND])
        self.assert_error_details(json_res['error']['details'][0], ERROR_CODE_INVALID,
                                  HIUError.CUSTOM_ERRORS[HIUError.CODE_PATIENT_NOT_FOUND], 'patient.id')
        self.assertEqual(ConsentRequest.objects.all().count(), 0)

    @patch('abdm_integrator.hiu.views.consents.GenerateConsent.check_if_health_id_exists')
    @patch('abdm_integrator.utils.requests.post')
    def test_generate_consent_request_gateway_error(self, mocked_post, *args):
        self.gateway_error_test(mocked_post, reverse('generate_consent_request'),
                                self._sample_generate_consent_data())

    @patch('abdm_integrator.utils.requests.post', side_effect=requests.Timeout)
    def test_generate_consent_request_service_unavailable_error(self, mocked_post):
        client = APIClient(raise_request_exception=False)
        client.credentials(HTTP_AUTHORIZATION=f'Token {self.token}')
        request_data = self._sample_generate_consent_data()
        res = client.post(reverse('generate_consent_request'), data=json.dumps(request_data),
                          content_type='application/json')
        self.assert_for_abdm_service_unavailable_error(res, HIUError.CODE_PREFIX)


class TestListConsentsAndArtefactsAPI(APITestCase, APITestHelperMixin):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_superuser(username='test_user', password='test')
        cls.token = Token.objects.create(user=cls.user)
        cls.consent_request_id_1 = str(uuid.uuid4())
        cls.consent_request_id_2 = str(uuid.uuid4())
        cls.patient_1 = 'test1@sbx'
        cls.patient_2 = 'test2@sbx'
        cls._add_consents_data()

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
            'artefact_id': str(uuid.uuid4()),
            'gateway_request_id': str(uuid.uuid4()),
            # sample data for details. Actual data will contain more fields
            'details': {
                'hip': {
                    'id': '6004',
                    'name': 'Test Eye Care Center '
                },
            }
        }
        artefact_data_2 = {
            'artefact_id': str(uuid.uuid4()),
            'gateway_request_id': str(uuid.uuid4()),
            'details': {
                'hip': {
                    'id': '6005',
                    'name': 'Demo Clinic'
                },
            }
        }
        ConsentArtefact.objects.create(**artefact_data_1, consent_request=consent_request_1)
        ConsentArtefact.objects.create(**artefact_data_2, consent_request=consent_request_1)
        consent_data_2 = {
            'consent_request_id': cls.consent_request_id_2,
            'gateway_request_id': str(uuid.uuid4()),
            'status': ConsentStatus.EXPIRED,
            'health_info_from_date': '2021-05-17T15:12:43.960000',
            'health_info_to_date': '2023-08-07T15:12:43.961000',
            'health_info_types': [
                "WellnessRecord"
            ],
            'expiry_date': (datetime.utcnow() - timedelta(days=2)).isoformat(),
            'details': {
                'patient': {
                    'id': cls.patient_2
                }
            }
        }
        ConsentRequest.objects.create(**consent_data_2, user=cls.user)

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token}')

    @classmethod
    def tearDownClass(cls):
        ConsentArtefact.objects.all().delete()
        ConsentRequest.objects.all().delete()
        User.objects.all().delete()
        super().tearDownClass()

    def test_list_consents(self):
        res = self.client.get(reverse('consents_list'))
        self.assertEqual(res.status_code, HTTP_200_OK)
        self.assertEqual(res.json()["count"], 2)
        self.assertEqual(res.json()['results'][0]['id'], 2)

    def test_list_consents_authentication_error(self):
        res = APIClient().get(reverse('consents_list'))
        self.assert_for_authentication_error(res, HIUError.CODE_PREFIX)

    def test_list_consents_filter_status(self):
        params = {"status": ConsentStatus.EXPIRED}
        res = self.client.get(reverse('consents_list'), data=params)
        self.assertEqual(res.status_code, HTTP_200_OK)
        self.assertEqual(res.json()["count"], 1)
        self.assertEqual(res.json()["results"][0]["status"], params["status"])

    def test_list_consents_filter_abha_id(self):
        params = {"abha_id": self.patient_1}
        res = self.client.get(reverse('consents_list'), data=params)
        self.assertEqual(res.status_code, HTTP_200_OK)
        self.assertEqual(res.json()["count"], 1)
        self.assertEqual(res.json()["results"][0]["details"]["patient"]["id"], params["abha_id"])

    def test_list_consents_filter_search(self):
        params = {"search": "prescript"}
        res = self.client.get(reverse('consents_list'), data=params)
        self.assertEqual(res.status_code, HTTP_200_OK)
        self.assertEqual(res.json()["count"], 1)
        self.assertTrue(any(params["search"].casefold() in hi_type.casefold()
                            for hi_type in res.json()["results"][0]["health_info_types"]))

    def test_list_consents_filter_from_date(self):
        params = {"from_date": "2018-07-10"}
        res = self.client.get(reverse('consents_list'), data=params)
        self.assertEqual(res.status_code, HTTP_200_OK)
        self.assertEqual(res.json()["count"], 1)
        self.assertGreaterEqual(abdm_iso_to_datetime(
            res.json()["results"][0]["health_info_to_date"]).date(),
            parse_date(params["from_date"])
        )

    def test_list_consents_filter_to_date(self):
        params = {"to_date": "2016-05-18"}
        res = self.client.get(reverse('consents_list'), data=params)
        self.assertEqual(res.status_code, HTTP_200_OK)
        self.assertEqual(res.json()["count"], 1)
        self.assertLessEqual(abdm_iso_to_datetime(res.json()["results"][0]["health_info_from_date"]).date(),
                             parse_date(params["to_date"]))

    def test_list_consents_filter_from_and_to_date(self):
        params = {"from_date": "2015-07-10", "to_date": "2022-05-18"}
        res = self.client.get(reverse('consents_list'), data=params)
        self.assertEqual(res.status_code, HTTP_200_OK)
        self.assertEqual(res.json()["count"], 2)
        for result in res.json()["results"]:
            self.assertGreaterEqual(abdm_iso_to_datetime(result["health_info_to_date"]).date(),
                                    parse_date(params["from_date"]))
            self.assertLessEqual(abdm_iso_to_datetime(result["health_info_from_date"]).date(),
                                 parse_date(params["to_date"]))

    def test_retrieve_consent(self):
        res = self.client.get(f"{reverse('consents_retrieve', args=['1'])}")
        self.assertEqual(res.status_code, HTTP_200_OK)
        self.assertEqual(res.json()['consent_request_id'], self.consent_request_id_1)

    def test_retrieve_consent_authentication_error(self):
        res = APIClient().get(f"{reverse('consents_retrieve', args=['1'])}")
        self.assert_for_authentication_error(res, HIUError.CODE_PREFIX)

    def test_list_consent_artefacts_consent_id(self):
        params = {"consent_request_id": self.consent_request_id_1}
        res = self.client.get(reverse('artefacts_list'), data=params)
        self.assertEqual(res.status_code, HTTP_200_OK)
        self.assertEqual(res.json()["count"], 2)
        self.assertEqual(res.json()['results'][0]['id'], 2)
        for result in res.json()["results"]:
            self.assertEqual(result["consent_request"], params['consent_request_id'])

    def test_list_consent_artefacts_authentication_error(self):
        res = APIClient().get(reverse('artefacts_list'))
        self.assert_for_authentication_error(res, HIUError.CODE_PREFIX)

    def test_list_consent_artefacts_no_consent_id(self):
        res = self.client.get(reverse('artefacts_list'))
        self.assertEqual(res.status_code, HTTP_400_BAD_REQUEST)
        self.assertEqual(res.json()['error']['details'][0],
                         {'attr': 'consent_request_id', 'code': ERROR_CODE_REQUIRED,
                          'detail': ERROR_CODE_REQUIRED_MESSAGE})

    def test_list_consents_artefacts_search(self):
        params = {"consent_request_id": self.consent_request_id_1, "search": "test eye"}
        res = self.client.get(reverse('artefacts_list'), data=params)
        self.assertEqual(res.status_code, HTTP_200_OK)
        self.assertEqual(res.json()["count"], 1)
        self.assertIn(params["search"].casefold(), res.json()["results"][0]["details"]["hip"]["name"].casefold())

    def test_retrieve_consent_artefact(self):
        res = self.client.get(f"{reverse('artefacts_retrieve', args=['1'])}")
        self.assertEqual(res.status_code, HTTP_200_OK)
        self.assertEqual(res.json()['consent_request'], self.consent_request_id_1)

    def test_retrieve_consent_artefact_authentication_error(self):
        res = APIClient().get(f"{reverse('artefacts_retrieve', args=['1'])}")
        self.assert_for_authentication_error(res, HIUError.CODE_PREFIX)


class TestConsentExpiryProcessor(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_superuser(username='test_user', password='test')
        cls.consent_request_id_1 = str(uuid.uuid4())
        cls.consent_request_id_2 = str(uuid.uuid4())
        cls.patient_1 = 'test1@sbx'
        cls._add_consents_data()

    @classmethod
    def tearDownClass(cls):
        ConsentArtefact.objects.all().delete()
        ConsentRequest.objects.all().delete()
        User.objects.all().delete()
        super().tearDownClass()

    @staticmethod
    def _copy_artefact_data(artefact_data):
        artefact_data_copy = deepcopy(artefact_data)
        artefact_data_copy['artefact_id'] = str(uuid.uuid4())
        artefact_data_copy['gateway_request_id'] = str(uuid.uuid4())
        return artefact_data_copy

    @classmethod
    def _add_consents_data(cls):
        consent_data_1 = {
            'consent_request_id': cls.consent_request_id_1,
            'gateway_request_id': str(uuid.uuid4()),
            'status': ConsentStatus.GRANTED,
            'health_info_from_date': (datetime.utcnow() - timedelta(days=100)).isoformat(),
            'health_info_to_date': (datetime.utcnow() - timedelta(days=1)).isoformat(),
            'health_info_types': [
                HealthInformationType.PRESCRIPTION,
            ],
            'expiry_date': (datetime.utcnow() - timedelta(hours=1)).isoformat(),
            'details': {
                'patient': {
                    'id': cls.patient_1
                }
            }
        }
        consent_request_1 = ConsentRequest.objects.create(**consent_data_1, user=cls.user)
        artefact_data_1 = {
            'artefact_id': str(uuid.uuid4()),
            'gateway_request_id': str(uuid.uuid4()),
            # sample data for details. Actual data will contain more fields
            'details': {
                'hip': {
                    'id': '6004',
                    'name': 'Test Eye Care Center '
                },
            }
        }
        artefact_data_2 = cls._copy_artefact_data(artefact_data_1)
        ConsentArtefact.objects.create(**artefact_data_1, consent_request=consent_request_1)
        ConsentArtefact.objects.create(**artefact_data_2, consent_request=consent_request_1)

        consent_data_2 = deepcopy(consent_data_1)
        consent_data_2['consent_request_id'] = cls.consent_request_id_2
        consent_data_2['gateway_request_id'] = str(uuid.uuid4())
        consent_data_2['expiry_date'] = (datetime.utcnow() + timedelta(hours=2)).isoformat()

        consent_request_2 = ConsentRequest.objects.create(**consent_data_2, user=cls.user)
        artefact_data_3 = cls._copy_artefact_data(artefact_data_1)
        ConsentArtefact.objects.create(**artefact_data_3, consent_request=consent_request_2)

    def test_process_consent_expiry(self):
        _process_hiu_expired_consents()
        self.assertEqual(ConsentRequest.objects.count(), 2)
        self.assertEqual(ConsentArtefact.objects.count(), 1)
        consent_request_1 = ConsentRequest.objects.get(consent_request_id=self.consent_request_id_1)
        self.assertEqual(consent_request_1.status, ConsentStatus.EXPIRED)
        self.assertEqual(consent_request_1.artefacts.count(), 0)
        consent_request_2 = ConsentRequest.objects.get(consent_request_id=self.consent_request_id_2)
        self.assertEqual(consent_request_2.status, ConsentStatus.GRANTED)
        self.assertEqual(consent_request_2.artefacts.count(), 1)
