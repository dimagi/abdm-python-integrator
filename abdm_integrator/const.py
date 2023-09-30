import celery

from abdm_integrator.settings import app_settings

SESSIONS_PATH = '/v0.5/sessions'
GATEWAY_CALLBACK_URL_PREFIX = 'api/gateway/v0.5'

CELERY_TASK = app_settings.CELERY_APP.task if app_settings.CELERY_APP else celery.shared_task


class ConsentStatus:
    PENDING = 'PENDING'
    REQUESTED = 'REQUESTED'
    GRANTED = 'GRANTED'
    DENIED = 'DENIED'
    REVOKED = 'REVOKED'
    EXPIRED = 'EXPIRED'
    ERROR = 'ERROR'

    HIP_GATEWAY_CHOICES = [
        (GRANTED, 'Granted'),
        (REVOKED, 'Revoked'),
        (EXPIRED, 'Expired'),
    ]
    GATEWAY_CHOICES = HIP_GATEWAY_CHOICES + [(DENIED, 'Denied')]
    CONSENT_REQUEST_CHOICES = GATEWAY_CHOICES + [
        (PENDING, 'Pending request from Gateway'),
        (REQUESTED, 'Requested'),
        (ERROR, 'Error occurred'),
    ]


class ArtefactFetchStatus:
    REQUESTED = 'REQUESTED'
    RECEIVED = 'RECEIVED'
    ERROR = 'ERROR'

    CHOICES = [
        (REQUESTED, 'Requested'),
        (RECEIVED, 'Received'),
        (ERROR, 'Error occurred'),
    ]


class ConsentPurpose:
    CARE_MANAGEMENT = 'CAREMGT'
    BREAK_THE_GLASS = 'BTG'
    PUBLIC_HEALTH = 'PUBHLTH'
    HEALTHCARE_PAYMENT = 'HPAYMT'
    DISEASE_SPECIFIC_HEALTHCARE_RESEARCH = 'DSRCH'
    SELF_REQUESTED = 'PATRQT'

    CHOICES = [
        (CARE_MANAGEMENT, 'Care Management'),
        (BREAK_THE_GLASS, 'Break the Glass'),
        (PUBLIC_HEALTH, 'Public Health'),
        (HEALTHCARE_PAYMENT, 'Healthcare Payment'),
        (DISEASE_SPECIFIC_HEALTHCARE_RESEARCH, 'Disease Specific Healthcare Research'),
        (SELF_REQUESTED, 'Self Requested'),
    ]

    REFERENCE_URI = 'http://terminology.hl7.org/ValueSet/v3-PurposeOfUse'


class HealthInformationType:
    PRESCRIPTION = 'Prescription'
    OP_CONSULTATION = 'OPConsultation'
    DISCHARGE_SUMMARY = 'DischargeSummary'
    DIAGNOSTIC_REPORT = 'DiagnosticReport'
    IMMUNIZATION_RECORD = 'ImmunizationRecord'
    HEALTH_DOCUMENT_RECORD = 'HealthDocumentRecord'
    WELLNESS_RECORD = 'WellnessRecord'

    CHOICES = [
        (PRESCRIPTION, 'Prescription'),
        (OP_CONSULTATION, 'OP Consultation'),
        (DISCHARGE_SUMMARY, 'Discharge Summary'),
        (DIAGNOSTIC_REPORT, 'Diagnostic Report'),
        (IMMUNIZATION_RECORD, 'Immunization Record'),
        (HEALTH_DOCUMENT_RECORD, 'Record artifact'),
        (WELLNESS_RECORD, 'Wellness Record'),
    ]


class DataAccessMode:
    VIEW = 'VIEW'
    STORE = 'STORE'
    QUERY = 'QUERY'
    STREAM = 'STREAM'

    CHOICES = [
        (VIEW, 'View'),
        (STORE, 'Store'),
        (QUERY, 'Query'),
        (STREAM, 'Stream'),
    ]


class TimeUnit:
    HOUR = 'HOUR'
    WEEK = 'WEEK'
    DAY = 'DAY'
    MONTH = 'MONTH'
    YEAR = 'YEAR'

    CHOICES = [
        (HOUR, 'Hour'),
        (WEEK, 'Week'),
        (DAY, 'Day'),
        (MONTH, 'Month'),
        (YEAR, 'Year'),
    ]
