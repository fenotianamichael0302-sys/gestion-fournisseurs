"""Modèle des fournisseurs."""
from decimal import Decimal
import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Supplier(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIF", "Actif"
        INACTIVE = "INACTIF", "Inactif"
        BLOCKED = "BLOQUE", "Bloqué"

    company_name = models.CharField("raison sociale", max_length=200, db_index=True)
    contact_name = models.CharField("personne de contact", max_length=200, blank=True)
    email = models.EmailField("email", blank=True)
    phone = models.CharField("téléphone", max_length=40, blank=True)
    street = models.CharField("rue et adresse", max_length=255, blank=True)
    city = models.CharField("ville", max_length=120, blank=True)
    postal_code = models.CharField("code postal", max_length=20, blank=True)
    country = models.CharField("pays", max_length=100, blank=True)
    tax_id = models.CharField("NIF / STAT", max_length=100, blank=True)
    bank_name = models.CharField("banque", max_length=150, blank=True)
    bank_account = models.CharField("IBAN / RIB", max_length=100, blank=True)
    swift = models.CharField("SWIFT", max_length=20, blank=True)
    status = models.CharField(
        "statut",
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    notes = models.TextField("notes", blank=True)
    is_deleted = models.BooleanField("supprimé logiquement", default=False, db_index=True)
    deleted_at = models.DateTimeField("date de suppression", null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="supprimé par",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="deleted_suppliers",
    )
    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        ordering = ["company_name", "id"]
        verbose_name = "fournisseur"
        verbose_name_plural = "fournisseurs"
        indexes = [
            models.Index(fields=["status", "is_deleted"]),
            models.Index(fields=["city", "country"]),
        ]

    def soft_delete(self, user=None):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.save(update_fields=["is_deleted", "deleted_at", "deleted_by", "updated_at"])

    def __str__(self):
        return self.company_name


class SupplierEvaluation(models.Model):
    supplier = models.ForeignKey(
        Supplier,
        verbose_name="fournisseur",
        on_delete=models.PROTECT,
        related_name="evaluations",
    )
    order = models.ForeignKey(
        "orders.PurchaseOrder",
        verbose_name="commande livrée",
        on_delete=models.PROTECT,
        related_name="supplier_evaluations",
    )
    evaluated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="évalué par",
        on_delete=models.PROTECT,
        related_name="supplier_evaluations",
    )
    quality_rating = models.PositiveSmallIntegerField(
        "qualité",
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    delivery_rating = models.PositiveSmallIntegerField(
        "respect des délais",
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    price_rating = models.PositiveSmallIntegerField(
        "compétitivité des prix",
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    reliability_rating = models.PositiveSmallIntegerField(
        "fiabilité",
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField("commentaire", blank=True)
    created_at = models.DateTimeField("évalué le", auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "évaluation fournisseur"
        verbose_name_plural = "évaluations fournisseur"
        constraints = [
            models.UniqueConstraint(
                fields=["order", "evaluated_by"],
                name="unique_supplier_evaluation_per_order_user",
            )
        ]
        indexes = [models.Index(fields=["supplier", "created_at"])]

    def __str__(self):
        return f"{self.supplier.company_name} — {self.order.order_number}"


class SupplierQuote(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "DEMANDE", "Demandé"
        RECEIVED = "RECU", "Reçu"
        DECLINED = "REFUSE", "Refusé"

    comparison_id = models.UUIDField(
        "groupe de comparaison",
        default=uuid.uuid4,
        db_index=True,
    )
    supplier = models.ForeignKey(
        Supplier,
        verbose_name="fournisseur",
        on_delete=models.PROTECT,
        related_name="quotes",
    )
    product_name = models.CharField("produit ou service", max_length=255, db_index=True)
    quantity = models.DecimalField(
        "quantité demandée",
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )
    status = models.CharField(
        "statut",
        max_length=10,
        choices=Status.choices,
        default=Status.REQUESTED,
        db_index=True,
    )
    unit_price = models.DecimalField(
        "prix unitaire HT proposé",
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
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
    delivery_days = models.PositiveSmallIntegerField(
        "délai de livraison (jours)",
        null=True,
        blank=True,
    )
    quality_rating = models.PositiveSmallIntegerField(
        "qualité évaluée",
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    payment_terms = models.TextField("conditions de paiement", blank=True)
    notes = models.TextField("notes", blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="demandeur",
        on_delete=models.PROTECT,
        related_name="supplier_quote_requests",
    )
    requested_at = models.DateTimeField("demandé le", auto_now_add=True)
    received_at = models.DateTimeField("reçu le", null=True, blank=True)

    class Meta:
        ordering = ["-requested_at", "-id"]
        verbose_name = "demande de devis fournisseur"
        verbose_name_plural = "demandes de devis fournisseur"
        constraints = [
            models.UniqueConstraint(
                fields=["comparison_id", "supplier"],
                name="unique_supplier_per_quote_comparison",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="supplier_quote_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__isnull=True) | models.Q(unit_price__gte=0),
                name="supplier_quote_price_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(tax_rate__gte=0, tax_rate__lte=100),
                name="supplier_quote_tax_range",
            ),
            models.CheckConstraint(
                condition=models.Q(quality_rating__isnull=True)
                | models.Q(quality_rating__gte=1, quality_rating__lte=5),
                name="supplier_quote_quality_range",
            ),
        ]

    def __str__(self):
        return f"{self.product_name} — {self.supplier.company_name}"
