# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2019-01-02 23:34
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('model', '0012_branch_maxlen'),
    ]

    operations = [
        migrations.AlterField(
            model_name='push',
            name='revision',
            field=models.CharField(db_index=True, max_length=40),
        ),
    ]
