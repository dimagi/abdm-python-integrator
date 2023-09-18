from unittest.mock import patch

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from abdm_python_integrator.abha.const import (
    CREATE_HEALTH_ID_URL,
    GENERATE_AADHAAR_OTP_URL,
    GENERATE_MOBILE_OTP_URL,
    VERIFY_AADHAAR_OTP_URL,
    VERIFY_MOBILE_OTP_URL,
)
from abdm_python_integrator.abha.exceptions import INVALID_AADHAAR_MESSAGE, INVALID_MOBILE_MESSAGE


class TestABHACreation(APITestCase):

    @classmethod
    def setUpClass(cls):
        cls.invalid_req_msg = "Unable to process the current request due to incorrect data entered."
        cls.user = User.objects.create_superuser(username='test_user', password='test')

    def setUp(self) -> None:
        self.client.force_authenticate(user=self.user)

    @staticmethod
    def _mock_abdm_http_post(url, payload):
        abdm_txn_id_mock = {"txnId": "1234"}
        return {
            GENERATE_AADHAAR_OTP_URL: abdm_txn_id_mock,
            VERIFY_MOBILE_OTP_URL: abdm_txn_id_mock,
            VERIFY_AADHAAR_OTP_URL: abdm_txn_id_mock,
            GENERATE_MOBILE_OTP_URL: abdm_txn_id_mock,
            CREATE_HEALTH_ID_URL: {"token": "1122", "refreshToken": "1133", "health_id": "123-456",
                                   "txnId": "1234", "new": 'true'},
        }.get(url)

    def test_aadhaar_otp_generation_success(self):
        abdm_txn_id_mock = {"txnId": "1234"}
        with patch('abdm_python_integrator.utils.ABDMRequestHelper.abha_post',
                   side_effect=self._mock_abdm_http_post):
            response = self.client.post(reverse("generate_aadhaar_otp"), {"aadhaar": "123412341234"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), abdm_txn_id_mock)

    def test_aadhaar_otp_generation_failure(self):
        response = self.client.post(reverse("generate_aadhaar_otp"), {"pan": "123456"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.invalid_req_msg, response.json().get("message"))

    def test_aadhaar_otp_generation_invalid_aadhaar(self):
        response = self.client.post(reverse("generate_aadhaar_otp"), {"aadhaar": "123456"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.invalid_req_msg, response.json().get("message"))
        self.assertEqual(INVALID_AADHAAR_MESSAGE, response.json()["details"][0]["message"])

    def test_mobile_otp_generation_success(self):
        abdm_txn_id_mock = {"txnId": "1234"}
        with patch('abdm_python_integrator.utils.ABDMRequestHelper.abha_post',
                   side_effect=self._mock_abdm_http_post):
            response = self.client.post(reverse("generate_mobile_otp"),
                                        {"txn_id": "1234", "mobile_number": "9999988888"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), abdm_txn_id_mock)

    def test_mobile_otp_generation_failure(self):
        response = self.client.post(reverse("generate_mobile_otp"), {"pan": "123456"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.invalid_req_msg, response.json().get("message"))

    def test_mobile_otp_generation_invalid_mobile(self):
        response = self.client.post(reverse("generate_mobile_otp"),
                                    {"txn_id": "1234", "mobile_number": "a999988888"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.invalid_req_msg, response.json().get("message"))
        self.assertEqual(INVALID_MOBILE_MESSAGE, response.json()["details"][0]["message"])

    def test_aadhaar_otp_verification_success(self):
        abdm_txn_id_mock = {"txnId": "1234"}
        with patch('abdm_python_integrator.utils.ABDMRequestHelper.abha_post',
                   side_effect=self._mock_abdm_http_post):
            response = self.client.post(reverse("verify_aadhaar_otp"),
                                        {"txn_id": "1234", "otp": "1111"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), abdm_txn_id_mock)

    def test_aadhaar_otp_verification_failure(self):
        response = self.client.post(reverse("verify_aadhaar_otp"), {"pan": "123456"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.invalid_req_msg, response.json().get("message"))

    def test_mobile_otp_verification_success(self):
        with patch('abdm_python_integrator.utils.ABDMRequestHelper.abha_post',
                   side_effect=self._mock_abdm_http_post):
            response = self.client.post(reverse("verify_mobile_otp"),
                                        {"txn_id": "1234", "otp": "1111", "health_id": "123-456"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"health_id": "123-456", "txnId": "1234", "user_token": "1122",
                                           "exists_on_abdm": False})

    def test_mobile_otp_verification_failure(self):
        response = self.client.post(reverse("verify_mobile_otp"), {"pan": "123456"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.invalid_req_msg, response.json().get("message"))

    @classmethod
    def tearDownClass(cls) -> None:
        User.objects.all().delete()
