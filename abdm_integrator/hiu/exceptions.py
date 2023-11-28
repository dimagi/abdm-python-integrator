from abdm_integrator.exceptions import APIErrorResponseHandler


class HIUError:
    CODE_PREFIX = '4'

    CODE_PATIENT_NOT_FOUND = 4407
    CODE_KEY_PAIR_EXPIRED = 4410
    CODE_ARTEFACT_NOT_FOUND = 4551
    CODE_CONSENT_EXPIRED = 4452
    CODE_HEALTH_INFO_TIMEOUT = 4555
    CODE_HEALTH_DATA_RECEIVER = 4556

    CUSTOM_ERRORS = {
        CODE_PATIENT_NOT_FOUND: 'Patient details not found',
        CODE_KEY_PAIR_EXPIRED: 'Key Pair expired',
        CODE_ARTEFACT_NOT_FOUND: 'Artefact not found',
        CODE_CONSENT_EXPIRED: 'Consent has expired',
        CODE_HEALTH_INFO_TIMEOUT: 'Health information not received from Provider in the time limit.'
                                  ' Please try again.',
        CODE_HEALTH_DATA_RECEIVER: 'Error occurred while receiving health data.'
                                   ' Please try again or contact administrator'
    }


hiu_error_response_handler = APIErrorResponseHandler(HIUError.CODE_PREFIX)
hiu_gateway_error_response_handler = APIErrorResponseHandler(
    HIUError.CODE_PREFIX,
    error_details=False,
    log_errors=True
)


class HealthDataReceiverException(Exception):
    pass
