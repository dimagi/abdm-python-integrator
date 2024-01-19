import json
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

import requests
from django.contrib.auth.models import User
from django.db import transaction
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.status import HTTP_200_OK, HTTP_202_ACCEPTED, HTTP_400_BAD_REQUEST
from rest_framework.test import APIClient, APITestCase

from abdm_integrator.const import AuthenticationMode, LinkRequestInitiator, LinkRequestStatus
from abdm_integrator.exceptions import (
    ERROR_CODE_INVALID,
    ERROR_CODE_REQUIRED,
    ERROR_CODE_REQUIRED_MESSAGE,
    STANDARD_ERRORS,
    ABDMGatewayError,
)
from abdm_integrator.hip.const import SMSOnNotifyStatus
from abdm_integrator.hip.exceptions import (
    DiscoveryMultiplePatientsFoundError,
    DiscoveryNoPatientFoundError,
    HIPError,
)
from abdm_integrator.hip.models import (
    HIPLinkRequest,
    LinkCareContext,
    LinkRequestDetails,
    PatientDiscoveryRequest,
    PatientLinkRequest,
)
from abdm_integrator.hip.views.care_contexts import (
    GatewayCareContextsDiscoverProcessor,
    GatewayCareContextsLinkConfirmProcessor,
    GatewayCareContextsLinkInitProcessor,
)
from abdm_integrator.tests.utils import APITestHelperMixin, generate_mock_response
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
        HIPLinkRequest.objects.all().delete()
        LinkRequestDetails.objects.all().delete()

    @classmethod
    def tearDownClass(cls):
        User.objects.all().delete()
        super().tearDownClass()

    @staticmethod
    def _link_care_context_sample_request_data():
        return {
            'accessToken': 'abcdefghi',
            'hip_id': '1001',
            'healthId': 'test@sbx',
            'patient': {
                'referenceNumber': 'Test_001',
                'display': 'Test User',
                'careContexts': [
                    {
                        'referenceNumber': str(uuid.uuid4()),
                        'display': 'Made a Test Visit',
                        'hiTypes': [
                            'Prescription', 'WellnessRecord'
                        ],
                        'additionalInfo': {
                            'domain': 'test',
                            'record_date': datetime.utcnow().isoformat()
                        }
                    }
                ]
            }
        }

    @staticmethod
    def _insert_link_request(request_data, user, gateway_request_id):
        link_request_details = LinkRequestDetails.objects.create(
            hip_id=request_data['hip_id'],
            patient_reference=request_data['patient']['referenceNumber'],
            patient_display=request_data['patient']['display'],
            initiated_by=LinkRequestInitiator.HIP,
            status=LinkRequestStatus.SUCCESS
        )
        HIPLinkRequest.objects.create(user=user, gateway_request_id=gateway_request_id,
                                      link_request_details=link_request_details)
        link_care_contexts = [LinkCareContext(reference=care_context['referenceNumber'],
                                              display=care_context['display'],
                                              health_info_types=care_context['hiTypes'],
                                              link_request_details=link_request_details)
                              for care_context in request_data['patient']['careContexts']]
        LinkCareContext.objects.bulk_create(link_care_contexts)

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

    def _assert_records_count_in_db(self, count=0):
        self.assertEqual(LinkRequestDetails.objects.all().count(), count)
        self.assertEqual(LinkCareContext.objects.all().count(), count)
        self.assertEqual(HIPLinkRequest.objects.all().count(), count)

    @patch('abdm_integrator.hip.views.care_contexts.process_care_context_link_notify')
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
        self._assert_records_count_in_db(1)
        link_request_details = LinkRequestDetails.objects.all()[0]
        self.assertEqual(link_request_details.patient_reference, request_data['patient']['referenceNumber'])
        self.assertEqual(link_request_details.hip_id, request_data['hip_id'])
        self.assertEqual(link_request_details.patient_display, request_data['patient']['display'])
        self.assertEqual(link_request_details.initiated_by, LinkRequestInitiator.HIP)
        hip_link_request = HIPLinkRequest.objects.all()[0]
        self.assertEqual(str(hip_link_request.gateway_request_id),
                         mocked_common_request_data.return_value['requestId'])
        self.assertEqual(hip_link_request.link_request_details, link_request_details)
        linked_care_context = LinkCareContext.objects.all()[0]
        self.assertEqual(linked_care_context.reference,
                         request_data['patient']['careContexts'][0]['referenceNumber'])
        self.assertEqual(linked_care_context.link_request_details, link_request_details)
        self.assertEqual(linked_care_context.health_info_types,
                         request_data['patient']['careContexts'][0]['hiTypes'])
        self.assertEqual(linked_care_context.additional_info,
                         request_data['patient']['careContexts'][0]['additionalInfo'])

    def test_link_care_context_authentication_error(self, *args):
        client = APIClient()
        request_data = self._link_care_context_sample_request_data()
        res = client.post(self.link_care_context_url, data=json.dumps(request_data),
                          content_type='application/json')
        self.assert_for_authentication_error(res, HIPError.CODE_PREFIX)
        self._assert_records_count_in_db(0)

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
        self._assert_records_count_in_db(0)

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
        self._assert_records_count_in_db(1)

    @patch('abdm_integrator.utils.requests.post')
    def test_link_care_context_gateway_error(self, mocked_post, *args):
        self.gateway_error_test(mocked_post, self.link_care_context_url,
                                self._link_care_context_sample_request_data())
        self._assert_records_count_in_db(0)

    @patch('abdm_integrator.utils.requests.post', side_effect=requests.Timeout)
    def test_link_care_context_service_unavailable_error(self, *args):
        client = APIClient(raise_request_exception=False)
        client.credentials(HTTP_AUTHORIZATION=f'Token {self.token}')
        request_data = self._link_care_context_sample_request_data()
        res = client.post(self.link_care_context_url, data=json.dumps(request_data),
                          content_type='application/json')
        self.assert_for_abdm_service_unavailable_error(res, HIPError.CODE_PREFIX)
        self._assert_records_count_in_db(0)


