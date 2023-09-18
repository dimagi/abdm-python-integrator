SESSIONS_PATH = '/v0.5/sessions'


class ConsentStatus:
    PENDING = 'PENDING'
    REQUESTED = 'REQUESTED'
    GRANTED = 'GRANTED'
    DENIED = 'DENIED'
    REVOKED = 'REVOKED'
    EXPIRED = 'EXPIRED'
    ERROR = 'ERROR'

    GATEWAY_CHOICES = [(GRANTED, 'Granted'), (DENIED, 'Denied'), (REVOKED, 'Revoked'),
                       (EXPIRED, 'Expired')]
    CONSENT_REQUEST_CHOICES = GATEWAY_CHOICES + [(PENDING, 'Pending request from Gateway'),
                                                     (REQUESTED, 'Requested'),
                                                     (ERROR, 'Error occurred')]
