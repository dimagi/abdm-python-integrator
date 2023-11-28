import logging
from dataclasses import dataclass

from drf_standardized_errors.handler import exception_handler as drf_standardized_exception_handler
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.status import HTTP_500_INTERNAL_SERVER_ERROR

logger = logging.getLogger('abdm_integrator')

ERROR_FUTURE_DATE_MESSAGE = 'This field must be in future'
ERROR_PAST_DATE_MESSAGE = 'This field must be in past'

ERROR_CODE_INVALID = 'invalid'
ERROR_CODE_REQUIRED = 'required'
ERROR_CODE_REQUIRED_MESSAGE = 'This field is required.'
ERROR_CODE_INVALID_CHOICE = 'invalid_choice'
ERROR_CODE_INVALID_CHOICE_MESSAGE = '"{}" is not a valid choice.'


STANDARD_ERRORS = {
    400: 'Required attributes not provided or Request information is not as expected',
    401: 'Unauthorized request',
    404: 'Resource not found',
    405: 'Method not allowed',
    500: 'Unknown error occurred',
    503: 'ABDM Gateway Service down',
    555: 'Gateway callback response timeout',
}


class ABDMAccessTokenException(Exception):
    pass


class ABDMServiceUnavailable(APIException):
    status_code = 503
    default_detail = 'ABDM Service temporarily unavailable, try again later.'
    default_code = 'service_unavailable'

    @property
    def error(self):
        return {'code': self.default_code, 'message': self.default_detail}


class ABDMGatewayCallbackTimeout(APIException):
    status_code = 555
    default_detail = 'Callback Response not received from ABDM Gateway within time. Please try again.'
    default_code = 'gateway_error'


@dataclass
class CustomAPIException(Exception):
    """
    Base Exception Class to be used for creating Custom API Exceptions
    """
    status_code: int
    error_code: int
    error_message: str
    detail_message: str
    detail_code: str
    detail_attr: str

    @property
    def error(self):
        return {
            'code': self.error_code,
            'message': self.error_message,
            'details': [{
                'code': self.detail_code,
                'detail': self.detail_message,
                'attr': self.detail_attr
            }]
        }


class ABDMGatewayError(CustomAPIException):
    status_code = 554
    error_message = 'ABDM Gateway Error'
    detail_code = 'abdm_gateway_error'
    detail_attr = None

    def __init__(self, error_code, detail_message):
        self.error_code = error_code
        self.detail_message = detail_message


class CustomError(CustomAPIException):

    def __init__(self, error_code, error_message, status_code=400, detail_code=ERROR_CODE_INVALID,
                 detail_message=None, detail_attr=None):
        self.status_code = status_code
        self.error_code = error_code
        self.error_message = error_message
        self.detail_code = detail_code
        self.detail_message = detail_message or self.error_message
        self.detail_attr = detail_attr


class APIErrorResponseHandler:
    standard_errors = STANDARD_ERRORS

    def __init__(self, error_code_prefix, error_details=True, log_errors=False):
        self.error_code_prefix = error_code_prefix
        self.error_details = error_details
        self.log_errors = log_errors

    def get_exception_handler(self):
        def _handler(exc, context):
            if isinstance(exc, CustomAPIException):
                response = self.generate_response_from_custom_exception(exc.status_code, exc.error)
            else:
                response = drf_standardized_exception_handler(exc, context)
                response = self.format_standard_error_response(response)
            if self.log_errors:
                self._log_error(context['request'], response)
            return self._handle_error_details(response)
        return _handler

    def _handle_error_details(self, response):
        if response is not None:
            if not self.error_details or response.status_code == HTTP_500_INTERNAL_SERVER_ERROR:
                del response.data['error']['details']
        return response

    @staticmethod
    def _log_error(request, response):
        # request_id and callback_request_id are applicable for gateway facing APIs.
        try:
            callback_request_id = request.data['resp']['requestId']
        except KeyError:
            callback_request_id = None
        logger.error(
            'ABDM Request Error: path=%s, status=%s, request_id=%s, callback_request_id=%s, error=%s',
            request.path,
            response.status_code,
            request.data.get('requestId'),
            callback_request_id,
            response.data.get('error')
        )

    def _error_from_status(self, status):
        return {
            'code': int(f'{self.error_code_prefix}{status}'),
            'message': self.standard_errors.get(status)
        }

    def format_standard_error_response(self, response):
        """
        ABDM (M2/M3) has a different response body format which includes custom codes for standard errors.
        This modifies the response body format obtained by drf_standardized_errors to the required format.
        'keep_details' flag is used to decide on sending 'error'>'details' field.
        The field 'error'>'code' is created by appending 'error_code_prefix' to the response status code.
        Sample:
        Input Response Body with Status Code as 400:
            {
              "type": "validation_error",
              "errors": [
                {
                  "code": "required",
                  "detail": "This field is required.",
                  "attr": "purpose.code"
                }
              ]
            }
        Output Response Body with `error_code_prefix` as `4`:
            {
                "error": {
                    "code": 4400,
                    "message": "Required attributes not provided or Request information is not as expected",
                    "details": [
                        {
                            "code": "required",
                            "detail": "This field is required.",
                            "attr": "purpose.code"
                        }
                    ]
                }
            }

        """
        if response is not None:
            data = {
                'error': {
                    'code': int(f'{self.error_code_prefix}{response.status_code}'),
                    'message': self.standard_errors.get(response.status_code),
                    'details': response.data.get('errors', [])
                }
            }
            response.data = data
        return response

    def generate_response_from_custom_exception(self, status_code, error):
        return Response(status=status_code, data={'error': error})
