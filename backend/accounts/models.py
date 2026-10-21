"""Utilisateur applicatif et rôles métier."""
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMINISTRATEUR = "ADMINISTRATEUR", "Administrateur"
        ACHETEUR = "ACHETEUR", "Acheteur"

    role = models.CharField(
        "rôle",
        max_length=20,
        choices=Role.choices,
        default=Role.ACHETEUR,
    )

    class Meta:
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"
        ordering = ["username"]

    def __str__(self):
        return self.get_full_name() or self.username
