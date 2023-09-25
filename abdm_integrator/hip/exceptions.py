from abdm_integrator.exceptions import APIErrorResponseHandler


class HIPError:
    CODE_PREFIX = '3'

    CUSTOM_ERRORS = {}


hip_error_response_handler = APIErrorResponseHandler(HIPError.CODE_PREFIX)
hip_gateway_error_response_handler = APIErrorResponseHandler(HIPError.CODE_PREFIX, error_details=False)
