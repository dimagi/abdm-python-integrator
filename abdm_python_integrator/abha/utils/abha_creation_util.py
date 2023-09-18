import re

from abdm_python_integrator.abha.const import (
    CREATE_HEALTH_ID_URL,
    GENERATE_AADHAAR_OTP_URL,
    GENERATE_MOBILE_OTP_URL,
    VERIFY_AADHAAR_OTP_URL,
    VERIFY_MOBILE_OTP_URL,
)
from abdm_python_integrator.utils import ABDMRequestHelper


def generate_aadhaar_otp(aadhaar_number):
    payload = {"aadhaar": str(aadhaar_number)}
    return ABDMRequestHelper().abha_post(GENERATE_AADHAAR_OTP_URL, payload)


def generate_mobile_otp(mobile_number, txnid):
    payload = {"mobile": str(mobile_number), "txnId": txnid}
    return ABDMRequestHelper().abha_post(GENERATE_MOBILE_OTP_URL, payload)


def verify_aadhar_otp(otp, txnid):
    payload = {"otp": str(otp), "txnId": txnid}
    return ABDMRequestHelper().abha_post(VERIFY_AADHAAR_OTP_URL, payload)


def verify_mobile_otp(otp, txnid):
    payload = {"otp": str(otp), "txnId": txnid}
    return ABDMRequestHelper().abha_post(VERIFY_MOBILE_OTP_URL, payload)


def create_health_id(txnid, health_id=None):
    """
    Created ABHA Health ID of the user.
    Info about what things are already authenticated in the ABHA creation
    flow is tracked using txnId.
    Demographic information of user such as name, address, age, etc. are
    fetched from the Aadhaar server by ABDM and used internally in Health ID creation.
    """
    payload = {
        "txnId": txnid
    }
    if health_id:
        payload.update({"healthId": health_id})
    return ABDMRequestHelper().abha_post(CREATE_HEALTH_ID_URL, payload)


def validate_aadhaar_number(aadhaar_number):
    return bool(re.match(r"^(\d{12}|\d{16})$", aadhaar_number))


def validate_mobile_number(mobile_number):
    return bool(re.match(r"^(\+91)?\d{10}$", mobile_number))
