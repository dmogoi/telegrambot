# mixins.py
from django.views.generic.edit import FormMixin, DeletionMixin

from bot.models import AuditLog


class AuditLogMixin:
    action_type = None
    model_name = None

    def get_client_ip(self):
        xff = self.request.META.get('HTTP_X_FORWARDED_FOR')
        return xff.split(',')[0] if xff else self.request.META.get('REMOTE_ADDR')

    def log_action(self, instance, action_type, metadata=None):
        AuditLog.objects.create(
            user=self.request.user,
            action_type=action_type,
            model_name=self.model_name or instance._meta.model_name,
            object_id=str(instance.pk),
            action=f"{action_type} {instance._meta.verbose_name} - {instance}",
            ip_address=self.get_client_ip(),
            metadata=metadata or {}
        )


class CreateAuditLogMixin(AuditLogMixin):
    def form_valid(self, form):
        response = super().form_valid(form)
        self.log_action(self.object, 'CREATE')
        return response


class UpdateAuditLogMixin(AuditLogMixin):
    def form_valid(self, form):
        old_instance = self.get_object()
        old_data = {f.name: getattr(old_instance, f.name) for f in old_instance._meta.fields}

        response = super().form_valid(form)

        new_instance = self.object
        changes = {}
        for field in new_instance._meta.fields:
            old_value = old_data.get(field.name)
            new_value = getattr(new_instance, field.name)
            if old_value != new_value:
                changes[field.name] = {
                    'old': old_value,
                    'new': new_value
                }

        self.log_action(
            self.object,
            'UPDATE',
            {'changes': changes}
        )
        return response


class DeleteAuditLogMixin(AuditLogMixin, DeletionMixin):
    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        metadata = {
            'data': {f.name: getattr(instance, f.name) for f in instance._meta.fields}
        }
        response = super().delete(request, *args, **kwargs)
        self.log_action(instance, 'DELETE', metadata)
        return response