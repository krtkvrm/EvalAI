# -*- coding: utf-8 -*-
# Generated by Django 1.10.2 on 2017-09-19 03:21
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("jobs", "0006_add_indexing_to_some_attributes")]

    operations = [
        migrations.AddField(
            model_name="submission",
            name="is_flagged",
            field=models.BooleanField(default=False),
        )
    ]
