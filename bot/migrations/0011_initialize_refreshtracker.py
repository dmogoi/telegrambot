from django.db import migrations

def create_initial_tracker(apps, schema_editor):
    RefreshTracker = apps.get_model('bot', 'RefreshTracker')
    RefreshTracker.objects.get_or_create(pk=1)

class Migration(migrations.Migration):
    dependencies = [
        # Corrected dependency to point to 0010_refreshtracker
        ('bot', '0010_refreshtracker'),
    ]

    operations = [
        migrations.RunPython(create_initial_tracker),
    ]