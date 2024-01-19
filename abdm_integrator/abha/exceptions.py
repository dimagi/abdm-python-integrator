from abdm_integrator.exceptions import APIErrorResponseHandler

ABHA_IN_USE_ERROR_CODE = 1001
ABHA_ERROR_MESSAGES = {
    ABHA_IN_USE_ERROR_CODE: 'Provided ABHA is already linked to another beneficiary!'
}

INVALID_AADHAAR_MESSAGE = "Aadhaar number is not valid"
INVALID_MOBILE_MESSAGE = "Mobile number is not valid"
INVALID_ABHA_ADDRESS_MESSAGE = "Abha address is not valid"


class AbhaError:
    CODE_PREFIX = '1'


abha_error_response_handler = APIErrorResponseHandler(AbhaError.CODE_PREFIX)
