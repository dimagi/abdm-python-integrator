from django.urls import path

from abdm_python_integrator.abha.views import abha_creation_views

abha_creation_urls = [
    path('api/generate_aadhaar_otp', abha_creation_views.generate_aadhaar_otp, name='generate_aadhaar_otp'),
    path('api/generate_mobile_otp', abha_creation_views.generate_mobile_otp, name='generate_mobile_otp'),
    path('api/verify_aadhaar_otp', abha_creation_views.verify_aadhaar_otp, name='verify_aadhaar_otp'),
    path('api/verify_mobile_otp', abha_creation_views.verify_mobile_otp, name='verify_mobile_otp'),
]

abha_urls = abha_creation_urls
