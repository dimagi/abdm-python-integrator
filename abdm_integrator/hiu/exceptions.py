from abdm_integrator.exceptions import APIErrorResponseHandler


class HIUError:
    CODE_PREFIX = '4'

    CODE_PATIENT_NOT_FOUND = 4407
    CODE_CONSENT_EXPIRED = 4451

    CUSTOM_ERRORS = {
        CODE_PATIENT_NOT_FOUND: 'Patient details not found',
        CODE_CONSENT_EXPIRED: 'Consent has expired',
    }


hiu_error_response_handler = APIErrorResponseHandler(HIUError.CODE_PREFIX)
hiu_gateway_error_response_handler = APIErrorResponseHandler(HIUError.CODE_PREFIX, error_details=False)