class TestPatientLinkCareContextAPI(APITestCase, APITestHelperMixin):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_superuser(username='test_user', password='test')
        cls.gateway_care_contexts_discover_url = reverse('gateway_care_contexts_discover')
        cls.gateway_care_contexts_link_init_url = reverse('gateway_care_contexts_link_init')
        cls.gateway_care_contexts_link_confirm_url = reverse('gateway_care_contexts_link_confirm')

    def setUp(self):
        # Client used to call Gateway facing APIs
        self.client.force_authenticate(self.user)

    def tearDown(self):
        LinkCareContext.objects.all().delete()
        PatientLinkRequest.objects.all().delete()
        LinkRequestDetails.objects.all().delete()
        PatientDiscoveryRequest.objects.all().delete()

    @classmethod
    def tearDownClass(cls):
        User.objects.all().delete()
        super().tearDownClass()

    @staticmethod
    def _discovery_request_data():
        return {
            'patient': {
                'id': 'test1@sbx',
                'name': 'Test User',
                'gender': 'M',
                'yearOfBirth': 1990,
                'verifiedIdentifiers': [
                    {
                        'type': 'MOBILE',
                        'value': '+91-8888899999'
                    },
                    {
                        'type': 'NDHM_HEALTH_NUMBER',
                        'value': '91-1111-1111-1111'
                    },
                    {
                        'type': 'HEALTH_ID',
                        'value': 'test1@sbx'
                    }
                ],
                'unverifiedIdentifiers': []
            },
            'requestId': str(uuid.uuid4()),
            'timestamp': datetime.utcnow().isoformat(),
            'transactionId': str(uuid.uuid4())
        }

    @staticmethod
    def _discovery_result():
        return {
            'referenceNumber': 'PT-101',
            'display': 'Test Patient',
            'careContexts': [
                {
                    'referenceNumber': 'CC-109',
                    'display': 'Visit 1',
                    'hiTypes': ['Prescription', 'OPConsultation'],
                    'additionalInfo': {
                        'domain': 'test',
                        'record_date': datetime.utcnow().isoformat()
                    }
                }
            ],
            'matchedBy': [
                'HEALTH_ID'
            ]
        }

    def _link_init_request_data(self):
        discovery_result = self._discovery_result()
        return {
            'requestId': str(uuid.uuid4()),
            'timestamp': datetime.utcnow().isoformat(),
            'transactionId': str(uuid.uuid4()),
            'patient': {
                'id': 'test1@sbx',
                'referenceNumber': discovery_result['referenceNumber'],
                'careContexts': [
                    {
                        'referenceNumber': discovery_result['careContexts'][0]['referenceNumber']
                    }
                ]
            }
        }

    def _insert_discovery_request(self, transaction_id, hip_id):
        patient_discovery_request = PatientDiscoveryRequest(
            transaction_id=transaction_id,
            hip_id=hip_id,
        )
        discovery_result = self._discovery_result()
        patient_discovery_request.patient_reference_number = discovery_result['referenceNumber']
        patient_discovery_request.patient_display = discovery_result['display']
        patient_discovery_request.care_contexts = discovery_result['careContexts']
        patient_discovery_request.save()
        return patient_discovery_request

    @staticmethod
    def _otp_response_success():
        return {
            'requestId': str(uuid.uuid4()),
            'timestamp': datetime.utcnow().isoformat(),
            'auth': {
                'transactionId': str(uuid.uuid4()),
                'mode': AuthenticationMode.MOBILE_OTP,
                'meta': {
                    'hint': None,
                    'expiry': (datetime.utcnow() + timedelta(minutes=10)).isoformat()
                }
            },
            'error': None,
            'resp': {
                'requestId': str(uuid.uuid4())
            }
        }

    @staticmethod
    def _otp_response_failure():
        return {
            'requestId': str(uuid.uuid4()),
            'timestamp': datetime.utcnow().isoformat(),
            'error': {
                'code': 1511,
                'message': 'Cannot process the request at the moment, please try later.'
            },
            'resp': {
                'requestId': str(uuid.uuid4())
            }
        }

    @staticmethod
    def _link_confirm_request_data():
        return {
            'requestId': str(uuid.uuid4()),
            'timestamp': datetime.utcnow().isoformat(),
            'confirmation': {
                'linkRefNumber': str(uuid.uuid4()),
                'token': '1',
            }
        }

    @transaction.atomic()
    def _insert_link_request_records(self, request_data, discovery_request):
        link_request_details = LinkRequestDetails.objects.create(
            patient_reference=request_data['patient']['referenceNumber'],
            patient_display=discovery_request.patient_display,
            hip_id=request_data['hip_id'],
            initiated_by=LinkRequestInitiator.PATIENT,
            status=LinkRequestStatus.PENDING,
        )
        otp_transaction_id = uuid.uuid4()
        PatientLinkRequest.objects.create(
            discovery_request=discovery_request,
            otp_transaction_id=otp_transaction_id,
            link_request_details=link_request_details
        )
        LinkCareContext.objects.bulk_create(
            self._get_link_care_contexts_to_insert(request_data, discovery_request, link_request_details)
        )
        return link_request_details

    def _get_link_care_contexts_to_insert(self, request_data, discovery_request, link_request_details):
        link_care_contexts = []
        for care_context in request_data['patient']['careContexts']:
            care_contexts_details = self._get_care_context_details(
                discovery_request,
                care_context['referenceNumber']
            )
            link_care_contexts.append(
                LinkCareContext(
                    reference=care_contexts_details['referenceNumber'],
                    display=care_contexts_details['display'],
                    health_info_types=care_contexts_details['hiTypes'],
                    additional_info=care_contexts_details['additionalInfo'],
                    link_request_details=link_request_details
                )
            )
        return link_care_contexts

    @staticmethod
    def _get_care_context_details(discovery_request, care_context_reference):
        return next(care_context for care_context in discovery_request.care_contexts
                    if care_context['referenceNumber'] == care_context_reference)

    @staticmethod
    def _verify_otp_response_success():
        return {
            'requestId': str(uuid.uuid4()),
            'timestamp': datetime.utcnow().isoformat(),
            'auth': {
                'accessToken': 'abcdefghijkl',
                'patient': None
            },
            'error': None,
            'resp': {
                'requestId': str(uuid.uuid4())
            }
        }

    @staticmethod
    def _verify_otp_response_failure():
        return {
            'requestId': str(uuid.uuid4()),
            'timestamp': datetime.utcnow().isoformat(),
            'auth': None,
            'error': {
                'code': 1441,
                'message': 'Invalid auth confirm request.'
            },
            'resp': {
                'requestId': str(uuid.uuid4())
            }
        }

    def _assert_discovery_task_failure(self, request_data, error_code):
        self.assertEqual(PatientDiscoveryRequest.objects.count(), 1)
        patient_discovery_request = PatientDiscoveryRequest.objects.all()[0]
        self.assertEqual(str(patient_discovery_request.transaction_id), request_data['transactionId'])
        self.assertEqual(str(patient_discovery_request.hip_id), request_data['hip_id'])
        self.assertIsNone(patient_discovery_request.patient_reference_number)
        self.assertIsNone(patient_discovery_request.patient_display)
        self.assertEqual(patient_discovery_request.care_contexts, [])
        self.assertEqual(
            patient_discovery_request.error,
            {'code': error_code, 'message': HIPError.CUSTOM_ERRORS[error_code]}
        )

    def _assert_link_request_records_count(self, count):
        self.assertEqual(PatientLinkRequest.objects.count(), count)
        self.assertEqual(LinkRequestDetails.objects.count(), count)
        self.assertEqual(LinkCareContext.objects.count(), count)

    def _assert_link_init_task_validation_failure(self, result, error_code):
        self._assert_link_request_records_count(0)
        self.assertEqual(
            result,
            {'code': error_code, 'message': HIPError.CUSTOM_ERRORS[error_code]}
        )

    @patch('abdm_integrator.hip.views.care_contexts.process_patient_care_context_discover_request')
    def test_gateway_care_contexts_discover_success(self, *args):
        request_data = self._discovery_request_data()
        res = self.client.post(
            self.gateway_care_contexts_discover_url,
            data=json.dumps(request_data),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, HTTP_202_ACCEPTED)

    def test_gateway_care_contexts_discover_validation_error(self):
        request_data = self._discovery_request_data()
        del request_data['patient']['name']
        res = self.client.post(
            self.gateway_care_contexts_discover_url,
            data=json.dumps(request_data),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, HTTP_400_BAD_REQUEST)
        json_res = res.json()
        self.assert_error(
            json_res['error'],
            int(f'{HIPError.CODE_PREFIX}{HTTP_400_BAD_REQUEST}'),
            STANDARD_ERRORS.get(HTTP_400_BAD_REQUEST)
        )

    @patch('abdm_integrator.hip.views.care_contexts.ABDMRequestHelper.gateway_post')
    @patch('abdm_integrator.hip.views.care_contexts.app_settings.HRP_INTEGRATION_CLASS.'
           'discover_patient_and_care_contexts')
    def test_discovery_task_success(self, mocked_discover_care_context, *args):
        discovery_result = self._discovery_result()
        mocked_discover_care_context.return_value = discovery_result
        request_data = self._discovery_request_data()
        request_data['hip_id'] = '1001'

        GatewayCareContextsDiscoverProcessor(request_data).process_request()

        self.assertEqual(PatientDiscoveryRequest.objects.count(), 1)
        patient_discovery_request = PatientDiscoveryRequest.objects.all()[0]
        self.assertEqual(str(patient_discovery_request.transaction_id), request_data['transactionId'])
        self.assertEqual(str(patient_discovery_request.hip_id), request_data['hip_id'])
        self.assertEqual(
            str(patient_discovery_request.patient_reference_number),
            discovery_result['referenceNumber']
        )
        self.assertEqual(patient_discovery_request.patient_display, discovery_result['display'])
        self.assertEqual(patient_discovery_request.care_contexts, discovery_result['careContexts'])
        self.assertIsNone(patient_discovery_request.error)

    @patch('abdm_integrator.hip.views.care_contexts.ABDMRequestHelper.gateway_post')
    @patch('abdm_integrator.hip.views.care_contexts.app_settings.HRP_INTEGRATION_CLASS.'
           'discover_patient_and_care_contexts')
    def test_discovery_task_no_patient_found(self, mocked_discover_care_context, *args):
        mocked_discover_care_context.side_effect = DiscoveryNoPatientFoundError()
        request_data = self._discovery_request_data()
        request_data['hip_id'] = '1001'
        GatewayCareContextsDiscoverProcessor(request_data).process_request()
        self._assert_discovery_task_failure(request_data, HIPError.CODE_PATIENT_NOT_FOUND)

    @patch('abdm_integrator.hip.views.care_contexts.ABDMRequestHelper.gateway_post')
    @patch('abdm_integrator.hip.views.care_contexts.app_settings.HRP_INTEGRATION_CLASS.'
           'discover_patient_and_care_contexts')
    def test_discovery_task_multiple_patients_found(self, mocked_discover_care_context, *args):
        mocked_discover_care_context.side_effect = DiscoveryMultiplePatientsFoundError()
        request_data = self._discovery_request_data()
        request_data['hip_id'] = '1001'
        GatewayCareContextsDiscoverProcessor(request_data).process_request()
        self._assert_discovery_task_failure(request_data, HIPError.CODE_MULTIPLE_PATIENTS_FOUND)

    @patch('abdm_integrator.hip.views.care_contexts.ABDMRequestHelper.gateway_post')
    @patch('abdm_integrator.hip.views.care_contexts.app_settings.HRP_INTEGRATION_CLASS.'
           'discover_patient_and_care_contexts')
    def test_discovery_task_internal_error(self, mocked_discover_care_context, *args):
        mocked_discover_care_context.side_effect = Exception()
        request_data = self._discovery_request_data()
        request_data['hip_id'] = '1001'
        GatewayCareContextsDiscoverProcessor(request_data).process_request()
        self._assert_discovery_task_failure(request_data, HIPError.CODE_INTERNAL_ERROR)

    @patch('abdm_integrator.hip.views.care_contexts.ABDMRequestHelper.gateway_post')
    @patch('abdm_integrator.hip.views.care_contexts.app_settings.HRP_INTEGRATION_CLASS.'
           'discover_patient_and_care_contexts')
    def test_discovery_task_care_contexts_already_linked(self, mocked_discover_care_context, *args):
        discovery_result = self._discovery_result()
        mocked_discover_care_context.return_value = discovery_result
        request_data = self._discovery_request_data()
        request_data['hip_id'] = '1001'
        link_request_details = LinkRequestDetails.objects.create(
            patient_reference=discovery_result['referenceNumber'],
            patient_display=discovery_result['display'],
            hip_id=request_data['hip_id'],
            status=LinkRequestStatus.SUCCESS
        )
        LinkCareContext.objects.create(
            reference=discovery_result['careContexts'][0]['referenceNumber'],
            display=discovery_result['careContexts'][0]['display'],
            health_info_types=discovery_result['careContexts'][0]['hiTypes'],
            additional_info=discovery_result['careContexts'][0]['additionalInfo'],
            link_request_details=link_request_details
        )

        GatewayCareContextsDiscoverProcessor(request_data).process_request()

        self.assertEqual(PatientDiscoveryRequest.objects.count(), 1)
        patient_discovery_request = PatientDiscoveryRequest.objects.all()[0]
        self.assertEqual(str(patient_discovery_request.transaction_id), request_data['transactionId'])
        self.assertEqual(str(patient_discovery_request.hip_id), request_data['hip_id'])
        self.assertEqual(
            str(patient_discovery_request.patient_reference_number),
            discovery_result['referenceNumber']
        )
        self.assertEqual(patient_discovery_request.patient_display, discovery_result['display'])
        self.assertEqual(patient_discovery_request.care_contexts, [])
        self.assertIsNone(patient_discovery_request.error)

    @patch('abdm_integrator.hip.views.care_contexts.process_patient_care_context_link_init_request')
    def test_gateway_care_context_link_init_success(self, *args):
        request_data = self._link_init_request_data()
        res = self.client.post(
            self.gateway_care_contexts_link_init_url,
            data=json.dumps(request_data),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, HTTP_202_ACCEPTED)

    def test_gateway_care_context_link_init_validation_error(self):
        request_data = self._link_init_request_data()
        del request_data['patient']['referenceNumber']
        res = self.client.post(
            self.gateway_care_contexts_link_init_url,
            data=json.dumps(request_data),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, HTTP_400_BAD_REQUEST)
        self.assert_error(
            res.json()['error'],
            int(f'{HIPError.CODE_PREFIX}{HTTP_400_BAD_REQUEST}'),
            STANDARD_ERRORS.get(HTTP_400_BAD_REQUEST)
        )

    @patch('abdm_integrator.hip.views.care_contexts.ABDMRequestHelper.gateway_post')
    @patch('abdm_integrator.hip.views.care_contexts.GatewayCareContextsLinkInitProcessor.send_otp_to_patient')
    def test_care_context_link_init_task_success(self, mocked_send_otp_patient, *args):
        otp_response = self._otp_response_success()
        mocked_send_otp_patient.return_value = otp_response
        request_data = self._link_init_request_data()
        request_data['hip_id'] = '1001'
        patient_discovery_request = self._insert_discovery_request(
            request_data['transactionId'],
            request_data['hip_id']
        )

        result = GatewayCareContextsLinkInitProcessor(request_data).process_request()

        self.assertIsNone(result)
        self._assert_link_request_records_count(1)
        patient_link_request = PatientLinkRequest.objects.all()[0]
        link_request_details = LinkRequestDetails.objects.all()[0]
        link_care_context = LinkCareContext.objects.all()[0]

        self.assertEqual(patient_link_request.discovery_request, patient_discovery_request)
        self.assertEqual(str(patient_link_request.otp_transaction_id), otp_response['auth']['transactionId'])
        self.assertEqual(patient_link_request.link_request_details, link_request_details)

        self.assertIsNotNone(link_request_details.link_reference)
        self.assertEqual(link_request_details.patient_reference, request_data['patient']['referenceNumber'])
        self.assertEqual(link_request_details.patient_display, patient_discovery_request.patient_display)
        self.assertEqual(link_request_details.hip_id, request_data['hip_id'])
        self.assertEqual(link_request_details.status, LinkRequestStatus.PENDING)
        self.assertEqual(link_request_details.initiated_by, LinkRequestInitiator.PATIENT)
        self.assertIsNone(link_request_details.error)

        discovered_care_context = patient_discovery_request.care_contexts[0]
        self.assertEqual(link_care_context.link_request_details, link_request_details)
        self.assertEqual(link_care_context.reference, discovered_care_context['referenceNumber'])
        self.assertEqual(link_care_context.display, discovered_care_context['display'])
        self.assertEqual(link_care_context.health_info_types, discovered_care_context['hiTypes'])
        self.assertEqual(link_care_context.additional_info, discovered_care_context['additionalInfo'])

    @patch('abdm_integrator.hip.views.care_contexts.ABDMRequestHelper.gateway_post')
    @patch('abdm_integrator.hip.views.care_contexts.GatewayCareContextsLinkInitProcessor.send_otp_to_patient')
    def test_care_context_link_init_task_discovery_request_not_found(self, mocked_send_otp_patient, *args):
        mocked_send_otp_patient.return_value = self._otp_response_success()
        request_data = self._link_init_request_data()
        request_data['hip_id'] = '1001'
        result = GatewayCareContextsLinkInitProcessor(request_data).process_request()
        self._assert_link_init_task_validation_failure(result, HIPError.CODE_DISCOVERY_REQUEST_NOT_FOUND)

    @patch('abdm_integrator.hip.views.care_contexts.ABDMRequestHelper.gateway_post')
    @patch('abdm_integrator.hip.views.care_contexts.GatewayCareContextsLinkInitProcessor.send_otp_to_patient')
    def test_care_context_link_init_task_discovery_request_patient_mismatch(self, mocked_send_otp_patient, *args):
        mocked_send_otp_patient.return_value = self._otp_response_success()
        request_data = self._link_init_request_data()
        request_data['patient']['referenceNumber'] = 'does-not-exist'
        request_data['hip_id'] = '1001'
        self._insert_discovery_request(request_data['transactionId'], request_data['hip_id'])
        result = GatewayCareContextsLinkInitProcessor(request_data).process_request()
        self._assert_link_init_task_validation_failure(result, HIPError.CODE_LINK_INIT_REQUEST_PATIENT_MISMATCH)

    @patch('abdm_integrator.hip.views.care_contexts.ABDMRequestHelper.gateway_post')
    @patch('abdm_integrator.hip.views.care_contexts.GatewayCareContextsLinkInitProcessor.send_otp_to_patient')
    def test_care_context_link_init_task_discovery_request_care_contexts_mismatch(
        self,
        mocked_send_otp_patient,
        *args
    ):
        mocked_send_otp_patient.return_value = self._otp_response_success()
        request_data = self._link_init_request_data()
        request_data['patient']['careContexts'][0]['referenceNumber'] = 'does-not-exist'
        request_data['hip_id'] = '1001'
        self._insert_discovery_request(request_data['transactionId'], request_data['hip_id'])
        result = GatewayCareContextsLinkInitProcessor(request_data).process_request()
        self._assert_link_init_task_validation_failure(
            result,
            HIPError.CODE_LINK_INIT_REQUEST_CARE_CONTEXTS_MISMATCH
        )

    @patch('abdm_integrator.hip.views.care_contexts.ABDMRequestHelper.gateway_post')
    @patch('abdm_integrator.hip.views.care_contexts.GatewayCareContextsLinkInitProcessor.send_otp_to_patient')
    def test_care_context_link_init_task_generate_otp_failed(self, mocked_send_otp_patient, *args):
        otp_response = self._otp_response_failure()
        mocked_send_otp_patient.return_value = self._otp_response_failure()
        request_data = self._link_init_request_data()
        request_data['hip_id'] = '1001'
        self._insert_discovery_request(request_data['transactionId'], request_data['hip_id'])

        GatewayCareContextsLinkInitProcessor(request_data).process_request()

        self._assert_link_request_records_count(1)
        link_request_details = LinkRequestDetails.objects.all()[0]
        error_message = (
            f"{HIPError.CUSTOM_ERRORS[HIPError.CODE_LINK_INIT_REQUEST_OTP_GENERATION_FAILED]}:"
            f" {otp_response['error'].get('message')}"
        )
        self.assertEqual(
            link_request_details.error,
            {'code': HIPError.CODE_LINK_INIT_REQUEST_OTP_GENERATION_FAILED,
             'message': error_message}
        )

    @patch('abdm_integrator.hip.views.care_contexts.process_patient_care_context_link_confirm_request')
    def test_gateway_care_context_link_confirm_success(self, *args):
        request_data = self._link_confirm_request_data()
        res = self.client.post(
            self.gateway_care_contexts_link_confirm_url,
            data=json.dumps(request_data),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, HTTP_202_ACCEPTED)

    @patch('abdm_integrator.hip.views.care_contexts.process_patient_care_context_link_confirm_request')
    def test_gateway_care_context_link_confirm_validation_error(self, *args):
        request_data = self._link_confirm_request_data()
        del request_data['confirmation']['token']
        res = self.client.post(
            self.gateway_care_contexts_link_confirm_url,
            data=json.dumps(request_data),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, HTTP_400_BAD_REQUEST)
        self.assert_error(
            res.json()['error'],
            int(f'{HIPError.CODE_PREFIX}{HTTP_400_BAD_REQUEST}'),
            STANDARD_ERRORS.get(HTTP_400_BAD_REQUEST)
        )

    @patch('abdm_integrator.hip.views.care_contexts.ABDMRequestHelper.gateway_post')
    @patch('abdm_integrator.hip.views.care_contexts.GatewayCareContextsLinkConfirmProcessor'
           '.verify_otp_from_patient')
    def test_link_confirm_task_success(self, mocked_verify_otp_response, *args):
        link_init_request_data = self._link_init_request_data()
        link_init_request_data['hip_id'] = '1001'
        patient_discovery_request = self._insert_discovery_request(
            link_init_request_data['transactionId'],
            link_init_request_data['hip_id']
        )
        link_request_details = self._insert_link_request_records(link_init_request_data, patient_discovery_request)

        request_data = self._link_confirm_request_data()
        request_data['confirmation']['linkRefNumber'] = link_request_details.link_reference
        request_data['hip_id'] = '1001'
        mocked_verify_otp_response.return_value = self._verify_otp_response_success()

        GatewayCareContextsLinkConfirmProcessor(request_data).process_request()

        self._assert_link_request_records_count(1)
        updated_link_request_details = LinkRequestDetails.objects.get(
            link_reference=link_request_details.link_reference
        )
        self.assertEqual(updated_link_request_details.status, LinkRequestStatus.SUCCESS)

    @patch('abdm_integrator.hip.views.care_contexts.ABDMRequestHelper.gateway_post')
    def test_link_confirm_task_link_request_not_found(self, *args):
        request_data = self._link_confirm_request_data()
        request_data['hip_id'] = '1001'
        result = GatewayCareContextsLinkConfirmProcessor(request_data).process_request()
        self.assertEqual(LinkRequestDetails.objects.count(), 0)
        error_code = HIPError.CODE_LINK_REQUEST_NOT_FOUND
        self.assertEqual(result, {'code': error_code, 'message': HIPError.CUSTOM_ERRORS.get(error_code)})

    @patch('abdm_integrator.hip.views.care_contexts.ABDMRequestHelper.gateway_post')
    @patch('abdm_integrator.hip.views.care_contexts.GatewayCareContextsLinkConfirmProcessor'
           '.verify_otp_from_patient')
    def test_link_confirm_task_verify_otp_failed(self, mocked_verify_otp_response, *args):
        link_init_request_data = self._link_init_request_data()
        link_init_request_data['hip_id'] = '1001'
        patient_discovery_request = self._insert_discovery_request(
            link_init_request_data['transactionId'],
            link_init_request_data['hip_id']
        )
        link_request_details = self._insert_link_request_records(link_init_request_data, patient_discovery_request)
        mocked_verify_otp_response.return_value = self._verify_otp_response_failure()

        request_data = self._link_confirm_request_data()
        request_data['confirmation']['linkRefNumber'] = link_request_details.link_reference
        request_data['hip_id'] = '1001'

        GatewayCareContextsLinkConfirmProcessor(request_data).process_request()

        self._assert_link_request_records_count(1)
        updated_link_request_details = LinkRequestDetails.objects.get(
            link_reference=link_request_details.link_reference
        )
        self.assertEqual(updated_link_request_details.status, LinkRequestStatus.ERROR)
        error_message = (
            f"{HIPError.CUSTOM_ERRORS[HIPError.CODE_LINK_CONFIRM_OTP_VERIFICATION_FAILED]}:"
            f" {mocked_verify_otp_response.return_value['error'].get('message')}"
        )
        self.assertEqual(
            updated_link_request_details.error,
            {'code': HIPError.CODE_LINK_CONFIRM_OTP_VERIFICATION_FAILED, 'message': error_message}
        )

    @patch('abdm_integrator.utils.requests.post')
    @patch('abdm_integrator.hip.views.care_contexts.GatewayCareContextsLinkConfirmProcessor'
           '.verify_otp_from_patient')
    def test_link_confirm_task_gateway_error(self, mocked_verify_otp_response, mocked_post, *args):
        link_init_request_data = self._link_init_request_data()
        link_init_request_data['hip_id'] = '1001'
        patient_discovery_request = self._insert_discovery_request(
            link_init_request_data['transactionId'],
            link_init_request_data['hip_id']
        )
        link_request_details = self._insert_link_request_records(link_init_request_data, patient_discovery_request)
        mocked_verify_otp_response.return_value = self._verify_otp_response_success()
        gateway_error = {'error': {'code': 2500, 'message': 'Invalid request'}}
        mocked_post.return_value = generate_mock_response(HTTP_400_BAD_REQUEST, gateway_error)

        request_data = self._link_confirm_request_data()
        request_data['confirmation']['linkRefNumber'] = link_request_details.link_reference
        request_data['hip_id'] = '1001'

        GatewayCareContextsLinkConfirmProcessor(request_data).process_request()

        self._assert_link_request_records_count(1)
        updated_link_request_details = LinkRequestDetails.objects.get(
            link_reference=link_request_details.link_reference
        )
        self.assertEqual(updated_link_request_details.status, LinkRequestStatus.ERROR)
        self.assert_error(
            updated_link_request_details.error,
            gateway_error['error']['code'],
            ABDMGatewayError.error_message
        )
        self.assert_error_details(
            updated_link_request_details.error['details'][0],
            ABDMGatewayError.detail_code,
            gateway_error['error']['message'], None
        )


