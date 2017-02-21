# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-02-09 22:17
from __future__ import unicode_literals

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('model', '0001_squashed_0053_add_job_platform_option_push_index'),
    ]

    operations = [
        migrations.CreateModel(
            name='TaskclusterMetadata',
            fields=[
                ('job', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name='taskcluster_metadata', serialize=False, to='model.Job')),
                ('task_id', models.CharField(max_length=22, unique=True, validators=[django.core.validators.MinLengthValidator(22)])),
                ('retry_id', models.PositiveIntegerField()),
            ],
            options={
                'db_table': 'taskcluster_metadata',
            },
        ),
    ]
