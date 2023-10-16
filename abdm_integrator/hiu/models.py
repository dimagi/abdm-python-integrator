from django.db import models

from abdm_integrator.const import ArtefactFetchStatus, ConsentStatus, HealthInformationStatus
from abdm_integrator.settings import app_settings


class ConsentRequest(models.Model):
    user = models.ForeignKey(app_settings.USER_MODEL, on_delete=models.PROTECT,
                             related_name='consent_requests')
    gateway_request_id = models.UUIDField(unique=True)
    consent_request_id = models.UUIDField(null=True, unique=True)
    status = models.CharField(choices=ConsentStatus.CONSENT_REQUEST_CHOICES, default=ConsentStatus.PENDING,
                              max_length=40)
    details = models.JSONField(null=True)
    error = models.JSONField(null=True)
    date_created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    # Below attributes correspond to ones that are approved by Patient when consent is granted.
    health_info_from_date = models.DateTimeField()
    health_info_to_date = models.DateTimeField()
    health_info_types = models.JSONField(default=list)
    expiry_date = models.DateTimeField()

    class Meta:
        app_label = 'abdm_hiu'

    def update_status(self, status):
        self.status = status
        self.save()

    def update_user_amendable_details(self, consent_permission, health_info_types):
        self.health_info_from_date = consent_permission['dateRange']['from']
        self.health_info_to_date = consent_permission['dateRange']['to']
        self.expiry_date = consent_permission['dataEraseAt']
        self.health_info_types = health_info_types
        self.save()


class ConsentArtefact(models.Model):
    consent_request = models.ForeignKey(ConsentRequest, to_field='consent_request_id', on_delete=models.PROTECT,
                                        related_name='artefacts')
    gateway_request_id = models.UUIDField(unique=True)
    artefact_id = models.UUIDField(unique=True)
    details = models.JSONField(null=True)
    fetch_status = models.CharField(choices=ArtefactFetchStatus.CHOICES, default=ArtefactFetchStatus.REQUESTED,
                                    max_length=40)
    error = models.JSONField(null=True)
    date_created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'abdm_hiu'


class HealthInformationRequest(models.Model):
    user = models.ForeignKey(app_settings.USER_MODEL, on_delete=models.PROTECT,
                             related_name='health_information_requests')
    consent_artefact = models.ForeignKey(ConsentArtefact, to_field='artefact_id', on_delete=models.CASCADE,
                                         related_name='health_information_request')
    gateway_request_id = models.UUIDField(unique=True)
    transaction_id = models.UUIDField(null=True, unique=True)
    key_material = models.JSONField()
    status = models.CharField(choices=HealthInformationStatus.HIU_CHOICES,
                              default=HealthInformationStatus.PENDING, max_length=40)
    error = models.JSONField(null=True)
    date_created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'abdm_hiu'


class HealthDataReceiver(models.Model):
    health_information_request = models.ForeignKey(HealthInformationRequest, to_field='transaction_id',
                                                   on_delete=models.CASCADE,
                                                   related_name='health_data_receipts')
    page_number = models.SmallIntegerField()
    care_contexts_status = models.JSONField()
    date_created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'abdm_hiu'