class TestPatientSMSNotifyAPI(APITestCase, APITestHelperMixin):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_superuser(username='test_user', password='test')
        cls.token = Token.objects.create(user=cls.user)
        cls.patient_sms_notify_url = reverse('patient_sms_notify')

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token}')

    @classmethod
    def tearDownClass(cls):
        User.objects.all().delete()
        super().tearDownClass()

    @staticmethod
    def _patient_sms_notify_request_data():
        return {
            'phoneNo': '9988776655',
            'hip': {
                'id': 'TEST-HIP'
            }
        }

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

    @patch('abdm_integrator.user_auth.views.ABDMRequestHelper.gateway_post', return_value={})
    @patch('abdm_integrator.user_auth.views.ABDMRequestHelper.common_request_data')
    def test_patient_sms_notify_success(self, mocked_common_request_data, *args):
        mocked_common_request_data.return_value = {
            'requestId': str(uuid.uuid4()),
            'timestamp': datetime.utcnow().isoformat()
        }
        callback_response = {
            'status': SMSOnNotifyStatus.ACKNOWLEDGED
        }
        self._mock_callback_response_with_cache(
            mocked_common_request_data.return_value['requestId'], callback_response
        )
        request_data = self._patient_sms_notify_request_data()
        res = self.client.post(self.patient_sms_notify_url, data=json.dumps(request_data),
                               content_type='application/json')
        self.assertEqual(res.status_code, HTTP_200_OK)
        self.assertEqual(res.json()['status'], True)

    @patch('abdm_integrator.user_auth.views.ABDMRequestHelper.gateway_post', return_value={})
    @patch('abdm_integrator.user_auth.views.ABDMRequestHelper.common_request_data')
    def test_patient_sms_notify_failure(self, mocked_common_request_data, *args):
        mocked_common_request_data.return_value = {
            'requestId': str(uuid.uuid4()),
            'timestamp': datetime.utcnow().isoformat()
        }
        callback_response = {
            'status': SMSOnNotifyStatus.ERRORED
        }
        self._mock_callback_response_with_cache(
            mocked_common_request_data.return_value['requestId'], callback_response
        )
        request_data = self._patient_sms_notify_request_data()
        res = self.client.post(
            self.patient_sms_notify_url,
            data=json.dumps(request_data),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, HTTP_200_OK)
        self.assertEqual(res.json()['status'], False)

    def test_patient_sms_notify_authentication_error(self, *args):
        client = APIClient()
        request_data = self._patient_sms_notify_request_data()
        res = client.post(
            self.patient_sms_notify_url,
            data=json.dumps(request_data),
            content_type='application/json'
        )
        self.assert_for_authentication_error(res, HIPError.CODE_PREFIX)

    def test_patient_sms_notify_validation_error(self, *args):
        request_data = self._patient_sms_notify_request_data()
        del request_data['phoneNo']
        res = self.client.post(
            self.patient_sms_notify_url,
            data=json.dumps(request_data),
            content_type='application/json'
        )
        json_res = res.json()
        self.assertEqual(res.status_code, HTTP_400_BAD_REQUEST)
        self.assert_error(
            json_res['error'],
            int(f'{HIPError.CODE_PREFIX}{HTTP_400_BAD_REQUEST}'),
            STANDARD_ERRORS.get(HTTP_400_BAD_REQUEST)
        )
        self.assertEqual(len(json_res['error']['details']), 1)
        self.assert_error_details(
            json_res['error']['details'][0], ERROR_CODE_REQUIRED,
            ERROR_CODE_REQUIRED_MESSAGE,
            'phoneNo'
        )

    @patch('abdm_integrator.utils.requests.post')
    def test_patient_sms_notify_gateway_error(self, mocked_post, *args):
        self.gateway_error_test(
            mocked_post,
            self.patient_sms_notify_url,
            self._patient_sms_notify_request_data()
        )

    @patch('abdm_integrator.utils.requests.post', side_effect=requests.Timeout)
    def test_patient_sms_notify_service_unavailable_error(self, *args):
        client = APIClient(raise_request_exception=False)
        client.credentials(HTTP_AUTHORIZATION=f'Token {self.token}')
        request_data = self._patient_sms_notify_request_data()
        res = client.post(
            self.patient_sms_notify_url,
            data=json.dumps(request_data),
            content_type='application/json'
        )
        self.assert_for_abdm_service_unavailable_error(res, HIPError.CODE_PREFIX)
