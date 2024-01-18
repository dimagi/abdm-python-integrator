from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from abdm_integrator.abha.const import (
    AUTH_OTP_URL,
    CONFIRM_WITH_AADHAAR_OTP_URL,
    CONFIRM_WITH_MOBILE_OTP_URL,
    EXISTS_BY_HEALTH_ID,
    SEARCH_BY_HEALTH_ID_URL,
)
from abdm_integrator.abha.exceptions import INVALID_ABHA_ADDRESS_MESSAGE
from abdm_integrator.settings import app_settings


class TestABHAVerification(APITestCase):

    @classmethod
    def setUpClass(cls):
        cls.invalid_req_msg = "Unable to process the current request due to incorrect data entered."
        cls.user = User.objects.create_superuser(username='test_user', password='test')
        cls.token = Token.objects.create(user=cls.user)

    def setUp(self) -> None:
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token}')

    @staticmethod
    def _mock_abdm_http_post(url, payload):
        abdm_txn_id_mock = {"txnId": "1234"}
        return {
            SEARCH_BY_HEALTH_ID_URL: {"authMethods": ["MOBILE_OTP"]},
            AUTH_OTP_URL: abdm_txn_id_mock,
            CONFIRM_WITH_MOBILE_OTP_URL: abdm_txn_id_mock,
            CONFIRM_WITH_AADHAAR_OTP_URL: abdm_txn_id_mock,
            EXISTS_BY_HEALTH_ID: {"status": True}
        }.get(url)

    @staticmethod
    def _get_health_card_mock_response(**kwargs):
        health_card_response_mock = Mock()
        health_card_response_mock.status_code = 200
        health_card_response_mock.content = b'image'
        return health_card_response_mock

    def test_getting_auth_methods_success(self):
        with patch('abdm_integrator.utils.ABDMRequestHelper.abha_post',
                   side_effect=TestABHAVerification._mock_abdm_http_post):
            response = self.client.get(reverse("get_auth_methods"), {"health_id": "123456"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'auth_methods': ['MOBILE_OTP']})

    def test_getting_auth_methods_failure(self):
        response = self.client.get(reverse("get_auth_methods"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.invalid_req_msg, response.json().get("message"))

    def test_generate_auth_otp_success(self):
        with patch('abdm_integrator.utils.ABDMRequestHelper.abha_post',
                   side_effect=TestABHAVerification._mock_abdm_http_post):
            response = self.client.post(reverse("generate_auth_otp"),
                                        {"health_id": "123456", "auth_method": "MOBILE_OTP"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"txnId": "1234"})

    def test_generate_auth_otp_failure(self):
        response = self.client.post(reverse("generate_auth_otp"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.invalid_req_msg, response.json().get("message"))

    def test_confirm_with_mobile_otp_success(self):
        with patch('abdm_integrator.utils.ABDMRequestHelper.abha_post',
                   side_effect=TestABHAVerification._mock_abdm_http_post):
            response = self.client.post(reverse("confirm_with_mobile_otp"),
                                        {"txn_id": "123456", "otp": "1111"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"txnId": "1234"})

    def test_confirm_with_mobile_otp_failure(self):
        response = self.client.post(reverse("confirm_with_mobile_otp"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.invalid_req_msg, response.json().get("message"))

    def test_confirm_with_aadhaar_otp_success(self):
        with patch('abdm_integrator.utils.ABDMRequestHelper.abha_post',
                   side_effect=TestABHAVerification._mock_abdm_http_post):
            response = self.client.post(reverse("confirm_with_aadhaar_otp"),
                                        {"txn_id": "123456", "otp": "1111"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"txnId": "1234"})

    def test_confirm_with_aadhaar_otp_failure(self):
        response = self.client.post(reverse("confirm_with_aadhaar_otp"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.invalid_req_msg, response.json().get("message"))

    def test_search_health_id_success(self):
        with patch('abdm_integrator.utils.ABDMRequestHelper.abha_post',
                   side_effect=TestABHAVerification._mock_abdm_http_post):
            response = self.client.post(reverse("search_health_id"), {"health_id": "11113333"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"authMethods": ["MOBILE_OTP"]})

    def test_search_health_id_failure(self):
        response = self.client.post(reverse("search_health_id"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.invalid_req_msg, response.json().get("message"))

    @patch('abdm_integrator.utils.ABDMRequestHelper.get_access_token')
    def test_get_health_card_success(self, post_mock):
        post_mock.return_value = 'test'
        with patch('abdm_integrator.abha.utils.abha_verification.requests.get',
                   side_effect=TestABHAVerification._get_health_card_mock_response):
            response = self.client.post(reverse("get_health_card_png"), {"user_token": "fake_token"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"health_card": "aW1hZ2U="})

    def test_get_health_card_failure(self):
        response = self.client.post(reverse("get_health_card_png"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.invalid_req_msg, response.json().get("message"))

    def test_get_health_id_existence_check_success(self):
        with patch('abdm_integrator.utils.ABDMRequestHelper.abha_post',
                   side_effect=TestABHAVerification._mock_abdm_http_post):
            response = self.client.post(reverse("exists_by_health_id"), {"health_id": "user_1234"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'health_id': f'user_1234@{app_settings.X_CM_ID}', 'exists': True})

    def test_get_health_id_existence_check_validation_failure(self):
        with patch('abdm_integrator.utils.ABDMRequestHelper.abha_post',
                   side_effect=TestABHAVerification._mock_abdm_http_post):
            response = self.client.post(reverse("exists_by_health_id"), {"health_id": "_user1234"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json().get("message"), self.invalid_req_msg)
        self.assertEqual(response.json().get("details")[0]['message'], INVALID_ABHA_ADDRESS_MESSAGE)

    def test_get_health_id_existence_check_failure(self):
        response = self.client.post(reverse("exists_by_health_id"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.invalid_req_msg, response.json().get("message"))

    @classmethod
    def tearDownClass(cls) -> None:
        User.objects.all().delete()
