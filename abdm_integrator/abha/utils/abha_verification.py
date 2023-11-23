import base64

import requests

from abdm_integrator.abha.const import (
    ACCOUNT_INFORMATION_URL,
    AUTH_OTP_URL,
    CONFIRM_WITH_AADHAAR_OTP_URL,
    CONFIRM_WITH_MOBILE_OTP_URL,
    EXISTS_BY_HEALTH_ID,
    HEALTH_CARD_PNG_FORMAT,
    SEARCH_BY_HEALTH_ID_URL,
)
from abdm_integrator.exceptions import ABDMGatewayError, ABDMServiceUnavailable
from abdm_integrator.settings import app_settings
from abdm_integrator.utils import ABDMRequestHelper, _get_json_from_resp


def generate_auth_otp(health_id, auth_method):
    payload = {"authMethod": auth_method, "healthid": health_id}
    return ABDMRequestHelper().abha_post(AUTH_OTP_URL, payload)


def confirm_with_mobile_otp(otp, txn_id):
    payload = {"otp": otp, "txnId": txn_id}
    return ABDMRequestHelper().abha_post(CONFIRM_WITH_MOBILE_OTP_URL, payload)


def confirm_with_aadhaar_otp(otp, txn_id):
    payload = {"otp": otp, "txnId": txn_id}
    return ABDMRequestHelper().abha_post(CONFIRM_WITH_AADHAAR_OTP_URL, payload)


def get_account_information(x_token):
    additional_headers = {"X-Token": f"Bearer {x_token}"}
    return ABDMRequestHelper().abha_get(ACCOUNT_INFORMATION_URL, additional_headers)


def search_by_health_id(health_id):
    payload = {"healthId": health_id}
    return ABDMRequestHelper().abha_post(SEARCH_BY_HEALTH_ID_URL, payload)


def get_health_card_png(user_token):
    headers = {"Content-Type": "application/json; charset=UTF-8"}
    token = ABDMRequestHelper().get_access_token()
    headers.update({"Authorization": "Bearer {}".format(token), "X-Token": f"Bearer {user_token}"})
    try:
        resp = requests.get(url=app_settings.ABHA_URL + HEALTH_CARD_PNG_FORMAT, headers=headers, stream=True)
        resp.raise_for_status()
        return {"health_card": base64.b64encode(resp.content)}
    except requests.Timeout:
        raise ABDMServiceUnavailable()
    except requests.HTTPError as err:
        error = _get_json_from_resp(err.response)
        detail_message = error['details'][0]['message'] if error.get('details') else error.get('message')
        raise ABDMGatewayError(error.get('code'), detail_message)


def exists_by_health_id(health_id):
    payload = {"healthId": health_id}
    return ABDMRequestHelper().abha_post(EXISTS_BY_HEALTH_ID, payload)
