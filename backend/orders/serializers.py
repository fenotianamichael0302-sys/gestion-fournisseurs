from django.db import transaction
from django.db.models import Sum, F
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from orders.models import Delivery, DeliveryLine, PurchaseOrder, PurchaseOrderLine
from orders.services import create_purchase_order
from suppliers.models import Supplier


class PurchaseOrderLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseOrderLine
        fields = ("id", "product_name", "quantity", "unit_price", "tax_rate")
        read_only_fields = ("id",)


class PurchaseOrderSerializer(serializers.ModelSerializer):
    lines = PurchaseOrderLineSerializer(many=True)
    supplier_name = serializers.CharField(source="supplier.company_name", read_only=True)
    approved_by_username = serializers.CharField(
        source="approved_by.username", read_only=True
    )
    rejected_by_username = serializers.CharField(
        source="rejected_by.username", read_only=True
    )
    total_ht = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    total_tax = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    total_ttc = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = (
            "id",
            "order_number",
            "supplier",
            "supplier_name",
            "order_date",
            "expected_delivery_date",
            "status",
            "approved_by",
            "approved_by_username",
            "approved_at",
            "rejected_by",
            "rejected_by_username",
            "rejected_at",
            "rejection_reason",
            "terms",
            "notes",
            "lines",
            "total_ht",
            "total_tax",
            "total_ttc",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "order_number",
            "status",
            "approved_by",
            "approved_at",
            "rejected_by",
            "rejected_at",
            "rejection_reason",
            "created_by",
            "created_at",
            "updated_at",
        )

    def to_internal_value(self, data):
        if "status" in data:
            raise serializers.ValidationError(
                {"status": "Utilisez l'action de workflow correspondante pour changer le statut."}
            )
        return super().to_internal_value(data)

    def validate_supplier(self, supplier):
        if supplier.is_deleted or supplier.status != Supplier.Status.ACTIVE:
            raise serializers.ValidationError(
                "Une commande ne peut être créée qu'auprès d'un fournisseur actif."
            )
        return supplier

    def validate(self, attrs):
        if not attrs.get("lines") and self.instance is None:
            raise serializers.ValidationError(
                {"lines": "Une commande doit contenir au moins une ligne."}
            )
        if self.instance and self.instance.status != PurchaseOrder.Status.DRAFT:
            raise serializers.ValidationError(
                "Seul un brouillon peut être modifié."
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        return create_purchase_order(
            validated_data=validated_data,
            created_by=self.context["request"].user,
        )

    @transaction.atomic
    def update(self, instance, validated_data):
        lines = validated_data.pop("lines", None)
        for attribute, value in validated_data.items():
            setattr(instance, attribute, value)
        instance.save()
        if lines is not None:
            instance.lines.all().delete()
            for line_data in lines:
                PurchaseOrderLine.objects.create(order=instance, **line_data)
        return instance


class DeliveryLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(
        source="order_line.product_name", read_only=True
    )
    quantity_ordered = serializers.DecimalField(
        source="order_line.quantity",
        max_digits=12,
        decimal_places=3,
        read_only=True,
    )

    class Meta:
        model = DeliveryLine
        fields = (
            "id",
            "order_line",
            "product_name",
            "quantity_ordered",
            "quantity_received",
            "quantity_damaged",
            "quantity_missing",
            "notes",
        )
        read_only_fields = ("id",)

    def validate(self, attrs):
        if attrs.get("quantity_damaged", 0) > attrs["quantity_received"]:
            raise serializers.ValidationError(
                {"quantity_damaged": "La quantité endommagée dépasse la quantité reçue."}
            )
        return attrs


class DeliverySerializer(serializers.ModelSerializer):
    lines = DeliveryLineSerializer(many=True)
    order_number = serializers.CharField(source="order.order_number", read_only=True)
    supplier_name = serializers.CharField(
        source="order.supplier.company_name", read_only=True
    )
    created_by_username = serializers.CharField(
        source="created_by.username", read_only=True
    )

    class Meta:
        model = Delivery
        fields = (
            "id",
            "order",
            "order_number",
            "supplier_name",
            "delivery_date",
            "notes",
            "lines",
            "created_by",
            "created_by_username",
            "created_at",
        )
        read_only_fields = ("id", "created_by", "created_at")

    def validate(self, attrs):
        order = attrs.get("order")
        lines = attrs.get("lines", [])
        if not lines:
            raise serializers.ValidationError(
                {"lines": "Une réception doit contenir au moins une ligne."}
            )
        if order and order.status not in (
            PurchaseOrder.Status.APPROVED,
            PurchaseOrder.Status.IN_DELIVERY,
            PurchaseOrder.Status.PARTIALLY_DELIVERED,
        ):
            raise serializers.ValidationError(
                {"order": "La commande doit être validée avant sa réception."}
            )
        line_ids = [line["order_line"].pk for line in lines]
        if len(line_ids) != len(set(line_ids)):
            raise serializers.ValidationError(
                {"lines": "Une ligne de commande ne peut apparaître qu'une fois par réception."}
            )
        if order and any(line["order_line"].order_id != order.pk for line in lines):
            raise serializers.ValidationError(
                {"lines": "Toutes les lignes doivent appartenir à la commande sélectionnée."}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        lines = validated_data.pop("lines")
        order = PurchaseOrder.objects.select_for_update().get(
            pk=validated_data["order"].pk
        )
        if order.status not in (
            PurchaseOrder.Status.APPROVED,
            PurchaseOrder.Status.IN_DELIVERY,
            PurchaseOrder.Status.PARTIALLY_DELIVERED,
        ):
            raise serializers.ValidationError(
                {"order": "La commande doit être validée avant sa réception."}
            )

        delivery = Delivery.objects.create(
            **validated_data,
            created_by=self.context["request"].user,
        )
        for line_data in lines:
            order_line = line_data["order_line"]
            already_received = DeliveryLine.objects.filter(
                order_line=order_line
            ).aggregate(
                accepted=Sum(F("quantity_received") - F("quantity_damaged"))
            )["accepted"] or 0
            accepted_now = (
                line_data["quantity_received"] - line_data.get("quantity_damaged", 0)
            )
            if already_received + accepted_now > order_line.quantity:
                raise serializers.ValidationError(
                    {
                        "lines": (
                            f"La quantité acceptée dépasse la quantité commandée pour "
                            f"{order_line.product_name}."
                        )
                    }
                )
            delivery_line = DeliveryLine(delivery=delivery, **line_data)
            try:
                delivery_line.full_clean()
            except DjangoValidationError as exc:
                raise serializers.ValidationError(exc.message_dict) from exc
            delivery_line.save()

        accepted_by_order_line = {
            item["order_line_id"]: item["accepted"] or 0
            for item in DeliveryLine.objects.filter(
                order_line__order=order
            )
            .values("order_line_id")
            .annotate(accepted=Sum(F("quantity_received") - F("quantity_damaged")))
        }
        has_received_quantity = any(accepted_by_order_line.values())
        fully_received = all(
            accepted_by_order_line.get(line.pk, 0) >= line.quantity
            for line in order.lines.all()
        )
        if fully_received:
            order.status = PurchaseOrder.Status.DELIVERED
        elif has_received_quantity:
            order.status = PurchaseOrder.Status.PARTIALLY_DELIVERED
        else:
            order.status = PurchaseOrder.Status.IN_DELIVERY
        order.save(update_fields=["status", "updated_at"])
        return delivery
