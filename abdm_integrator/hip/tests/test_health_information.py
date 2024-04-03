import json
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from rest_framework.reverse import reverse
from rest_framework.status import (
    HTTP_202_ACCEPTED,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)
from rest_framework.test import APIClient, APITestCase

from abdm_integrator.const import (
    HealthInformationStatus,
    HealthInformationType,
    LinkRequestInitiator,
    LinkRequestStatus,
)
from abdm_integrator.exceptions import STANDARD_ERRORS, ABDMGatewayError, ABDMServiceUnavailable
from abdm_integrator.hip.exceptions import HIPError
from abdm_integrator.hip.models import (
    ConsentArtefact,
    HealthDataTransfer,
    HealthInformationRequest,
    LinkCareContext,
    LinkRequestDetails,
)
from abdm_integrator.hip.views.health_information import (
    GatewayHealthInformationRequestProcessor,
    HealthDataTransferProcessor,
)
from abdm_integrator.tests.utils import APITestHelperMixin, generate_mock_response


class TestHIPGatewayHealthInformationRequestAPI(APITestCase, APITestHelperMixin):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_superuser(username='test_user', password='test')
        cls.gateway_health_information_request_url = reverse('gateway_health_information_request_hip')

    def setUp(self):
        # Client used to call Gateway facing APIs
        self.client.force_authenticate(self.user)
        self.consent_artefact_id = uuid.uuid4().hex
        self.care_context_reference = uuid.uuid4().hex

    def tearDown(self):
        LinkCareContext.objects.all().delete()
        LinkRequestDetails.objects.all().delete()
        ConsentArtefact.objects.all().delete()
        HealthDataTransfer.objects.all().delete()
        HealthInformationRequest.objects.all().delete()

    @classmethod
    def tearDownClass(cls):
        User.objects.all().delete()
        super().tearDownClass()

    @staticmethod
    def _health_information_request_data(consent_artefact_id):
        return {
            'transactionId': str(uuid.uuid4()),
            'requestId': str(uuid.uuid4()),
            'timestamp': datetime.utcnow().isoformat(),
            'hiRequest': {
                'consent': {
                    'id': consent_artefact_id
                },
                'dateRange': {
                    'from': datetime(year=2023, month=2, day=1).isoformat(),
                    'to': datetime(year=2023, month=11, day=30).isoformat()
                },
                'dataPushUrl': 'https://dev.abdm.gov.in/patient-hiu/data/notification',
                'keyMaterial': {
                    'cryptoAlg': 'ECDH',
                    'curve': 'curve25519',
                    'dhPublicKey': {
                        'expiry': (datetime.utcnow() + timedelta(hours=1)).isoformat(),
                        'parameters': 'Ephemeral public key',
                        'keyValue': '62eyUWpVCksedcSb376Hc4='
                    },
                    'nonce': 'nIvmTpz2F0Ur3UA7i8Q='
                }
            }
        }

    @staticmethod
    def _add_consent_artefact(consent_artefact_id, expiry_datetime=None, care_context_references=None):
        if expiry_datetime is None:
            expiry_datetime = (datetime.utcnow() + timedelta(days=1)).isoformat()
        artefact_details = {
            'consentId': consent_artefact_id,
            'createdAt': datetime.utcnow().isoformat(),
            'purpose': {
                'text': 'Self Requested',
                'code': 'PATRQT',
                'refUri': 'NULL'
            },
            'patient': {'id': 'test_user@sbx'},
            'consentManager': {'id': 'sbx'},
            'hip': {'id': '1001', 'name': 'Test HIP'},
            'hiTypes': [
                'DiagnosticReport',
                'Prescription',
                'ImmunizationRecord',
            ],
            'permission': {
                'accessMode': 'VIEW',
                'dateRange': {
                    'from': datetime(year=2023, month=1, day=1).isoformat(),
                    'to': datetime(year=2023, month=12, day=31, hour=23, minute=59, second=59).isoformat()
                },
                'dataEraseAt': expiry_datetime,
                'frequency': {
                    'unit': 'HOUR',
                    'value': 1,
                    'repeats': 0
                }
            },
            'careContexts': [
                {
                    'patientReference': 'PT-101',
                    'careContextReference': reference
                }
                for reference in care_context_references
            ]
        }
        return ConsentArtefact.objects.create(
            artefact_id=consent_artefact_id,
            details=artefact_details,
            expiry_date=artefact_details['permission']['dataEraseAt'],
            signature=uuid.uuid4().hex,
            grant_acknowledgement=True,
        )

    @staticmethod
    def _add_linked_care_context_data(care_context_reference, health_info_types, record_date=None):
        if record_date is None:
            record_date = datetime(year=2023, month=3, day=1).isoformat()
        link_request_details = LinkRequestDetails.objects.create(
            patient_reference='PT-101',
            patient_display='Test Patient',
            hip_id='1001',
            initiated_by=LinkRequestInitiator.PATIENT,
            status=LinkRequestStatus.SUCCESS,
        )
        return LinkCareContext.objects.create(
            reference=care_context_reference,
            display='Visit to Patient One',
            health_info_types=health_info_types,
            additional_info={'domain': 'test', 'record_date': record_date},
            link_request_details=link_request_details
        )

    @staticmethod
    def _add_health_information_request(consent_artefact_id, transaction_id):
        return HealthInformationRequest.objects.create(
            consent_artefact_id=consent_artefact_id,
            transaction_id=transaction_id,
        )

    def _assert_health_info_request_error(self, transaction_id, error):
        health_information_request = HealthInformationRequest.objects.get(transaction_id=transaction_id)
        self.assertEqual(health_information_request.status, HealthInformationStatus.ERROR)
        self.assertEqual(health_information_request.error, error)

    def _assert_for_health_data_transfer_single_page(self, health_information_request, care_contexts_status):
        results = HealthDataTransfer.objects.filter(health_information_request=health_information_request)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].page_number, 1)
        self.assertEqual(results[0].care_contexts_status, care_contexts_status)

    @patch('abdm_integrator.hip.views.health_information.process_hip_health_information_request')
    def test_gateway_health_information_request_success(self, *args):
        request_data = self._health_information_request_data(self.consent_artefact_id)

        res = self.client.post(
            self.gateway_health_information_request_url,
            data=json.dumps(request_data),
            content_type='application/json'
        )

        self.assertEqual(res.status_code, HTTP_202_ACCEPTED)

    @patch('abdm_integrator.hip.views.health_information.process_hip_health_information_request')
    def test_gateway_health_information_request_authentication_error(self, *args):
        request_data = self._health_information_request_data(self.consent_artefact_id)

        res = APIClient().post(
            self.gateway_health_information_request_url,
            data=json.dumps(request_data),
            content_type='application/json'
        )

        self.assertEqual(res.status_code, HTTP_401_UNAUTHORIZED)

    @patch('abdm_integrator.hip.views.health_information.process_hip_health_information_request')
    def test_gateway_health_information_request_validation_error(self, *args):
        request_data = self._health_information_request_data(self.consent_artefact_id)
        del request_data['hiRequest']['dataPushUrl']

        res = self.client.post(
            self.gateway_health_information_request_url,
            data=json.dumps(request_data),
            content_type='application/json',
        )

        self.assertEqual(res.status_code, HTTP_400_BAD_REQUEST)
        self.assert_error(
            res.json()['error'],
            int(f'{HIPError.CODE_PREFIX}{HTTP_400_BAD_REQUEST}'),
            STANDARD_ERRORS.get(HTTP_400_BAD_REQUEST),
        )

    @patch('abdm_integrator.hip.views.health_information.ABDMRequestHelper.gateway_post')
    @patch('abdm_integrator.hip.views.health_information.HealthDataTransferProcessor.process')
    def test_process_health_information_request_success(self, mocked_health_data_transfer_processor, *args):
        mocked_health_data_transfer_processor.return_value = (
            True,
            [{
                'careContextReference': self.care_context_reference,
                'hiStatus': HealthInformationStatus.DELIVERED,
                'description': 'Delivered',
            }]
        )
        consent_artefact = self._add_consent_artefact(
            self.consent_artefact_id,
            care_context_references=[self.care_context_reference]
        )
        request_data = self._health_information_request_data(self.consent_artefact_id)

        result = GatewayHealthInformationRequestProcessor(request_data).process_request()

        self.assertIsNone(result)
        health_information_request = HealthInformationRequest.objects.get(
            transaction_id=request_data['transactionId']
        )
        self.assertEqual(health_information_request.consent_artefact, consent_artefact)
        self.assertEqual(health_information_request.status, HealthInformationStatus.TRANSFERRED)
        self.assertIsNone(health_information_request.error)

    @patch('abdm_integrator.hip.views.health_information.ABDMRequestHelper.gateway_post')
    @patch('abdm_integrator.hip.views.health_information.HealthDataTransferProcessor.process')
    def test_process_health_information_request_transfer_failed(self, mocked_health_data_transfer_processor,
                                                                *args):
        mocked_health_data_transfer_processor.return_value = (
            False,
            [{'careContextReference': self.care_context_reference, 'hiStatus': HealthInformationStatus.ERRORED,
              'description': 'some error occurred'}]
        )

        consent_artefact = self._add_consent_artefact(
            self.consent_artefact_id,
            care_context_references=[self.care_context_reference])
        request_data = self._health_information_request_data(self.consent_artefact_id)

        result = GatewayHealthInformationRequestProcessor(request_data).process_request()

        self.assertIsNone(result)
        health_information_request = HealthInformationRequest.objects.get(
            transaction_id=request_data['transactionId']
        )
        self.assertEqual(health_information_request.consent_artefact, consent_artefact)
        self.assertEqual(health_information_request.status, HealthInformationStatus.FAILED)
        self.assertIsNone(health_information_request.error)

    @patch('abdm_integrator.hip.views.health_information.ABDMRequestHelper.gateway_post')
    def test_process_health_information_request_artefact_not_found(self, *args):
        request_data = self._health_information_request_data(self.consent_artefact_id)

        result = GatewayHealthInformationRequestProcessor(request_data).process_request()

        error_code = HIPError.CODE_ARTEFACT_NOT_FOUND
        self.assertEqual(result, {'code': error_code, 'message': HIPError.CUSTOM_ERRORS.get(error_code)})
        self._assert_health_info_request_error(request_data['transactionId'], result)

    @patch('abdm_integrator.hip.views.health_information.ABDMRequestHelper.gateway_post')
    def test_process_health_information_request_key_pair_expired(self, *args):
        self._add_consent_artefact(self.consent_artefact_id, care_context_references=[self.care_context_reference])
        request_data = self._health_information_request_data(self.consent_artefact_id)
        request_data['hiRequest']['keyMaterial']['dhPublicKey']['expiry'] = (
            datetime.utcnow() - timedelta(minutes=1)
        ).isoformat()

        result = GatewayHealthInformationRequestProcessor(request_data).process_request()

        error_code = HIPError.CODE_KEY_PAIR_EXPIRED
        self.assertEqual(result, {'code': error_code, 'message': HIPError.CUSTOM_ERRORS.get(error_code)})
        self._assert_health_info_request_error(request_data['transactionId'], result)

    @patch('abdm_integrator.hip.views.health_information.ABDMRequestHelper.gateway_post')
    def test_process_health_information_request_consent_expired(self, *args):
        expiry_datetime = (datetime.utcnow() - timedelta(minutes=1)).isoformat()
        self._add_consent_artefact(
            self.consent_artefact_id,
            expiry_datetime=expiry_datetime,
            care_context_references=[uuid.uuid4().hex]
        )
        request_data = self._health_information_request_data(self.consent_artefact_id)

        result = GatewayHealthInformationRequestProcessor(request_data).process_request()

        error_code = HIPError.CODE_CONSENT_EXPIRED
        self.assertEqual(result, {'code': error_code, 'message': HIPError.CUSTOM_ERRORS.get(error_code)})
        self._assert_health_info_request_error(request_data['transactionId'], result)

    @patch('abdm_integrator.hip.views.health_information.ABDMRequestHelper.gateway_post')
    def test_process_health_information_request_invalid_date_range(self, *args):
        self._add_consent_artefact(self.consent_artefact_id, care_context_references=[self.care_context_reference])
        request_data = self._health_information_request_data(self.consent_artefact_id)
        request_data['hiRequest']['dateRange']['from'] = datetime(year=2022, month=12, day=31).isoformat()

        result = GatewayHealthInformationRequestProcessor(request_data).process_request()

        error_code = HIPError.CODE_INVALID_DATE_RANGE
        self.assertEqual(result, {'code': error_code, 'message': HIPError.CUSTOM_ERRORS.get(error_code)})
        self._assert_health_info_request_error(request_data['transactionId'], result)

    @patch('abdm_integrator.hip.views.health_information.ABDMRequestHelper.gateway_post')
    def test_process_health_information_request_gateway_error(self, mocked_post):
        gateway_error = {'code': 2500, 'message': 'Invalid request'}
        mocked_post.side_effect = ABDMGatewayError(
            error_code=gateway_error['code'],
            detail_message=gateway_error['message']
        )

        self._add_consent_artefact(self.consent_artefact_id, care_context_references=[self.care_context_reference])
        request_data = self._health_information_request_data(self.consent_artefact_id)

        result = GatewayHealthInformationRequestProcessor(request_data).process_request()

        self.assertEqual(result['code'], gateway_error['code'])
        self.assertEqual(result['message'], ABDMGatewayError.error_message)
        self.assert_error_details(
            result['details'][0],
            ABDMGatewayError.detail_code,
            gateway_error['message'],
        )
        self._assert_health_info_request_error(request_data['transactionId'], result)

    @patch('abdm_integrator.hip.views.health_information.ABDMRequestHelper.gateway_post',
           side_effect=ABDMServiceUnavailable)
    def test_process_health_information_request_abdm_service_unavailable_error(self, *args):
        self._add_consent_artefact(self.consent_artefact_id, care_context_references=[self.care_context_reference])
        request_data = self._health_information_request_data(self.consent_artefact_id)

        result = GatewayHealthInformationRequestProcessor(request_data).process_request()

        self.assertEqual(result, ABDMServiceUnavailable().error)
        self._assert_health_info_request_error(request_data['transactionId'], result)

    @patch('abdm_integrator.integrations.HRPIntegration.fetch_health_data', return_value=['health data'])
    @patch('abdm_integrator.hip.views.health_information.ABDMCrypto.encrypt', return_value='encrypted')
    @patch('abdm_integrator.hip.views.health_information.requests.post')
    def test_process_health_information_transfer_care_contexts_success(self, *args):
        self._add_consent_artefact(self.consent_artefact_id, care_context_references=[self.care_context_reference])
        self._add_linked_care_context_data(self.care_context_reference, [HealthInformationType.PRESCRIPTION])
        request_data = self._health_information_request_data(self.consent_artefact_id)
        health_information_request = self._add_health_information_request(
            self.consent_artefact_id,
            request_data['transactionId']
        )

        overall_transfer_status, care_contexts_status = HealthDataTransferProcessor(
            health_information_request,
            request_data['hiRequest']
        ).process()

        self.assertTrue(overall_transfer_status)
        self.assertEqual(
            care_contexts_status,
            [{
                'careContextReference': self.care_context_reference,
                'hiStatus': HealthInformationStatus.DELIVERED,
                'description': 'Delivered'
            }]
        )
        self._assert_for_health_data_transfer_single_page(health_information_request, care_contexts_status)

    @patch('abdm_integrator.integrations.HRPIntegration.fetch_health_data', return_value=['health data'])
    @patch('abdm_integrator.hip.views.health_information.ABDMCrypto.encrypt', return_value='encrypted')
    @patch('abdm_integrator.hip.views.health_information.requests.post')
    def test_process_health_information_transfer_linked_care_contexts_not_found(self, *args):
        self._add_consent_artefact(self.consent_artefact_id, care_context_references=[self.care_context_reference])
        request_data = self._health_information_request_data(self.consent_artefact_id)
        health_information_request = self._add_health_information_request(
            self.consent_artefact_id,
            request_data['transactionId']
        )

        overall_transfer_status, care_contexts_status = HealthDataTransferProcessor(
            health_information_request,
            request_data['hiRequest']
        ).process()

        self.assertFalse(overall_transfer_status)
        self.assertEqual(
            care_contexts_status,
            [{
                'careContextReference': self.care_context_reference,
                'hiStatus': HealthInformationStatus.ERRORED,
                'description': f'Linked Care Context not found for {self.care_context_reference}'
            }]
        )
        self._assert_for_health_data_transfer_single_page(health_information_request, care_contexts_status)

    @patch('abdm_integrator.integrations.HRPIntegration.fetch_health_data', return_value=['health data'])
    @patch('abdm_integrator.hip.views.health_information.ABDMCrypto.encrypt', return_value='encrypted')
    @patch('abdm_integrator.hip.views.health_information.requests.post')
    def test_process_health_information_transfer_hi_types_validation_failed(self, *args):
        self._add_consent_artefact(self.consent_artefact_id, care_context_references=[self.care_context_reference])
        self._add_linked_care_context_data(self.care_context_reference, [HealthInformationType.WELLNESS_RECORD])
        request_data = self._health_information_request_data(self.consent_artefact_id)
        health_information_request = self._add_health_information_request(
            self.consent_artefact_id,
            request_data['transactionId']
        )

        overall_transfer_status, care_contexts_status = HealthDataTransferProcessor(
            health_information_request,
            request_data['hiRequest']
        ).process()

        self.assertFalse(overall_transfer_status)
        self.assertEqual(
            care_contexts_status,
            [{
                'careContextReference': self.care_context_reference,
                'hiStatus': HealthInformationStatus.ERRORED,
                'description': f'Validation failed for HI Types for care context: {self.care_context_reference}'
            }]
        )
        self._assert_for_health_data_transfer_single_page(health_information_request, care_contexts_status)

    @patch('abdm_integrator.integrations.HRPIntegration.fetch_health_data', return_value=['health data'])
    @patch('abdm_integrator.hip.views.health_information.ABDMCrypto.encrypt', return_value='encrypted')
    @patch('abdm_integrator.hip.views.health_information.requests.post')
    def test_process_health_information_transfer_health_data_not_in_range(self, *args):
        self._add_consent_artefact(self.consent_artefact_id, care_context_references=[self.care_context_reference])
        record_date = datetime(year=2023, month=1, day=2).isoformat()
        self._add_linked_care_context_data(
            self.care_context_reference,
            [HealthInformationType.PRESCRIPTION],
            record_date
        )
        request_data = self._health_information_request_data(self.consent_artefact_id)
        health_information_request = self._add_health_information_request(
            self.consent_artefact_id,
            request_data['transactionId']
        )

        overall_transfer_status, care_contexts_status = HealthDataTransferProcessor(
            health_information_request,
            request_data['hiRequest']
        ).process()

        self.assertFalse(overall_transfer_status)
        self.assertEqual(
            care_contexts_status,
            [{
                'careContextReference': self.care_context_reference,
                'hiStatus': HealthInformationStatus.ERRORED,
                'description': f'Health record date is not in requested date range '
                               f'for {self.care_context_reference}'
            }]
        )
        self._assert_for_health_data_transfer_single_page(health_information_request, care_contexts_status)

    @patch('abdm_integrator.integrations.HRPIntegration.fetch_health_data', return_value=[])
    @patch('abdm_integrator.hip.views.health_information.ABDMCrypto.encrypt', return_value='encrypted')
    @patch('abdm_integrator.hip.views.health_information.requests.post')
    def test_process_health_information_transfer_fetch_no_health_data(self, *args):
        self._add_consent_artefact(self.consent_artefact_id, care_context_references=[self.care_context_reference])
        self._add_linked_care_context_data(self.care_context_reference, [HealthInformationType.PRESCRIPTION])
        request_data = self._health_information_request_data(self.consent_artefact_id)
        health_information_request = self._add_health_information_request(
            self.consent_artefact_id,
            request_data['transactionId']
        )

        overall_transfer_status, care_contexts_status = HealthDataTransferProcessor(
            health_information_request,
            request_data['hiRequest']
        ).process()

        self.assertFalse(overall_transfer_status)
        self.assertEqual(
            care_contexts_status,
            [{
                'careContextReference': self.care_context_reference,
                'hiStatus': HealthInformationStatus.ERRORED,
                'description': f'Error occurred while fetching health data from HRP: No health record available'
                               f' from HRP for {self.care_context_reference}'
            }]
        )
        self._assert_for_health_data_transfer_single_page(health_information_request, care_contexts_status)

    @patch('abdm_integrator.integrations.HRPIntegration.fetch_health_data',
           side_effect=Exception('Internal error'))
    @patch('abdm_integrator.hip.views.health_information.ABDMCrypto.encrypt', return_value='encrypted')
    @patch('abdm_integrator.hip.views.health_information.requests.post')
    def test_process_health_information_transfer_fetch_health_data_error(self, *args):
        self._add_consent_artefact(self.consent_artefact_id, care_context_references=[self.care_context_reference])
        self._add_linked_care_context_data(self.care_context_reference, [HealthInformationType.PRESCRIPTION])
        request_data = self._health_information_request_data(self.consent_artefact_id)
        health_information_request = self._add_health_information_request(
            self.consent_artefact_id,
            request_data['transactionId']
        )

        overall_transfer_status, care_contexts_status = HealthDataTransferProcessor(
            health_information_request,
            request_data['hiRequest']
        ).process()

        self.assertFalse(overall_transfer_status)
        self.assertEqual(
            care_contexts_status,
            [{
                'careContextReference': self.care_context_reference,
                'hiStatus': HealthInformationStatus.ERRORED,
                'description': 'Error occurred while fetching health data from HRP: Internal error'
            }]
        )
        self._assert_for_health_data_transfer_single_page(health_information_request, care_contexts_status)

    @patch('abdm_integrator.integrations.HRPIntegration.fetch_health_data', return_value=['health data'])
    @patch('abdm_integrator.hip.views.health_information.ABDMCrypto.encrypt',
           side_effect=Exception('Crypto error'))
    @patch('abdm_integrator.hip.views.health_information.requests.post')
    def test_process_health_information_transfer_health_data_encryption_error(self, *args):
        self._add_consent_artefact(self.consent_artefact_id, care_context_references=[self.care_context_reference])
        self._add_linked_care_context_data(self.care_context_reference, [HealthInformationType.PRESCRIPTION])

        request_data = self._health_information_request_data(self.consent_artefact_id)
        health_information_request = self._add_health_information_request(
            self.consent_artefact_id,
            request_data['transactionId']
        )

        overall_transfer_status, care_contexts_status = HealthDataTransferProcessor(
            health_information_request,
            request_data['hiRequest']
        ).process()

        self.assertFalse(overall_transfer_status)
        self.assertEqual(
            care_contexts_status,
            [{
                'careContextReference': self.care_context_reference,
                'hiStatus': HealthInformationStatus.ERRORED,
                'description': 'Error occurred while encryption process: Crypto error'
            }]
        )
        self._assert_for_health_data_transfer_single_page(health_information_request, care_contexts_status)

    @patch('abdm_integrator.integrations.HRPIntegration.fetch_health_data', return_value=['health data'])
    @patch('abdm_integrator.hip.views.health_information.ABDMCrypto.encrypt', return_value='encrypted')
    @patch('abdm_integrator.hip.views.health_information.requests.post')
    def test_process_health_information_transfer_send_data_hiu_failed(self, mocked_post, *args):
        mocked_post.return_value = generate_mock_response(status_code=HTTP_404_NOT_FOUND,
                                                          json_response={'code': 'error'})
        self._add_consent_artefact(self.consent_artefact_id, care_context_references=[self.care_context_reference])
        self._add_linked_care_context_data(self.care_context_reference, [HealthInformationType.PRESCRIPTION])
        request_data = self._health_information_request_data(self.consent_artefact_id)
        health_information_request = self._add_health_information_request(
            self.consent_artefact_id,
            request_data['transactionId']
        )

        overall_transfer_status, care_contexts_status = HealthDataTransferProcessor(
            health_information_request,
            request_data['hiRequest']
        ).process()

        self.assertFalse(overall_transfer_status)
        self.assertEqual(
            care_contexts_status,
            [{
                'careContextReference': self.care_context_reference,
                'hiStatus': HealthInformationStatus.ERRORED,
                'description': 'Error occurred while sending health data to HIU: 404 Client Error: '
                               'None for url: None'
            }]
        )
        self._assert_for_health_data_transfer_single_page(health_information_request, care_contexts_status)

    @patch('abdm_integrator.integrations.HRPIntegration.fetch_health_data', return_value=['health data'])
    @patch('abdm_integrator.hip.views.health_information.ABDMCrypto.encrypt', return_value='encrypted')
    @patch('abdm_integrator.hip.views.health_information.requests.post')
    def test_process_health_information_transfer_multiple_care_contexts_success(self, *args):
        care_context_references = [self.care_context_reference, uuid.uuid4().hex]
        self._add_consent_artefact(self.consent_artefact_id, care_context_references=care_context_references)
        self._add_linked_care_context_data(care_context_references[0], [HealthInformationType.PRESCRIPTION])
        self._add_linked_care_context_data(care_context_references[1], [HealthInformationType.DIAGNOSTIC_REPORT])

        request_data = self._health_information_request_data(self.consent_artefact_id)
        health_information_request = self._add_health_information_request(
            self.consent_artefact_id,
            request_data['transactionId']
        )

        overall_transfer_status, care_contexts_status = HealthDataTransferProcessor(
            health_information_request,
            request_data['hiRequest']
        ).process()

        self.assertTrue(overall_transfer_status)
        self.assertEqual(len(care_contexts_status), len(care_context_references))
        for idx, status in enumerate(care_contexts_status):
            self.assertEqual(
                status,
                {
                    'careContextReference': care_context_references[idx],
                    'hiStatus': HealthInformationStatus.DELIVERED,
                    'description': 'Delivered'
                }
            )
        self._assert_for_health_data_transfer_single_page(health_information_request, care_contexts_status)

    @patch('abdm_integrator.integrations.HRPIntegration.fetch_health_data', return_value=['health data'])
    @patch('abdm_integrator.hip.views.health_information.ABDMCrypto.encrypt', return_value='encrypted')
    @patch('abdm_integrator.hip.views.health_information.requests.post')
    def test_process_health_information_multiple_care_contexts_error(self, *args):
        care_context_references = [self.care_context_reference, uuid.uuid4().hex]
        self._add_consent_artefact(self.consent_artefact_id, care_context_references=care_context_references)

        request_data = self._health_information_request_data(self.consent_artefact_id)
        health_information_request = self._add_health_information_request(
            self.consent_artefact_id,
            request_data['transactionId']
        )

        overall_transfer_status, care_contexts_status = HealthDataTransferProcessor(
            health_information_request,
            request_data['hiRequest']
        ).process()

        self.assertFalse(overall_transfer_status)
        self.assertEqual(len(care_contexts_status), len(care_context_references))
        for idx, status in enumerate(care_contexts_status):
            self.assertEqual(
                status,
                {
                    'careContextReference': care_context_references[idx],
                    'hiStatus': HealthInformationStatus.ERRORED,
                    'description': f'Linked Care Context not found for {care_context_references[idx]}'
                }
            )
        self._assert_for_health_data_transfer_single_page(health_information_request, care_contexts_status)

    @patch('abdm_integrator.integrations.HRPIntegration.fetch_health_data', return_value=['health data'])
    @patch('abdm_integrator.hip.views.health_information.ABDMCrypto.encrypt', return_value='encrypted')
    @patch('abdm_integrator.hip.views.health_information.requests.post')
    def test_process_health_information_transfer_multiple_care_contexts_partial_success(self, *args):
        care_context_references = [self.care_context_reference, uuid.uuid4().hex]
        request_data = self._health_information_request_data(self.consent_artefact_id)

        self._add_consent_artefact(self.consent_artefact_id, care_context_references=care_context_references)
        self._add_linked_care_context_data(care_context_references[0], [HealthInformationType.PRESCRIPTION])
        self._add_linked_care_context_data(care_context_references[1], [HealthInformationType.WELLNESS_RECORD])
        health_information_request = self._add_health_information_request(
            self.consent_artefact_id,
            request_data['transactionId']
        )

        overall_transfer_status, care_contexts_status = HealthDataTransferProcessor(
            health_information_request,
            request_data['hiRequest']
        ).process()

        self.assertFalse(overall_transfer_status)
        self.assertEqual(len(care_contexts_status), len(care_context_references))
        care_context_1_status = next(care_context_status for care_context_status in care_contexts_status
                                     if care_context_status['careContextReference'] == care_context_references[0])
        care_context_2_status = next(care_context_status for care_context_status in care_contexts_status
                                     if care_context_status['careContextReference'] == care_context_references[1])
        self.assertEqual(
            care_context_1_status,
            {
                'careContextReference': care_context_references[0],
                'hiStatus': HealthInformationStatus.DELIVERED,
                'description': 'Delivered'
            }
        )
        self.assertEqual(
            care_context_2_status,
            {
                'careContextReference': care_context_references[1],
                'hiStatus': HealthInformationStatus.ERRORED,
                'description': f'Validation failed for HI Types for care context: {care_context_references[1]}'
            }
        )
        self._assert_for_health_data_transfer_single_page(health_information_request, care_contexts_status)

    @patch('abdm_integrator.integrations.HRPIntegration.fetch_health_data', return_value=['health data'])
    @patch('abdm_integrator.hip.views.health_information.ABDMCrypto.encrypt', return_value='encrypted')
    @patch('abdm_integrator.hip.views.health_information.requests.post')
    @patch('abdm_integrator.hip.views.health_information.HealthDataTransferProcessor.entries_per_page', 1)
    def test_process_health_information_transfer_multi_page(self, *args):
        care_context_references = [self.care_context_reference, uuid.uuid4().hex]
        request_data = self._health_information_request_data(self.consent_artefact_id)

        self._add_consent_artefact(self.consent_artefact_id, care_context_references=care_context_references)
        self._add_linked_care_context_data(care_context_references[0], [HealthInformationType.PRESCRIPTION])
        self._add_linked_care_context_data(care_context_references[1], [HealthInformationType.DIAGNOSTIC_REPORT])

        health_information_request = self._add_health_information_request(
            self.consent_artefact_id,
            request_data['transactionId']
        )

        overall_transfer_status, care_contexts_status = HealthDataTransferProcessor(
            health_information_request,
            request_data['hiRequest'],
        ).process()
        self.assertTrue(overall_transfer_status)
        self.assertEqual(len(care_contexts_status), len(care_context_references))
        for idx, status in enumerate(care_contexts_status):
            self.assertEqual(
                status,
                {
                    'careContextReference': care_context_references[idx],
                    'hiStatus': HealthInformationStatus.DELIVERED,
                    'description': 'Delivered'
                }
            )

        results = HealthDataTransfer.objects.filter(
            health_information_request=health_information_request
        ).order_by('id')
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].page_number, 1)
        self.assertEqual(results[1].page_number, 2)
        self.assertEqual(results[0].care_contexts_status, [care_contexts_status[0]])
        self.assertEqual(results[1].care_contexts_status, [care_contexts_status[1]])
