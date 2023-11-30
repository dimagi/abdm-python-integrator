import json
import logging
from functools import wraps

logger = logging.getLogger('abdm_integrator')


def log_api(view_function):
    @wraps(view_function)
    def wrap(request, *args, **kwargs):
        body = json.loads(request.body) if request.body else request.GET
        response = view_function(request, *args, **kwargs)
        logger.info('API Request: path=%s, headers=%s, payload=%s, status=%s, response=%s', request.path,
                    request.headers, body, response.status_code, response.data)
        return response
    return wrap
