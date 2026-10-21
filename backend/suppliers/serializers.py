from decimal import Decimal

from rest_framework import serializers

from orders.models import PurchaseOrder
from accounts.models import User
from suppliers.models import Supplier, SupplierEvaluation, SupplierQuote


class SupplierSerializer(serializers.ModelSerializer):
    evaluation_count = serializers.IntegerField(read_only=True)
    quality_rating = serializers.FloatField(read_only=True, allow_null=True)
    delivery_rating = serializers.FloatField(read_only=True, allow_null=True)
    price_rating = serializers.FloatField(read_only=True, allow_null=True)
    reliability_rating = serializers.FloatField(read_only=True, allow_null=True)

    class Meta:
        model = Supplier
        exclude = ("is_deleted", "deleted_at", "deleted_by")
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "evaluation_count",
            "quality_rating",
            "delivery_rating",
            "price_rating",
            "reliability_rating",
        )

    def get_fields(self):
        fields = super().get_fields()
        user = getattr(self.context.get("request"), "user", None)
        if getattr(user, "role", None) != User.Role.ADMINISTRATEUR:
            for field in ("bank_name", "bank_account", "swift"):
                fields.pop(field, None)
        return fields


class SupplierEvaluationSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.company_name", read_only=True)
    order_number = serializers.CharField(source="order.order_number", read_only=True)
    evaluated_by_username = serializers.CharField(
        source="evaluated_by.username", read_only=True
    )

    class Meta:
        model = SupplierEvaluation
        fields = (
            "id",
            "supplier",
            "supplier_name",
            "order",
            "order_number",
            "quality_rating",
            "delivery_rating",
            "price_rating",
            "reliability_rating",
            "comment",
            "evaluated_by",
            "evaluated_by_username",
            "created_at",
        )
        read_only_fields = ("id", "evaluated_by", "created_at")

    def validate(self, attrs):
        order = attrs.get("order")
        supplier = attrs.get("supplier")
        if order and supplier and order.supplier_id != supplier.id:
            raise serializers.ValidationError(
                {"order": "La commande sélectionnée appartient à un autre fournisseur."}
            )
        if order and order.status != PurchaseOrder.Status.DELIVERED:
            raise serializers.ValidationError(
                {"order": "Seule une commande entièrement livrée peut être évaluée."}
            )
        if (
            order
            and self.instance is None
            and SupplierEvaluation.objects.filter(
                order=order,
                evaluated_by=self.context["request"].user,
            ).exists()
        ):
            raise serializers.ValidationError(
                {"order": "Vous avez déjà évalué cette commande."}
            )
        return attrs


class SupplierQuoteSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.company_name", read_only=True)
    requested_by_username = serializers.CharField(
        source="requested_by.username", read_only=True
    )

    class Meta:
        model = SupplierQuote
        fields = (
            "id",
            "comparison_id",
            "supplier",
            "supplier_name",
            "product_name",
            "quantity",
            "status",
            "unit_price",
            "tax_rate",
            "delivery_days",
            "quality_rating",
            "payment_terms",
            "notes",
            "requested_by",
            "requested_by_username",
            "requested_at",
            "received_at",
        )
        read_only_fields = (
            "id",
            "comparison_id",
            "status",
            "requested_by",
            "requested_at",
            "received_at",
        )


class QuoteRequestBatchSerializer(serializers.Serializer):
    product_name = serializers.CharField(max_length=255)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"))
    supplier_ids = serializers.PrimaryKeyRelatedField(
        queryset=Supplier.objects.filter(
            is_deleted=False,
            status=Supplier.Status.ACTIVE,
        ),
        many=True,
    )

    def validate_supplier_ids(self, suppliers):
        if not suppliers:
            raise serializers.ValidationError("Sélectionnez au moins un fournisseur.")
        if len({supplier.pk for supplier in suppliers}) != len(suppliers):
            raise serializers.ValidationError("Un fournisseur ne peut être sélectionné qu'une fois.")
        return suppliers


class QuoteResponseSerializer(serializers.Serializer):
    unit_price = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.00"),
    )
    tax_rate = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0.00"),
        max_value=Decimal("100.00"),
        required=False,
        default=Decimal("0.00"),
    )
    delivery_days = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    quality_rating = serializers.IntegerField(min_value=1, max_value=5, required=False, allow_null=True)
    payment_terms = serializers.CharField(required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
