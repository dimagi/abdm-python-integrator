import uuid

from django.db import models

from abdm_integrator.const import HealthInformationStatus, LinkRequestInitiator, LinkRequestStatus
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


class LinkRequestDetails(models.Model):
    link_reference = models.UUIDField(default=uuid.uuid4, unique=True)
    patient_reference = models.CharField(max_length=255)
    patient_display = models.TextField()
    hip_id = models.CharField(max_length=255)
    status = models.CharField(choices=LinkRequestStatus.CHOICES, default=LinkRequestStatus.PENDING,
                              max_length=40)
    initiated_by = models.CharField(choices=LinkRequestInitiator.CHOICES, max_length=40)
    error = models.JSONField(null=True)
    date_created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'abdm_hip'
        indexes = [
            models.Index(fields=['patient_reference', 'hip_id'])
        ]


class LinkCareContext(models.Model):
    reference = models.CharField(max_length=255)
    display = models.TextField()
    health_info_types = models.JSONField(default=list)
    additional_info = models.JSONField(null=True)
    link_request_details = models.ForeignKey(LinkRequestDetails, on_delete=models.PROTECT,
                                             related_name='care_contexts')

    class Meta:
        app_label = 'abdm_hip'


class HIPLinkRequest(models.Model):
    user = models.ForeignKey(app_settings.USER_MODEL, on_delete=models.PROTECT, related_name='link_requests')
    gateway_request_id = models.UUIDField(unique=True)
    link_request_details = models.OneToOneField(LinkRequestDetails, on_delete=models.CASCADE,
                                                related_name='hip_link_request')
    date_created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)


class HealthInformationRequest(models.Model):
    consent_artefact = models.ForeignKey(ConsentArtefact, to_field='artefact_id', on_delete=models.CASCADE,
                                         related_name='health_information_requests', null=True)
    transaction_id = models.UUIDField(unique=True)
    status = models.CharField(choices=HealthInformationStatus.HIP_CHOICES,
                              default=HealthInformationStatus.ACKNOWLEDGED, max_length=40)
    error = models.JSONField(null=True)
    date_created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'abdm_hip'


class HealthDataTransfer(models.Model):
    health_information_request = models.ForeignKey(HealthInformationRequest, to_field='transaction_id',
                                                   on_delete=models.CASCADE,
                                                   related_name='health_data_transfer')
    page_number = models.SmallIntegerField()
    care_contexts_status = models.JSONField()
    date_created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'abdm_hip'


class PatientDiscoveryRequest(models.Model):
    transaction_id = models.UUIDField(unique=True)
    patient_reference_number = models.CharField(max_length=255, null=True)
    patient_display = models.TextField(null=True)
    hip_id = models.CharField(max_length=255)
    care_contexts = models.JSONField(default=list)
    error = models.JSONField(null=True)
    date_created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'abdm_hip'


class PatientLinkRequest(models.Model):
    discovery_request = models.ForeignKey(PatientDiscoveryRequest, on_delete=models.CASCADE,
                                          related_name='link_requests')
    otp_transaction_id = models.UUIDField(unique=True, null=True)
    link_request_details = models.OneToOneField(LinkRequestDetails, on_delete=models.CASCADE,
                                                related_name='patient_link_request')
    date_created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
