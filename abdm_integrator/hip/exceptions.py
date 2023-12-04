from abdm_integrator.exceptions import APIErrorResponseHandler


class HIPError:
    CODE_PREFIX = '3'

    CODE_MULTIPLE_PATIENTS_FOUND = 3403
    CODE_PATIENT_NOT_FOUND = 3404
    CODE_DISCOVERY_REQUEST_NOT_FOUND = 3407
    CODE_KEY_PAIR_EXPIRED = 3410
    CODE_LINK_REQUEST_NOT_FOUND = 3413
    CODE_ARTEFACT_NOT_FOUND = 3416
    CODE_INVALID_CONSENT_STATUS = 3417
    CODE_CONSENT_EXPIRED = 3418
    CODE_INVALID_DATE_RANGE = 3419
    CODE_CARE_CONTEXT_ALREADY_LINKED = 3420
    CODE_LINK_INIT_REQUEST_PATIENT_MISMATCH = 3421
    CODE_LINK_INIT_REQUEST_CARE_CONTEXTS_MISMATCH = 3422
    CODE_INTERNAL_ERROR = 3500
    CODE_LINK_INIT_REQUEST_OTP_GENERATION_FAILED = 3501
    CODE_LINK_CONFIRM_OTP_VERIFICATION_FAILED = 3509

    CUSTOM_ERRORS = {
        CODE_CARE_CONTEXT_ALREADY_LINKED: '{} care contexts are already linked',
        CODE_MULTIPLE_PATIENTS_FOUND: 'Multiple patients found for discovery request',
        CODE_PATIENT_NOT_FOUND: 'No patient found for discovery request',
        CODE_DISCOVERY_REQUEST_NOT_FOUND: 'Discovery request not found',
        CODE_KEY_PAIR_EXPIRED: 'Expired Key Pair',
        CODE_LINK_REQUEST_NOT_FOUND: 'Link request not found',
        CODE_ARTEFACT_NOT_FOUND: 'Consent Artefact Not Found',
        CODE_INVALID_CONSENT_STATUS: 'Invalid Consent Status',
        CODE_CONSENT_EXPIRED: 'Consent has expired',
        CODE_INVALID_DATE_RANGE: 'Date range is not valid',
        CODE_LINK_INIT_REQUEST_PATIENT_MISMATCH: 'Patient reference does not match the discovery request',
        CODE_LINK_INIT_REQUEST_CARE_CONTEXTS_MISMATCH: 'Care Contexts references does '
                                                       'not match the discovery request',
        CODE_INTERNAL_ERROR: 'Internal Error Occurred',
        CODE_LINK_INIT_REQUEST_OTP_GENERATION_FAILED: 'OTP Generation failed for link',
        CODE_LINK_CONFIRM_OTP_VERIFICATION_FAILED: 'OTP Verification failed for link',
    }


hip_error_response_handler = APIErrorResponseHandler(HIPError.CODE_PREFIX)
hip_gateway_error_response_handler = APIErrorResponseHandler(
    HIPError.CODE_PREFIX,
    error_details=False,
    log_errors=True
)


class HealthDataTransferException(Exception):
    pass


class DiscoveryNoPatientFoundError(Exception):
    pass


class DiscoveryMultiplePatientsFoundError(Exception):
    pass
