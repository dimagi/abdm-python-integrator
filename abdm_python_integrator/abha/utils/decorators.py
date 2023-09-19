from functools import wraps
from typing import List

from abdm_python_integrator.abha.utils.response import get_bad_response


def required_request_params(required_request_data):
    """
    Checks if the parameters provided in the decorator(a list of strings) are present in the DRF request.
    If not, raises 400 Bad Request error.
    """

    def decorate(fn):
        if not (required_request_data and isinstance(required_request_data, List)):
            error_msg = "Parameter names not provided in the correct format. These parameters are defined" \
                        "in the decorator argument of api and used for validating the request." \
                        "Required: List of parameters."
            return get_bad_response(error_msg)

        @wraps(fn)
        def wrapped(request, *args, **kwargs):
            request_data = request.query_params if request.method == 'GET' else request.data
            invalid_params = []
            for param in required_request_data:
                if not request_data.get(param):
                    invalid_params.append(param)
            if invalid_params:
                error_msg = f"Missing required data in the request: {','.join(invalid_params)}"
                return get_bad_response(error_msg)
            return fn(request, *args, **kwargs)

        return wrapped

    return decorate
