# Generated by Django 4.2.5 on 2023-11-16 08:22

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("abdm_hip", "0004_patientdiscoveryrequest_patientlinkrequest"),
    ]

    operations = [
        migrations.AddField(
            model_name="consentartefact",
            name="expiry_date",
            field=models.DateTimeField(default=datetime.datetime.utcnow),
            preserve_default=False,
        ),
    ]
