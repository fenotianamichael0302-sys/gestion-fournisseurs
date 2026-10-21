from rest_framework import serializers

from payments.models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)
    supplier_name = serializers.CharField(source="invoice.supplier.company_name", read_only=True)

    class Meta:
        model = Payment
        fields = (
            "id",
            "invoice",
            "invoice_number",
            "supplier_name",
            "payment_date",
            "amount",
            "method",
            "reference",
            "notes",
            "recorded_by",
            "created_at",
        )
        read_only_fields = ("id", "recorded_by", "created_at")

    def validate(self, attrs):
        invoice = attrs.get("invoice", getattr(self.instance, "invoice", None))
        amount = attrs.get("amount", getattr(self.instance, "amount", None))
        reference = attrs.get(
            "reference",
            getattr(self.instance, "reference", ""),
        ).strip()
        if self.instance is None and not reference:
            raise serializers.ValidationError(
                {"reference": "La référence du règlement est obligatoire."}
            )
        if invoice and amount is not None:
            allowed_balance = invoice.balance_due
            if self.instance and self.instance.invoice_id == invoice.id:
                allowed_balance += self.instance.amount
            if amount > allowed_balance:
                raise serializers.ValidationError(
                    {"amount": "Le paiement dépasse le solde restant de la facture."}
                )
        return attrs
