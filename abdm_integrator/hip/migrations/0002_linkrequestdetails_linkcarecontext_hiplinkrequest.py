# Generated by Django 4.2.5 on 2023-10-26 06:29

from django.db import migrations, models
import django.db.models.deletion
import uuid
from abdm_integrator.settings import app_settings


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(app_settings.USER_MODEL),
        ("abdm_hip", "0001_consent_artefact"),
    ]

    operations = [
        migrations.CreateModel(
            name="LinkRequestDetails",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("link_reference", models.UUIDField(default=uuid.uuid4, unique=True)),
                ("patient_reference", models.CharField(max_length=255)),
                ("patient_display", models.TextField()),
                ("hip_id", models.CharField(max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending request from Gateway"),
                            ("SUCCESS", "Success"),
                            ("ERROR", "Error"),
                        ],
                        default="PENDING",
                        max_length=40,
                    ),
                ),
                (
                    "initiated_by",
                    models.CharField(
                        choices=[("PATIENT", "Patient"), ("HIP", "HIP")], max_length=40
                    ),
                ),
                ("error", models.JSONField(null=True)),
                ("date_created", models.DateTimeField(auto_now_add=True)),
                ("last_modified", models.DateTimeField(auto_now=True)),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["patient_reference", "hip_id"],
                        name="abdm_hip_li_patient_9d819b_idx",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="LinkCareContext",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("reference", models.CharField(max_length=255)),
                ("display", models.TextField()),
                ("health_info_types", models.JSONField(default=list)),
                ("additional_info", models.JSONField(null=True)),
                (
                    "link_request_details",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="care_contexts",
                        to="abdm_hip.linkrequestdetails",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="HIPLinkRequest",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("gateway_request_id", models.UUIDField(unique=True)),
                ("date_created", models.DateTimeField(auto_now_add=True)),
                ("last_modified", models.DateTimeField(auto_now=True)),
                (
                    "link_request_details",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="hip_link_request",
                        to="abdm_hip.linkrequestdetails",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="link_requests",
                        to=app_settings.USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
