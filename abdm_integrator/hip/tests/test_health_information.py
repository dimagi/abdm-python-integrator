import json
import os
import uuid
from copy import deepcopy
from datetime import datetime, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from rest_framework.reverse import reverse
from rest_framework.status import HTTP_202_ACCEPTED, HTTP_400_BAD_REQUEST
from rest_framework.test import APITestCase

from abdm_integrator.const import HealthInformationStatus
from abdm_integrator.crypto import ABDMCrypto
from abdm_integrator.exceptions import STANDARD_ERRORS
from abdm_integrator.hip.exceptions import HIPError
from abdm_integrator.hip.models import ConsentArtefact, HealthDataTransfer, HealthInformationRequest
from abdm_integrator.tests.utils import ErrorResponseAssertMixin, generate_mock_response, init_test_celery_app
from abdm_integrator.utils import ABDMRequestHelper, json_from_file


class TestHealthInformationRequestAPI(APITestCase, ErrorResponseAssertMixin):
    dir_path = os.path.dirname(os.path.abspath(__file__))
    artefact_sample_json_path = os.path.join(dir_path, 'data/artefact_request_sample.json')

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        init_test_celery_app()
        cls.user = User.objects.create_superuser(username='test_user', password='test')
        cls.health_information_request_url = reverse('gateway_health_information_request_hip')
        cls.artefact_sample = json_from_file(cls.artefact_sample_json_path)

    def setUp(self):
        self.client.force_authenticate(user=self.user)

    def tearDown(self):
        HealthDataTransfer.objects.all().delete()
        HealthInformationRequest.objects.all().delete()
        ConsentArtefact.objects.all().delete()

    @classmethod
    def tearDownClass(cls):
        User.objects.all().delete()
        super().tearDownClass()

    @classmethod
    def _sample_artefact_data(cls):
        artefact_data = deepcopy(cls.artefact_sample)
        artefact_data['notification']['consentDetail']['permission']['dataEraseAt'] = (
            datetime.utcnow() + timedelta(days=1)).isoformat()
        return artefact_data

    def _create_artefact(self, artefact_data):
        ConsentArtefact.objects.create(artefact_id=artefact_data['notification']['consentId'],
                                       details=artefact_data['notification']['consentDetail'],
                                       signature=artefact_data['notification']['signature'],
                                       grant_acknowledgement=True)

    def _sample_health_info_request(self):
        payload = ABDMRequestHelper.common_request_data()
        payload['transactionId'] = str(uuid.uuid4())
        payload['hiRequest'] = {
            'consent': {
                'id': self._sample_artefact_data()['notification']['consentId']
            },
            'dateRange': {
                'from': '2016-05-02T07:48:11.937158712',
                'to': '2023-10-01T07:34:21.916Z'
            },
            'dataPushUrl': 'http://sample.com',
        }
        payload['hiRequest']['keyMaterial'] = ABDMCrypto().transfer_material
        return payload

    @patch('abdm_integrator.utils.ABDMRequestHelper.gateway_post', return_value={})
    @patch('abdm_integrator.hip.views.health_information.HealthDataTransferProcessor'
           '.check_health_information_types')
    @patch('abdm_integrator.hip.views.health_information.HealthDataTransferProcessor.fetch_linked_care_context')
    @patch('abdm_integrator.hip.views.health_information.HealthDataTransferProcessor.get_fhir_data_hrp',
           return_value={'test': 'This is confidential health data'})
    @patch('abdm_integrator.hip.views.health_information.requests.post',
           return_value=generate_mock_response(json_response={}))
    def test_health_information_request_success(self, *args):
        artefact_data = self._sample_artefact_data()
        self._create_artefact(artefact_data)
        request_data = self._sample_health_info_request()
        res = self.client.post(self.health_information_request_url, data=json.dumps(request_data),
                               content_type='application/json')
        self.assertEqual(res.status_code, HTTP_202_ACCEPTED)
        self.assertEqual(HealthInformationRequest.objects.all().count(), 1)
        health_info_request = HealthInformationRequest.objects.all()[0]
        self.assertEqual(health_info_request.status, HealthInformationStatus.TRANSFERRED)
        self.assertEqual(str(health_info_request.transaction_id), request_data['transactionId'])
        self.assertIsNone(health_info_request.error)
        self.assertEqual(str(health_info_request.consent_artefact.artefact_id),
                         request_data['hiRequest']['consent']['id'])
        self.assertEqual(HealthDataTransfer.objects.all().count(), 1)
        health_data_transfer = HealthDataTransfer.objects.all()[0]
        self.assertEqual(health_data_transfer.health_information_request, health_info_request)
        self.assertEqual(health_data_transfer.page_number, 1)
        # self.assertEqual(health_data_transfer.care_contexts_status,
        #                  health_info_request.consent_artefact.details['careContexts'])

    def test_health_information_request_validation_error(self, *args):
        request_data = {}
        res = self.client.post(self.health_information_request_url, data=json.dumps(request_data),
                               content_type='application/json')
        json_res = res.json()
        self.assertEqual(res.status_code, HTTP_400_BAD_REQUEST)
        self.assert_error(json_res['error'], int(f'{HIPError.CODE_PREFIX}{HTTP_400_BAD_REQUEST}'),
                          STANDARD_ERRORS.get(HTTP_400_BAD_REQUEST))
        self.assertIsNone(json_res['error'].get('details'))
        self.assertEqual(HealthInformationRequest.objects.all().count(), 0)
        self.assertEqual(HealthDataTransfer.objects.all().count(), 0)

    def test_health_information_request_artefact_not_found(self, *args):
        pass

    def test_health_information_request_consent_expired(self, *args):
        pass

    def test_health_information_request_invalid_date_range(self, *args):
        pass

    def test_health_information_request_key_material_expired(self, *args):
        pass

    def test_health_information_request_fetch_fhir_data_error(self, *args):
        pass

    def test_health_information_request_encryption_error(self, *args):
        pass

    def test_health_information_request_hiu_send_data_error(self, *args):
        pass

    # @patch('abdm_integrator.utils.requests.post')
    # def test_health_information_request_request_gateway_error(self, mocked_post):
    #     gateway_error = {'error': {'code': 2500, 'message': 'Invalid request'}}
    #     mocked_post.return_value = self._mock_response(HTTP_400_BAD_REQUEST, gateway_error)
    #     request_data = self._sample_generate_consent_data()
    #     res = self.client.post(reverse('generate_consent_request'), data=json.dumps(request_data),
    #                            content_type='application/json')
    #     json_res = res.json()
    #     self.assertEqual(res.status_code, ABDMGatewayError.status_code)
    #     self.assert_error(json_res['error'], gateway_error['error']['code'], ABDMGatewayError.error_message)
    #     self.assert_error_details(json_res['error']['details'][0], ABDMGatewayError.detail_code,
    #                               gateway_error['error']['message'], None)
    #     self.assertEqual(ConsentRequest.objects.all().count(), 0)
    #
    # @patch('abdm_integrator.utils.requests.post', side_effect=requests.Timeout)
    # def test_health_information_request_request_service_unavailable_error(self, mocked_post):
    #     client = APIClient(raise_request_exception=False)
    #     client.force_authenticate(self.user)
    #     request_data = self._sample_generate_consent_data()
    #     res = client.post(reverse('generate_consent_request'), data=json.dumps(request_data),
    #                       content_type='application/json')
    #     self.assert_for_abdm_service_unavailable_error(res, HIUError.CODE_PREFIX)
