from datetime import datetime

from celery.schedules import crontab
from django.db import transaction

from abdm_integrator.const import CELERY_PERIODIC_TASK, CELERY_TASK, ConsentStatus
from abdm_integrator.exceptions import ABDMServiceUnavailable
from abdm_integrator.hiu.models import ConsentRequest
from abdm_integrator.settings import app_settings


@CELERY_TASK(queue=app_settings.CELERY_QUEUE, bind=True, ignore_result=False,
             autoretry_for=(ABDMServiceUnavailable,), retry_backoff=2, max_retries=3)
def process_hiu_consent_notification_request(self, request_data):
    from abdm_integrator.hiu.views.consents import GatewayConsentRequestNotifyProcessor
    GatewayConsentRequestNotifyProcessor(request_data).process_request()


@CELERY_TASK(queue=app_settings.CELERY_QUEUE, bind=True, ignore_result=False)
def process_hiu_health_information_receiver(self, request_data):
    from abdm_integrator.hiu.views.health_information import ReceiveHealthInformationProcessor
    ReceiveHealthInformationProcessor(request_data).process_request()


@CELERY_PERIODIC_TASK(run_every=crontab(hour='*/2', minute='0'), queue=app_settings.CELERY_QUEUE)
def process_hiu_expired_consents():
    _process_hiu_expired_consents()


def _process_hiu_expired_consents():
    exclude = [ConsentStatus.EXPIRED, ConsentStatus.REVOKED, ConsentStatus.DENIED]
    for consent in ConsentRequest.objects.exclude(status__in=exclude).filter(
        expiry_date__lt=datetime.utcnow()
    ):
        with transaction.atomic():
            consent.update_status(ConsentStatus.EXPIRED)
            consent.artefacts.all().delete()
