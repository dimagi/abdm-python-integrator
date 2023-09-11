from rest_framework.response import Response
from rest_framework.status import HTTP_400_BAD_REQUEST


def generate_invalid_req_response(message, error_code=HTTP_400_BAD_REQUEST):
    resp = {
        "code": str(error_code),
        "message": "Unable to process the current request due to incorrect data entered.",
        "details": [{
            "message": message,
            "attribute": None
        }]
    }
    return Response(resp, status=HTTP_400_BAD_REQUEST)
