# Generated by Django 5.0.4 on 2025-03-03 10:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0006_alter_scheduledmessage_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='keywordresponse',
            name='icon',
            field=models.ImageField(blank=True, null=True, upload_to='icons/'),
        ),
    ]
