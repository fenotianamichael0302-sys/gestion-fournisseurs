"""Factures fournisseur et détail des montants facturés."""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from orders.models import PurchaseOrder
from suppliers.models import Supplier


class Invoice(models.Model):
    supplier = models.ForeignKey(
        Supplier,
        verbose_name="fournisseur",
        on_delete=models.PROTECT,
        related_name="invoices",
    )
    order = models.ForeignKey(
        PurchaseOrder,
        verbose_name="commande associée",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="invoices",
    )
    invoice_number = models.CharField("numéro de facture", max_length=100)
    invoice_date = models.DateField("date de facture")
    due_date = models.DateField("date d'échéance", db_index=True)
    attachment = models.FileField(
        "pièce jointe",
        upload_to="invoices/%Y/%m/",
        blank=True,
    )
    notes = models.TextField("notes", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="créé par",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="supplier_invoices",
    )
    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        ordering = ["-invoice_date", "-id"]
        verbose_name = "facture fournisseur"
        verbose_name_plural = "factures fournisseur"
        constraints = [
            models.UniqueConstraint(
                fields=["supplier", "invoice_number"],
                name="unique_invoice_number_per_supplier",
            ),
            models.CheckConstraint(
                condition=models.Q(due_date__gte=models.F("invoice_date")),
                name="invoice_due_date_not_before_invoice_date",
            ),
        ]
        indexes = [
            models.Index(fields=["supplier", "invoice_date"]),
            models.Index(fields=["due_date", "invoice_date"]),
        ]

    def clean(self):
        super().clean()
        if (
            self.order_id
            and self.supplier_id
            and self.order.supplier_id != self.supplier_id
        ):
            raise ValidationError(
                {"order": "La commande sélectionnée appartient à un autre fournisseur."}
            )

    @property
    def total_ht(self):
        return sum(
            (line.line_total_ht for line in self.lines.all()),
            Decimal("0.00"),
        )

    @property
    def total_tax(self):
        return sum(
            (line.line_tax_amount for line in self.lines.all()),
            Decimal("0.00"),
        )

    @property
    def total_ttc(self):
        return self.total_ht + self.total_tax

    @property
    def amount_paid(self):
        return self.payments.aggregate(total=models.Sum("amount"))["total"] or Decimal(
            "0.00"
        )

    @property
    def balance_due(self):
        return max(self.total_ttc - self.amount_paid, Decimal("0.00"))

    @property
    def status(self):
        if self.balance_due == Decimal("0.00") and self.total_ttc > Decimal("0.00"):
            return self.PaymentStatus.PAID
        if self.amount_paid > Decimal("0.00"):
            return self.PaymentStatus.PARTIALLY_PAID
        if self.due_date < timezone.localdate():
            return self.PaymentStatus.OVERDUE
        return self.PaymentStatus.UNPAID

    class PaymentStatus(models.TextChoices):
        UNPAID = "NON_PAYEE", "Non payée"
        PARTIALLY_PAID = "PARTIELLEMENT_PAYEE", "Partiellement payée"
        PAID = "PAYEE", "Payée"
        OVERDUE = "EN_RETARD", "En retard"

    def __str__(self):
        return f"{self.invoice_number} — {self.supplier.company_name}"


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(
        Invoice,
        verbose_name="facture",
        on_delete=models.CASCADE,
        related_name="lines",
    )
    product_name = models.CharField("désignation", max_length=255, db_index=True)
    quantity = models.DecimalField(
        "quantité",
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )
    unit_price = models.DecimalField(
        "prix unitaire HT",
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    tax_rate = models.DecimalField(
        "taux de taxe (%)",
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0.00")),
            MaxValueValidator(Decimal("100.00")),
        ],
    )

    class Meta:
        ordering = ["id"]
        verbose_name = "ligne de facture"
        verbose_name_plural = "lignes de facture"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="invoice_line_qty_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name="invoice_line_price_nonneg",
            ),
            models.CheckConstraint(
                condition=models.Q(tax_rate__gte=0, tax_rate__lte=100),
                name="invoice_line_tax_range",
            ),
        ]

    @property
    def line_total_ht(self):
        return (self.quantity * self.unit_price).quantize(Decimal("0.01"))

    @property
    def line_tax_amount(self):
        return (self.line_total_ht * self.tax_rate / Decimal("100")).quantize(
            Decimal("0.01")
        )

    def __str__(self):
        return self.product_name
