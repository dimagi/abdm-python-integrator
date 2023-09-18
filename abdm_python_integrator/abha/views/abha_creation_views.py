from django.utils.decorators import method_decorator

from abdm_python_integrator.abha.utils import abha_creation_util as abdm_util
from abdm_python_integrator.abha.utils.decorators import required_request_params
from abdm_python_integrator.abha.utils.response_util import parse_response
from abdm_python_integrator.abha.views.base import ABHABaseView
from abdm_python_integrator.settings import app_settings


class GenerateAadhaarOTP(ABHABaseView):

    @method_decorator(required_request_params(["aadhaar"]))
    def post(self, request, format=None):
        aadhaar_number = request.data.get("aadhaar")
        raw_response = abdm_util.generate_aadhaar_otp(aadhaar_number)
        return parse_response(raw_response)


class GenerateMobileOTP(ABHABaseView):

    @method_decorator(required_request_params(["txn_id", "mobile_number"]))
    def post(self, request, format=None):
        txn_id = request.data.get("txn_id")
        mobile_number = request.data.get("mobile_number")
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

    @method_decorator(required_request_params(["txn_id", "otp"]))
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
