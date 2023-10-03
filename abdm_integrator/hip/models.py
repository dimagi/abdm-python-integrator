from django.db import models

from abdm_integrator.const import LinkRequestStatus
from abdm_integrator.settings import app_settings


class ConsentArtefact(models.Model):
    artefact_id = models.UUIDField(unique=True)
    details = models.JSONField()
    signature = models.TextField()
    grant_acknowledgement = models.BooleanField()
    date_created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'abdm_hip'


class LinkRequest(models.Model):

    user = models.ForeignKey(app_settings.USER_MODEL, on_delete=models.PROTECT, related_name='link_requests')
    patient_reference = models.CharField(max_length=255)
    hip_id = models.CharField(max_length=255)
    gateway_request_id = models.UUIDField(unique=True)
    status = models.CharField(choices=LinkRequestStatus.CHOICES, default=LinkRequestStatus.PENDING,
                              max_length=40)
    error = models.JSONField(null=True)
    date_created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'abdm_hip'
        indexes = [
            models.Index(fields=['patient_reference', 'hip_id'])
        ]


class LinkCareContext(models.Model):
    care_context_number = models.CharField(max_length=255)
    link_request = models.ForeignKey(LinkRequest, on_delete=models.PROTECT,
                                     related_name='care_contexts')
    health_info_types = models.JSONField(default=list)

    class Meta:
        app_label = 'abdm_hip'
