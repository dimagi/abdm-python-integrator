from abdm_integrator.exceptions import APIErrorResponseHandler


class UserAuthError:
    CODE_PREFIX = '1'
    CODE_GATEWAY_CALLBACK_TIMEOUT = 1555

    CUSTOM_ERRORS = {
        CODE_GATEWAY_CALLBACK_TIMEOUT: 'Gateway callback response timeout'
    }


user_auth_error_response_handler = APIErrorResponseHandler(UserAuthError.CODE_PREFIX)
user_auth_gateway_error_response_handler = APIErrorResponseHandler(UserAuthError.CODE_PREFIX, error_details=False)
