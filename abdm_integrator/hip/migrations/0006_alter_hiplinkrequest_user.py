# Generated by Django 4.2.5 on 2023-11-30 01:42

from django.db import migrations, models
import django.db.models.deletion
from abdm_integrator.settings import app_settings


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(app_settings.USER_MODEL),
        ("abdm_hip", "0005_consentartefact_expiry_date"),
    ]

    operations = [
        migrations.AlterField(
            model_name="hiplinkrequest",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="link_requests",
                to=app_settings.USER_MODEL,
            ),
        ),
    ]