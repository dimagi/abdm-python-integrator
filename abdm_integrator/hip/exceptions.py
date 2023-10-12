from abdm_integrator.exceptions import APIErrorResponseHandler


class HIPError:
    CODE_PREFIX = '3'

    CODE_CARE_CONTEXT_ALREADY_LINKED = 3420
    CODE_PATIENT_NOT_FOUND = 3407
    CODE_KEY_PAIR_EXPIRED = 3410
    CODE_ARTEFACT_NOT_FOUND = 3416
    CODE_INVALID_CONSENT_STATUS = 3417
    CODE_CONSENT_EXPIRED = 3418
    CODE_INVALID_DATE_RANGE = 3419

    CUSTOM_ERRORS = {
        CODE_CARE_CONTEXT_ALREADY_LINKED: '{} care contexts are already linked',
        CODE_PATIENT_NOT_FOUND: 'Patient details not found',
        CODE_KEY_PAIR_EXPIRED: 'Expired Key Pair',
        CODE_ARTEFACT_NOT_FOUND: 'Consent Artefact Not Found',
        CODE_INVALID_CONSENT_STATUS: 'Invalid Consent Status',
        CODE_CONSENT_EXPIRED: 'Consent has expired',
        CODE_INVALID_DATE_RANGE: 'Date range is not valid',
    }


hip_error_response_handler = APIErrorResponseHandler(HIPError.CODE_PREFIX)
hip_gateway_error_response_handler = APIErrorResponseHandler(HIPError.CODE_PREFIX, error_details=False)


class HealthDataTransferException(Exception):
    pass
