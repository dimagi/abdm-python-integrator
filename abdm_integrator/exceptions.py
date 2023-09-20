from rest_framework.exceptions import APIException

ERROR_FUTURE_DATE_MESSAGE = 'This field must be in future'
ERROR_PAST_DATE_MESSAGE = 'This field must be in past'


class ABDMAccessTokenException(Exception):
    pass


class ABDMServiceUnavailable(APIException):
    status_code = 503
    default_detail = 'ABDM Service temporarily unavailable, try again later.'
    default_code = 'service_unavailable'


class ABDMGatewayError(Exception):

    def __init__(self, error):
        self.error = error
