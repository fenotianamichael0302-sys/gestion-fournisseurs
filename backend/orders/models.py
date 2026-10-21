"""Commandes d'achat et lignes associées."""
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from suppliers.models import Supplier


class PurchaseOrder(models.Model):
    class Status(models.TextChoices):
        DRAFT = "BROUILLON", "Brouillon"
        PENDING = "EN_ATTENTE", "En attente"
        APPROVED = "VALIDEE", "Validée"
        REJECTED = "REFUSEE", "Refusée"
        IN_DELIVERY = "EN_COURS_LIVRAISON", "En cours de livraison"
        PARTIALLY_DELIVERED = "PARTIELLEMENT_LIVREE", "Partiellement livrée"
        DELIVERED = "LIVREE", "Livrée"
        CANCELLED = "ANNULEE", "Annulée"

    order_number = models.CharField("numéro de commande", max_length=30, unique=True)
    supplier = models.ForeignKey(
        Supplier,
        verbose_name="fournisseur",
        on_delete=models.PROTECT,
        related_name="orders",
    )
    order_date = models.DateField(
        "date de commande",
        default=timezone.localdate,
        db_index=True,
    )
    expected_delivery_date = models.DateField(
        "date de livraison prévue",
        null=True,
        blank=True,
    )
    status = models.CharField(
        "statut",
        max_length=24,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="validé par",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_purchase_orders",
    )
    approved_at = models.DateTimeField("validé le", null=True, blank=True)
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="refusé par",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rejected_purchase_orders",
    )
    rejected_at = models.DateTimeField("refusé le", null=True, blank=True)
    rejection_reason = models.TextField("motif du refus", blank=True)
    terms = models.TextField("conditions", blank=True)
    notes = models.TextField("notes", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="créé par",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="purchase_orders",
    )
    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        ordering = ["-order_date", "-id"]
        verbose_name = "commande d'achat"
        verbose_name_plural = "commandes d'achat"
        indexes = [
            models.Index(fields=["status", "order_date"]),
            models.Index(fields=["supplier", "order_date"]),
        ]

    @property
    def total_ht(self):
        return sum((line.total_ht for line in self.lines.all()), Decimal("0.00"))

    @property
    def total_tax(self):
        return sum((line.tax_amount for line in self.lines.all()), Decimal("0.00"))

    @property
    def total_ttc(self):
        return self.total_ht + self.total_tax

    def __str__(self):
        return self.order_number


class OrderNumberSequence(models.Model):
    year = models.PositiveSmallIntegerField("année", primary_key=True)
    next_number = models.PositiveIntegerField("prochain numéro", default=1)

    class Meta:
        verbose_name = "séquence de numérotation des commandes"
        verbose_name_plural = "séquences de numérotation des commandes"


class PurchaseOrderLine(models.Model):
    order = models.ForeignKey(
        PurchaseOrder,
        verbose_name="commande",
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
        verbose_name = "ligne de commande"
        verbose_name_plural = "lignes de commande"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="order_line_qty_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name="order_line_price_nonneg",
            ),
            models.CheckConstraint(
                condition=models.Q(tax_rate__gte=0, tax_rate__lte=100),
                name="order_line_tax_range",
            ),
        ]

    @property
    def total_ht(self):
        return (self.quantity * self.unit_price).quantize(Decimal("0.01"))

    @property
    def tax_amount(self):
        return (self.total_ht * self.tax_rate / Decimal("100")).quantize(
            Decimal("0.01")
        )

    @property
    def total_ttc(self):
        return self.total_ht + self.tax_amount

    def __str__(self):
        return self.product_name


class Delivery(models.Model):
    order = models.ForeignKey(
        PurchaseOrder,
        verbose_name="commande",
        on_delete=models.PROTECT,
        related_name="deliveries",
    )
    delivery_date = models.DateField("date de réception")
    notes = models.TextField("observations", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="enregistré par",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recorded_deliveries",
    )
    created_at = models.DateTimeField("créé le", auto_now_add=True)

    class Meta:
        ordering = ["-delivery_date", "-id"]
        verbose_name = "réception de livraison"
        verbose_name_plural = "réceptions de livraison"
        indexes = [models.Index(fields=["order", "delivery_date"])]

    def __str__(self):
        return f"Réception {self.delivery_date:%d/%m/%Y} — {self.order.order_number}"


class DeliveryLine(models.Model):
    delivery = models.ForeignKey(
        Delivery,
        verbose_name="réception",
        on_delete=models.CASCADE,
        related_name="lines",
    )
    order_line = models.ForeignKey(
        PurchaseOrderLine,
        verbose_name="ligne de commande",
        on_delete=models.PROTECT,
        related_name="delivery_lines",
    )
    quantity_received = models.DecimalField(
        "quantité reçue",
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )
    quantity_damaged = models.DecimalField(
        "quantité endommagée",
        max_digits=12,
        decimal_places=3,
        default=Decimal("0.000"),
        validators=[MinValueValidator(Decimal("0.000"))],
    )
    quantity_missing = models.DecimalField(
        "quantité manquante signalée",
        max_digits=12,
        decimal_places=3,
        default=Decimal("0.000"),
        validators=[MinValueValidator(Decimal("0.000"))],
    )
    notes = models.TextField("observations", blank=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "ligne de réception"
        verbose_name_plural = "lignes de réception"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity_received__gt=0),
                name="delivery_line_received_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity_damaged__gte=0),
                name="delivery_line_damaged_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity_missing__gte=0),
                name="delivery_line_missing_nonnegative",
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError

        super().clean()
        if self.quantity_damaged > self.quantity_received:
            raise ValidationError(
                {"quantity_damaged": "La quantité endommagée ne peut dépasser la quantité reçue."}
            )

    def __str__(self):
        return f"{self.order_line.product_name} — {self.quantity_received}"
