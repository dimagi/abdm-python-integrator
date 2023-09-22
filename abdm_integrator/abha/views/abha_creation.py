from django.utils.decorators import method_decorator

from abdm_integrator.abha.exceptions import INVALID_AADHAAR_MESSAGE, INVALID_MOBILE_MESSAGE
from abdm_integrator.abha.utils import abha_creation as abdm_util
from abdm_integrator.abha.utils.abha_creation import validate_aadhaar_number, validate_mobile_number
from abdm_integrator.abha.utils.decorators import required_request_params
from abdm_integrator.abha.utils.response import get_bad_response, parse_response
from abdm_integrator.abha.views.base import ABHABaseView
from abdm_integrator.settings import app_settings


class GenerateAadhaarOTP(ABHABaseView):

    @method_decorator(required_request_params(["aadhaar"]))
    def post(self, request, format=None):
        aadhaar_number = request.data.get("aadhaar")
        if not validate_aadhaar_number(aadhaar_number):
            return get_bad_response(INVALID_AADHAAR_MESSAGE)
        raw_response = abdm_util.generate_aadhaar_otp(aadhaar_number)
        return parse_response(raw_response)


class GenerateMobileOTP(ABHABaseView):

    @method_decorator(required_request_params(["txn_id", "mobile_number"]))
    def post(self, request, format=None):
        txn_id = request.data.get("txn_id")
        mobile_number = request.data.get("mobile_number")
        if not validate_mobile_number(mobile_number):
            return get_bad_response(INVALID_MOBILE_MESSAGE)
        resp = abdm_util.generate_mobile_otp(mobile_number, txn_id)
        return parse_response(resp)


class VerifyAadhaarOTP(ABHABaseView):

    @method_decorator(required_request_params(["txn_id", "otp"]))
    def post(self, request, format=None):
        txn_id = request.data.get("txn_id")
        otp = request.data.get("otp")
        resp = abdm_util.verify_aadhar_otp(otp, txn_id)
        return parse_response(resp)


class VerifyMobileOTP(ABHABaseView):

    @method_decorator(required_request_params(["txn_id", "otp", "health_id"]))
    def post(self, request, format=None):
        txn_id = request.data.get("txn_id")
        otp = request.data.get("otp")
        health_id = request.data.get("health_id")
        resp = abdm_util.verify_mobile_otp(otp, txn_id)
        if resp and "txnId" in resp:
            resp = abdm_util.create_health_id(txn_id, health_id)
            resp["user_token"] = resp.pop("token")
            resp.pop("refreshToken")
            resp["exists_on_abdm"] = not resp.pop("new")
            if app_settings.HRP_ABHA_REGISTERED_CHECK_CLASS is not None:
                resp["exists_on_hq"] = (app_settings.HRP_ABHA_REGISTERED_CHECK_CLASS().
                                        check_if_abha_registered(request.user, health_id))
        return parse_response(resp)
