import json
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from rest_framework.reverse import reverse
from rest_framework.status import HTTP_202_ACCEPTED, HTTP_400_BAD_REQUEST, HTTP_401_UNAUTHORIZED
from rest_framework.test import APIClient, APITestCase

from abdm_integrator.const import ConsentStatus
from abdm_integrator.exceptions import STANDARD_ERRORS
from abdm_integrator.hip.exceptions import HIPError
from abdm_integrator.hip.models import ConsentArtefact
from abdm_integrator.hip.tasks import _process_hip_expired_consents
from abdm_integrator.hip.views.consents import GatewayConsentRequestNotifyProcessor
from abdm_integrator.tests.utils import APITestHelperMixin


class TestHIPGatewayConsentNotifyAPI(APITestCase, APITestHelperMixin):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_superuser(username='test_user', password='test')
        cls.gateway_consent_request_notify_request_url = reverse('gateway_consent_request_notify_hip')

    def setUp(self):
        # Client used to call Gateway facing APIs
        self.client.force_authenticate(self.user)
        self.consent_artefact_id = uuid.uuid4().hex

    @staticmethod
    def _consent_request_notify_request_data(consent_artefact_id, status=ConsentStatus.GRANTED,
                                             expiry_datetime=None):
        if expiry_datetime is None:
            expiry_datetime = (datetime.utcnow() + timedelta(days=1)).isoformat()
        consent_detail = None
        if status == ConsentStatus.GRANTED:
            consent_detail = {
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
                        'careContextReference': 'CC-101'
                    }
                ]
            }
        return {
            'notification': {
                'consentDetail': consent_detail,
                'status': status,
                'signature': 'FoGgsGBISA7jm/+Nxs7W+DyJTd==' if status == ConsentStatus.GRANTED else None,
                'consentId': consent_artefact_id,
                'grantAcknowledgement': False
            },
            'requestId': uuid.uuid4().hex,
            'timestamp': datetime.utcnow().isoformat()
        }

    @staticmethod
    def _add_consent_artefact(consent_notify_request_data):
        artefact = ConsentArtefact.objects.create(
            artefact_id=consent_notify_request_data['notification']['consentId'],
            signature=consent_notify_request_data['notification']['signature'],
            details=consent_notify_request_data['notification']['consentDetail'],
            expiry_date=consent_notify_request_data['notification']['consentDetail']['permission']['dataEraseAt'],
            grant_acknowledgement=consent_notify_request_data['notification']['grantAcknowledgement']
        )
        return artefact

    def tearDown(self):
        ConsentArtefact.objects.all().delete()

    @classmethod
    def tearDownClass(cls):
        User.objects.all().delete()
        super().tearDownClass()

    @patch('abdm_integrator.hip.views.consents.process_hip_consent_notification_request')
    def test_gateway_consent_request_notify_success(self, *args):
        request_data = self._consent_request_notify_request_data(self.consent_artefact_id)

        res = self.client.post(
            self.gateway_consent_request_notify_request_url,
            data=json.dumps(request_data),
            content_type='application/json'
        )

        self.assertEqual(res.status_code, HTTP_202_ACCEPTED)

    @patch('abdm_integrator.hip.views.consents.process_hip_consent_notification_request')
    def test_gateway_consent_request_notify_authentication_error(self, *args):
        request_data = self._consent_request_notify_request_data(self.consent_artefact_id)

        res = APIClient().post(
            self.gateway_consent_request_notify_request_url,
            data=json.dumps(request_data),
            content_type='application/json'
        )

        self.assertEqual(res.status_code, HTTP_401_UNAUTHORIZED)

    @patch('abdm_integrator.hip.views.consents.process_hip_consent_notification_request')
    def test_gateway_consent_request_notify_validation_error(self, *args):
        request_data = self._consent_request_notify_request_data(self.consent_artefact_id)
        del request_data['notification']['consentDetail']['permission']

        res = self.client.post(
            self.gateway_consent_request_notify_request_url,
            data=json.dumps(request_data),
            content_type='application/json'
        )

        self.assertEqual(res.status_code, HTTP_400_BAD_REQUEST)
        self.assert_error(
            res.json()['error'],
            int(f'{HIPError.CODE_PREFIX}{HTTP_400_BAD_REQUEST}'),
            STANDARD_ERRORS.get(HTTP_400_BAD_REQUEST),
        )

    @patch('abdm_integrator.hip.views.consents.ABDMRequestHelper.gateway_post')
    def test_consent_request_notify_processor_granted(self, *args):
        request_data = self._consent_request_notify_request_data(self.consent_artefact_id)

        GatewayConsentRequestNotifyProcessor(request_data).process_request()

        consent_artefact = ConsentArtefact.objects.get(artefact_id=self.consent_artefact_id)
        consent_artefact.details = request_data['notification']['consentDetail']
        consent_artefact.expiry_date = request_data['notification']['consentDetail']['permission']['dataEraseAt']
        consent_artefact.grant_acknowledgement = bool(request_data['notification']['grantAcknowledgement'])
        consent_artefact.signature = request_data['notification']['signature']

    @patch('abdm_integrator.hip.views.consents.ABDMRequestHelper.gateway_post')
    def test_consent_request_notify_processor_revoked(self, *args):
        artefact_data = self._consent_request_notify_request_data(self.consent_artefact_id)
        self._add_consent_artefact(artefact_data)
        request_data = self._consent_request_notify_request_data(self.consent_artefact_id, ConsentStatus.REVOKED)

        GatewayConsentRequestNotifyProcessor(request_data).process_request()

        with self.assertRaises(ConsentArtefact.DoesNotExist):
            ConsentArtefact.objects.get(artefact_id=self.consent_artefact_id)

    @patch('abdm_integrator.hip.views.consents.ABDMRequestHelper.gateway_post')
    def test_consent_request_notify_processor_expired(self, *args):
        artefact_data = self._consent_request_notify_request_data(self.consent_artefact_id)
        self._add_consent_artefact(artefact_data)
        request_data = self._consent_request_notify_request_data(self.consent_artefact_id, ConsentStatus.EXPIRED)

        GatewayConsentRequestNotifyProcessor(request_data).process_request()

        with self.assertRaises(ConsentArtefact.DoesNotExist):
            ConsentArtefact.objects.get(artefact_id=self.consent_artefact_id)

    def test_consent_request_expiry_processor(self, *args):
        expiry_datetime = (datetime.utcnow() - timedelta(minutes=1)).isoformat()
        artefact_data = self._consent_request_notify_request_data(
            self.consent_artefact_id,
            expiry_datetime=expiry_datetime
        )
        self._add_consent_artefact(artefact_data)

        _process_hip_expired_consents()

        with self.assertRaises(ConsentArtefact.DoesNotExist):
            ConsentArtefact.objects.get(artefact_id=self.consent_artefact_id)
