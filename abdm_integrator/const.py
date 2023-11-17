import celery

from abdm_integrator.periodic_task import periodic_task
from abdm_integrator.settings import app_settings

GATEWAY_CALLBACK_URL_PREFIX = 'api/gateway/v0.5'
HEALTH_INFORMATION_MEDIA_TYPE = 'application/fhir+json'

CELERY_TASK = app_settings.CELERY_APP.task if app_settings.CELERY_APP else celery.shared_task
# `CELERY_APP.periodic_task` should support creating periodic task using decorator.
# See `abdm_integrator.periodic_task.periodic_task`
CELERY_PERIODIC_TASK = app_settings.CELERY_APP.periodic_task if app_settings.CELERY_APP else periodic_task


GENDER_CHOICES = ['M', 'F', 'O', 'U']

CALLBACK_RESPONSE_CACHE_TIMEOUT = 10


class GatewayAPIPath:
    SESSIONS_PATH = '/v0.5/sessions'
    CERTS_PATH = '/v0.5/certs'


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
    PENDING = 'PENDING'
    REQUESTED = 'REQUESTED'
    RECEIVED = 'RECEIVED'
    ERROR = 'ERROR'

    CHOICES = [
        (PENDING, 'Pending'),
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


class AuthFetchModesPurpose:
    LINK = 'LINK'
    KYC = 'KYC'
    KYC_AND_LINK = 'KYC_AND_LINK'
    CHOICES = [(LINK, 'Link'), (KYC, 'KYC'), (KYC_AND_LINK, 'KYC and Link')]


class RequesterType:
    HIP = 'HIP'
    HIU = 'HIU'
    CHOICES = [(HIP, 'Health Information Provider'), (HIU, 'Health Information User')]


class AuthenticationMode:
    MOBILE_OTP = 'MOBILE_OTP'
    DIRECT = 'DIRECT'
    AADHAAR_OTP = 'AADHAAR_OTP'
    DEMOGRAPHICS = 'DEMOGRAPHICS'
    PASSWORD = 'PASSWORD'
    CHOICES = [(MOBILE_OTP, 'SMS OTP'), (DIRECT, 'Direct'), (AADHAAR_OTP, 'Aadhar OTP'),
               (DEMOGRAPHICS, 'Demographics'), (PASSWORD, 'Password')]


class LinkRequestStatus:
    PENDING = 'PENDING'
    SUCCESS = 'SUCCESS'
    ERROR = 'ERROR'

    CHOICES = [(PENDING, 'Pending request from Gateway'), (SUCCESS, 'Success'), (ERROR, 'Error')]


class LinkRequestInitiator:
    PATIENT = 'PATIENT'
    HIP = 'HIP'

    CHOICES = [(PATIENT, 'Patient'), (HIP, 'HIP')]


class HealthInformationStatus:
    PENDING = 'PENDING'
    REQUESTED = 'REQUESTED'
    ERROR = 'ERROR'
    ACKNOWLEDGED = 'ACKNOWLEDGED'
    TRANSFERRED = 'TRANSFERRED'
    DELIVERED = 'DELIVERED'
    FAILED = 'FAILED'
    ERRORED = 'ERRORED'
    OK = 'OK'

    HIP_CHOICES = [
        (ACKNOWLEDGED, 'Acknowledged'),
        (ERROR, 'Error occurred'),
        (TRANSFERRED, 'Transferred'),
        (FAILED, 'Failed'),
    ]

    HIU_CHOICES = [
        (PENDING, 'Pending request from Gateway'),
        (REQUESTED, 'Requested'),
    ] + HIP_CHOICES


class IdentifierType:
    MR = 'MR'
    MOBILE = 'MOBILE'
    NDHM_HEALTH_NUMBER = 'NDHM_HEALTH_NUMBER'
    HEALTH_ID = 'HEALTH_ID'
    EMAIL = 'EMAIL'

    CHOICES = [
        (MR, 'Medical Registration Number'),
        (MOBILE, 'Mobile'),
        (NDHM_HEALTH_NUMBER, 'NDHM Health Number'),
        (HEALTH_ID, 'Health Id'),
        (EMAIL, 'Email')
    ]
