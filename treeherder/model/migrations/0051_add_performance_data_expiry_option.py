# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-01-16 20:34
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('model', '0050_remove_redundant_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='repository',
            name='expire_performance_data',
            field=models.BooleanField(default=True),
        ),
    ]
