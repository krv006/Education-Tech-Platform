"""Request ID middleware — har bir so'rovga qisqa unikal ID.

Frontend/loglar/audit bir so'rovni bitta ID orqali bog'laydi (debugging uchun oltin).
"""
import uuid


class RequestIDMiddleware:
    HEADER = 'X-Request-ID'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = request.headers.get(self.HEADER) or uuid.uuid4().hex[:12]
        response = self.get_response(request)
        response[self.HEADER] = request.request_id
        return response
