from django.db import models


class ConsentArtefact(models.Model):
    artefact_id = models.UUIDField(unique=True)
    details = models.JSONField()
    signature = models.TextField()
    grant_acknowledgement = models.BooleanField()
    date_created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'abdm_hip'
