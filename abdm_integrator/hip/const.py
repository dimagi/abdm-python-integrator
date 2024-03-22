
class HIPGatewayAPIPath:
    CONSENT_REQUEST_ON_NOTIFY_PATH = '/v0.5/consents/hip/on-notify'
    ADD_CARE_CONTEXTS = '/v0.5/links/link/add-contexts'
    CARE_CONTEXTS_LINK_NOTIFY = '/v0.5/links/context/notify'
    HEALTH_INFO_ON_REQUEST = '/v0.5/health-information/hip/on-request'
    HEALTH_INFO_NOTIFY = '/v0.5/health-information/notify'
    CARE_CONTEXTS_ON_DISCOVER = '/v0.5/care-contexts/on-discover'
    CARE_CONTEXTS_LINK_ON_INIT = '/v0.5/links/link/on-init'
    CARE_CONTEXTS_LINK_ON_CONFIRM = '/v0.5/links/link/on-confirm'
    PATIENT_SMS_NOTIFY_PATH = '/v0.5/patients/sms/notify2'


HEADER_NAME_HIP_ID = 'HTTP_X_HIP_ID'


class SMSOnNotifyStatus:
    ACKNOWLEDGED = 'ACKNOWLEDGED'
    ERRORED = 'ERRORED'

    CHOICES = [
        (ACKNOWLEDGED, 'Acknowledged'),
        (ERRORED, 'Errored'),
    ]
