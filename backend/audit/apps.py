from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "audit"
    verbose_name = "Historique des actions"

    def ready(self):
        from audit.signals import register_signals

        register_signals()
