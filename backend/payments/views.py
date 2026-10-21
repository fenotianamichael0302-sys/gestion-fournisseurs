from django.db import transaction
from rest_framework import filters, serializers, viewsets
from rest_framework.exceptions import ValidationError

from accounts.permissions import CanManageProcurement
from invoices.models import Invoice
from payments.models import Payment
from payments.serializers import PaymentSerializer


class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [CanManageProcurement]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "invoice__invoice_number",
        "invoice__supplier__company_name",
        "reference",
    ]
    ordering_fields = ["payment_date", "amount"]
    ordering = ["-payment_date", "-id"]

    def get_queryset(self):
        queryset = Payment.objects.select_related(
            "invoice", "invoice__supplier", "recorded_by"
        )
        supplier_id = self.request.query_params.get("supplier")
        if supplier_id:
            if not supplier_id.isdecimal():
                raise ValidationError({"supplier": "Un identifiant numérique est requis."})
            queryset = queryset.filter(invoice__supplier_id=int(supplier_id))
        invoice_id = self.request.query_params.get("invoice")
        if invoice_id:
            if not invoice_id.isdecimal():
                raise ValidationError({"invoice": "Un identifiant numérique est requis."})
            queryset = queryset.filter(invoice_id=int(invoice_id))
        return queryset

    def perform_create(self, serializer):
        invoice_id = serializer.validated_data["invoice"].pk
        amount = serializer.validated_data["amount"]
        with transaction.atomic():
            invoice = Invoice.objects.select_for_update().get(pk=invoice_id)
            if amount > invoice.balance_due:
                raise serializers.ValidationError(
                    {"amount": "Le paiement dépasse le solde restant de la facture."}
                )
            reference = serializer.validated_data.get("reference", "").strip()
            if reference and Payment.objects.filter(
                invoice=invoice,
                reference=reference,
            ).exists():
                raise serializers.ValidationError(
                    {"reference": "Cette référence de paiement existe déjà pour la facture."}
                )
            serializer.save(recorded_by=self.request.user)

    def perform_update(self, serializer):
        payment = self.get_object()
        invoice = serializer.validated_data.get("invoice", payment.invoice)
        amount = serializer.validated_data.get("amount", payment.amount)
        invoice_ids = sorted({payment.invoice_id, invoice.pk})
        with transaction.atomic():
            locked_invoices = {
                item.pk: item
                for item in Invoice.objects.select_for_update()
                .filter(pk__in=invoice_ids)
                .order_by("pk")
            }
            target = locked_invoices[invoice.pk]
            allowed_balance = target.balance_due
            if payment.invoice_id == invoice.pk:
                allowed_balance += payment.amount
            if amount > allowed_balance:
                raise serializers.ValidationError(
                    {"amount": "Le paiement dépasse le solde restant de la facture."}
                )
            reference = serializer.validated_data.get("reference", payment.reference).strip()
            if reference and Payment.objects.filter(
                invoice=target,
                reference=reference,
            ).exclude(pk=payment.pk).exists():
                raise serializers.ValidationError(
                    {"reference": "Cette référence de paiement existe déjà pour la facture."}
                )
            serializer.save()
