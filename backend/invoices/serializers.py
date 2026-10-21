from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from invoices.models import Invoice, InvoiceLine


class InvoiceLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLine
        fields = ("id", "product_name", "quantity", "unit_price", "tax_rate")
        read_only_fields = ("id",)


class InvoiceSerializer(serializers.ModelSerializer):
    lines = InvoiceLineSerializer(many=True)
    supplier_name = serializers.CharField(source="supplier.company_name", read_only=True)
    total_ht = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    total_tax = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    total_ttc = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    amount_paid = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    balance_due = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    status = serializers.CharField(read_only=True)

    class Meta:
        model = Invoice
        fields = (
            "id",
            "supplier",
            "supplier_name",
            "order",
            "invoice_number",
            "invoice_date",
            "due_date",
            "attachment",
            "notes",
            "lines",
            "total_ht",
            "total_tax",
            "total_ttc",
            "amount_paid",
            "balance_due",
            "status",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_by", "created_at", "updated_at")

    def validate(self, attrs):
        supplier = attrs.get("supplier", getattr(self.instance, "supplier", None))
        order = attrs.get("order", getattr(self.instance, "order", None))
        invoice_date = attrs.get("invoice_date", getattr(self.instance, "invoice_date", None))
        due_date = attrs.get("due_date", getattr(self.instance, "due_date", None))
        errors = {}
        if order and supplier and order.supplier_id != supplier.id:
            errors["order"] = "La commande sélectionnée appartient à un autre fournisseur."
        if invoice_date and due_date and due_date < invoice_date:
            errors["due_date"] = "L'échéance ne peut pas précéder la date de facture."
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        lines = validated_data.pop("lines")
        validated_data["created_by"] = self.context["request"].user
        invoice = Invoice(**validated_data)
        try:
            invoice.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        invoice.save()
        for line_data in lines:
            InvoiceLine.objects.create(invoice=invoice, **line_data)
        return invoice

    @transaction.atomic
    def update(self, instance, validated_data):
        lines = validated_data.pop("lines", None)
        if instance.payments.exists():
            if lines is not None:
                raise serializers.ValidationError(
                    {"lines": "Les lignes ne peuvent plus être modifiées après un paiement."}
                )
            if any(
                validated_data.get(field, getattr(instance, field)) != getattr(instance, field)
                for field in ("supplier", "order")
            ):
                raise serializers.ValidationError(
                    "Le fournisseur et la commande ne peuvent plus changer après un paiement."
                )
        for attribute, value in validated_data.items():
            setattr(instance, attribute, value)
        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        instance.save()
        if lines is not None:
            instance.lines.all().delete()
            for line_data in lines:
                InvoiceLine.objects.create(invoice=instance, **line_data)
        return instance
