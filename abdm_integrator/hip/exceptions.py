from abdm_integrator.exceptions import APIErrorResponseHandler


class HIPError:
    CODE_PREFIX = '3'

    CODE_CARE_CONTEXT_ALREADY_LINKED = 3420
    CUSTOM_ERRORS = {
        CODE_CARE_CONTEXT_ALREADY_LINKED: '{} care contexts are already linked'
    }


hip_error_response_handler = APIErrorResponseHandler(HIPError.CODE_PREFIX)
hip_gateway_error_response_handler = APIErrorResponseHandler(HIPError.CODE_PREFIX, error_details=False)
