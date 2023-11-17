from datetime import datetime

from celery.schedules import crontab

from abdm_integrator.const import CELERY_PERIODIC_TASK, CELERY_TASK
from abdm_integrator.exceptions import ABDMServiceUnavailable
from abdm_integrator.hip.models import ConsentArtefact
from abdm_integrator.settings import app_settings


@CELERY_TASK(queue=app_settings.CELERY_QUEUE, bind=True, ignore_result=False,
             autoretry_for=(ABDMServiceUnavailable,), retry_backoff=2, max_retries=3)
def process_hip_consent_notification_request(self, request_data):
    from abdm_integrator.hip.views.consents import GatewayConsentRequestNotifyProcessor
    GatewayConsentRequestNotifyProcessor(request_data).process_request()


@CELERY_TASK(queue=app_settings.CELERY_QUEUE, bind=True, ignore_result=False)
def process_hip_health_information_request(self, request_data):
    from abdm_integrator.hip.views.health_information import GatewayHealthInformationRequestProcessor
    GatewayHealthInformationRequestProcessor(request_data).process_request()


@CELERY_TASK(queue=app_settings.CELERY_QUEUE, bind=True, ignore_result=False)
def process_patient_care_context_discover_request(self, request_data):
    from abdm_integrator.hip.views.care_contexts import GatewayCareContextsDiscoverProcessor
    GatewayCareContextsDiscoverProcessor(request_data).process_request()


@CELERY_TASK(queue=app_settings.CELERY_QUEUE, bind=True, ignore_result=False)
def process_patient_care_context_link_init_request(self, request_data):
    from abdm_integrator.hip.views.care_contexts import GatewayCareContextsLinkInitProcessor
    GatewayCareContextsLinkInitProcessor(request_data).process_request()


@CELERY_TASK(queue=app_settings.CELERY_QUEUE, bind=True, ignore_result=False)
def process_patient_care_context_link_confirm_request(self, request_data):
    from abdm_integrator.hip.views.care_contexts import GatewayCareContextsLinkConfirmProcessor
    GatewayCareContextsLinkConfirmProcessor(request_data).process_request()


@CELERY_PERIODIC_TASK(run_every=crontab(hour='*/2', minute='0'), queue=app_settings.CELERY_QUEUE)
def process_hip_expired_consents():
    _process_hip_expired_consents()


def _process_hip_expired_consents():
    ConsentArtefact.objects.filter(expiry_date__lt=datetime.utcnow()).delete()
