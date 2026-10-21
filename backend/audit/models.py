"""Journal d'audit immuable des opérations importantes."""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class AuditLog(models.Model):
    class Action(models.TextChoices):
        CREATE = "CREATE", "Création"
        UPDATE = "UPDATE", "Modification"
        DELETE = "DELETE", "Suppression"
        STATUS_CHANGE = "STATUS_CHANGE", "Changement de statut"
        LOGIN = "LOGIN", "Connexion"
        LOGOUT = "LOGOUT", "Déconnexion"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="utilisateur",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )
    action = models.CharField("action", max_length=20, choices=Action.choices, db_index=True)
    content_type = models.ForeignKey(
        ContentType,
        verbose_name="type d'objet",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    object_id = models.CharField("identifiant d'objet", max_length=64, blank=True)
    target = GenericForeignKey("content_type", "object_id")
    object_repr = models.CharField("objet", max_length=255, blank=True)
    old_values = models.JSONField("anciennes valeurs", null=True, blank=True)
    new_values = models.JSONField("nouvelles valeurs", null=True, blank=True)
    ip_address = models.GenericIPAddressField("adresse IP", null=True, blank=True)
    created_at = models.DateTimeField("date", auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "événement d'audit"
        verbose_name_plural = "événements d'audit"
        indexes = [
            models.Index(fields=["action", "created_at"]),
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        return f"{self.get_action_display()} — {self.object_repr or self.object_id}"
