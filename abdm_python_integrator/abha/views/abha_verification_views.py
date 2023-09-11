from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated

from abdm_python_integrator.abha.exceptions import ABHA_ERROR_MESSAGES, ABHA_IN_USE_ERROR_CODE
from abdm_python_integrator.abha.utils import abha_verification_util as abdm_util
from abdm_python_integrator.abha.utils.abha_verification_util import get_account_information
from abdm_python_integrator.abha.utils.decorators import required_request_params
from abdm_python_integrator.abha.utils.response_util import generate_invalid_req_response, parse_response
from abdm_python_integrator.settings import app_settings


@api_view(["GET"])
@permission_classes((IsAuthenticated,))
@authentication_classes((app_settings.AUTHENTICATION_CLASS,))
def get_auth_methods(request):
    health_id = request.query_params.get("health_id")
    if not health_id:
        error_msg = "Missing required parameter: health_id"
        return generate_invalid_req_response(error_msg)
    resp = abdm_util.search_by_health_id(health_id)
    auth_methods = resp.get("authMethods")
    resp = {"auth_methods": auth_methods}
    return parse_response(resp)


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
@authentication_classes((app_settings.AUTHENTICATION_CLASS,))
@required_request_params(["health_id", "auth_method"])
def generate_auth_otp(request):
    health_id = request.data.get("health_id")
    auth_method = request.data.get("auth_method")
    resp = abdm_util.generate_auth_otp(health_id, auth_method)
    return parse_response(resp)


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
@authentication_classes((app_settings.AUTHENTICATION_CLASS,))
@required_request_params(["txn_id", "otp"])
def confirm_with_mobile_otp(request):
    txn_id = request.data.get("txn_id")
    otp = request.data.get("otp")
    resp = abdm_util.confirm_with_mobile_otp(otp, txn_id)
    if "token" in resp:
        resp = {"status": "success", "txnId": txn_id, "user_token": resp.get("token")}
        resp.update(get_account_information(resp.get("user_token")))
    return parse_response(resp)


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
@authentication_classes((app_settings.AUTHENTICATION_CLASS,))
@required_request_params(["txn_id", "otp"])
def confirm_with_aadhaar_otp(request):
    txn_id = request.data.get("txn_id")
    otp = request.data.get("otp")
    resp = abdm_util.confirm_with_aadhaar_otp(otp, txn_id)
    if "token" in resp:
        resp = {"status": "success", "txnId": txn_id, "user_token": resp.get("token")}
        resp.update(get_account_information(resp.get("user_token")))
    return parse_response(resp)


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
@authentication_classes((app_settings.AUTHENTICATION_CLASS,))
@required_request_params(["health_id"])
def search_health_id(request):
    health_id = request.data.get("health_id")
    if app_settings.HRP_ABHA_REGISTERED_CHECK_CLASS is not None:
        if (app_settings.HRP_ABHA_REGISTERED_CHECK_CLASS().
                check_if_abha_registered(request.user, health_id)):
            return generate_invalid_req_response(ABHA_ERROR_MESSAGES[ABHA_IN_USE_ERROR_CODE],
                                                 error_code=ABHA_IN_USE_ERROR_CODE)
    resp = abdm_util.search_by_health_id(health_id)
    return parse_response(resp)


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
@authentication_classes((app_settings.AUTHENTICATION_CLASS,))
@required_request_params(["user_token"])
def get_health_card_png(request):
    user_token = request.data.get("user_token")
    return parse_response(abdm_util.get_health_card_png(user_token))


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
@authentication_classes((app_settings.AUTHENTICATION_CLASS,))
@required_request_params(["health_id"])
def get_existence_by_health_id(request):
    health_id = request.data.get("health_id")
    if app_settings.HRP_ABHA_REGISTERED_CHECK_CLASS is not None:
        if app_settings.HRP_ABHA_REGISTERED_CHECK_CLASS().check_if_abha_registered(request.user, health_id):
            return generate_invalid_req_response(ABHA_ERROR_MESSAGES[ABHA_IN_USE_ERROR_CODE],
                                                 error_code=ABHA_IN_USE_ERROR_CODE)
    resp = abdm_util.exists_by_health_id(health_id)
    if "status" in resp:
        resp = {"health_id": health_id, "exists": resp.get("status")}
    return parse_response(resp)
