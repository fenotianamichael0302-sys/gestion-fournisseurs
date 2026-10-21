"""Règlements effectués sur les factures."""
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from invoices.models import Invoice


class Payment(models.Model):
    class Method(models.TextChoices):
        BANK_TRANSFER = "VIREMENT", "Virement"
        CHEQUE = "CHEQUE", "Chèque"
        CASH = "ESPECES", "Espèces"
        MOBILE_MONEY = "MOBILE_MONEY", "Mobile money"
        CARD = "CARTE", "Carte"

    invoice = models.ForeignKey(
        Invoice,
        verbose_name="facture",
        on_delete=models.PROTECT,
        related_name="payments",
    )
    payment_date = models.DateField("date de paiement", db_index=True)
    amount = models.DecimalField(
        "montant",
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    method = models.CharField("mode de paiement", max_length=20, choices=Method.choices)
    reference = models.CharField("référence", max_length=150, blank=True)
    notes = models.TextField("notes", blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="enregistré par",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recorded_payments",
    )
    created_at = models.DateTimeField("créé le", auto_now_add=True)

    class Meta:
        ordering = ["-payment_date", "-id"]
        verbose_name = "paiement"
        verbose_name_plural = "paiements"
        indexes = [models.Index(fields=["invoice", "payment_date"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="payment_amount_positive",
            ),
        ]

    def __str__(self):
        return f"{self.amount} — {self.invoice.invoice_number}"
