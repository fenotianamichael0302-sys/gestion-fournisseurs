from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce, Round
from django.utils import timezone
from rest_framework import filters, viewsets
from rest_framework.exceptions import ValidationError

from accounts.permissions import CanManageProcurement
from invoices.models import Invoice, InvoiceLine
from payments.models import Payment
from invoices.serializers import InvoiceSerializer


class InvoiceViewSet(viewsets.ModelViewSet):
    serializer_class = InvoiceSerializer
    permission_classes = [CanManageProcurement]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["invoice_number", "supplier__company_name"]
    ordering_fields = ["invoice_date", "due_date", "invoice_number"]
    ordering = ["-invoice_date", "-id"]

    def get_queryset(self):
        queryset = Invoice.objects.select_related(
            "supplier", "order", "created_by"
        ).prefetch_related("lines", "payments")
        supplier_id = self.request.query_params.get("supplier")
        if supplier_id:
            if not supplier_id.isdecimal():
                raise ValidationError({"supplier": "Un identifiant numérique est requis."})
            queryset = queryset.filter(supplier_id=int(supplier_id))
        status = self.request.query_params.get("status")
        if status:
            if status not in Invoice.PaymentStatus.values:
                raise ValidationError({"status": "Statut de facture inconnu."})
            money = DecimalField(max_digits=18, decimal_places=2)
            quantity_price = Round(
                F("quantity") * F("unit_price"),
                precision=2,
                output_field=money,
            )
            line_tax = Round(
                quantity_price * F("tax_rate") / Value(Decimal("100.00")),
                precision=2,
                output_field=money,
            )
            line_totals = (
                InvoiceLine.objects.filter(invoice_id=OuterRef("pk"))
                .order_by()
                .values("invoice_id")
                .annotate(
                    total_ht=Sum(quantity_price, output_field=money),
                    total_tax=Sum(line_tax, output_field=money),
                )
            )
            paid_totals = (
                Payment.objects.filter(invoice_id=OuterRef("pk"))
                .order_by()
                .values("invoice_id")
                .annotate(total=Sum("amount"))
                .values("total")[:1]
            )
            queryset = queryset.annotate(
                _total_ht=Coalesce(
                    Subquery(line_totals.values("total_ht")[:1]),
                    Value(Decimal("0.00")),
                    output_field=money,
                ),
                _total_tax=Coalesce(
                    Subquery(line_totals.values("total_tax")[:1]),
                    Value(Decimal("0.00")),
                    output_field=money,
                ),
                _amount_paid=Coalesce(
                    Subquery(paid_totals),
                    Value(Decimal("0.00")),
                    output_field=money,
                ),
            ).annotate(_total_amount=F("_total_ht") + F("_total_tax"))
            total_amount = F("_total_amount")
            today = timezone.localdate()
            if status == Invoice.PaymentStatus.UNPAID:
                queryset = queryset.filter(
                    _amount_paid=Decimal("0.00"),
                    due_date__gte=today,
                )
            elif status == Invoice.PaymentStatus.OVERDUE:
                queryset = queryset.filter(
                    _amount_paid=Decimal("0.00"),
                    due_date__lt=today,
                )
            elif status == Invoice.PaymentStatus.PARTIALLY_PAID:
                queryset = queryset.filter(
                    _amount_paid__gt=Decimal("0.00"),
                    _amount_paid__lt=total_amount,
                )
            else:
                queryset = queryset.filter(
                    _total_amount__gt=Decimal("0.00"),
                    _amount_paid__gte=total_amount,
                )
        return queryset
