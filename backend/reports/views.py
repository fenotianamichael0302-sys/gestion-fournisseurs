from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Avg, Count, DecimalField, ExpressionWrapper, F, Q, Sum, Value
from django.db.models.functions import Coalesce, Round, TruncMonth
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    PolymorphicProxySerializer,
    extend_schema,
)

from accounts.models import User
from accounts.permissions import CanManageProcurement
from invoices.models import Invoice, InvoiceLine
from orders.models import PurchaseOrder, PurchaseOrderLine
from payments.models import Payment
from reports.serializers import (
    DashboardSerializer,
    BuyerDashboardSerializer,
    InvoiceSummaryPageSerializer,
    MonthlyPurchaseSerializer,
    PriceComparisonPageSerializer,
    SupplierSpendingSerializer,
)
from reports.exports import export_report_response
from suppliers.models import Supplier


MONEY_FIELD = DecimalField(max_digits=24, decimal_places=2)
ZERO_AMOUNT = Value(Decimal("0.00"), output_field=MONEY_FIELD)
PURCHASE_STATUSES = (
    PurchaseOrder.Status.APPROVED,
    PurchaseOrder.Status.IN_DELIVERY,
    PurchaseOrder.Status.PARTIALLY_DELIVERED,
    PurchaseOrder.Status.DELIVERED,
)
EXPORT_PARAMETER = OpenApiParameter(
    name="export",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    required=False,
    enum=["pdf", "xlsx"],
    description="Télécharger le rapport au format PDF ou Excel.",
)


def _line_amount_expressions():
    total_ht = Round(
        ExpressionWrapper(
            F("quantity") * F("unit_price"),
            output_field=MONEY_FIELD,
        ),
        precision=2,
        output_field=MONEY_FIELD,
    )
    tax = Round(
        ExpressionWrapper(
            total_ht * F("tax_rate") / Value(100, output_field=MONEY_FIELD),
            output_field=MONEY_FIELD,
        ),
        precision=2,
        output_field=MONEY_FIELD,
    )
    return total_ht, tax


def _date_filter(queryset, field, request, supplier_field="supplier_id"):
    for parameter, lookup in (
        ("date_from", f"{field}__gte"),
        ("date_to", f"{field}__lte"),
    ):
        raw_date = request.query_params.get(parameter)
        if not raw_date:
            continue
        value = parse_date(raw_date)
        if not isinstance(value, date):
            raise ValidationError(
                {parameter: "La date doit respecter le format AAAA-MM-JJ."}
            )
        queryset = queryset.filter(**{lookup: value})
    supplier_id = request.query_params.get("supplier")
    if supplier_id:
        if not supplier_id.isdecimal():
            raise ValidationError({"supplier": "Un identifiant numérique est requis."})
        queryset = queryset.filter(**{supplier_field: int(supplier_id)})
    return queryset


def _invoice_summaries(request=None, queryset=None):
    line_ht, line_tax = _line_amount_expressions()
    invoices = queryset if queryset is not None else Invoice.objects.all()
    if request is not None:
        invoices = _date_filter(invoices, "invoice_date", request)
    line_totals = {
        item["invoice_id"]: item
        for item in InvoiceLine.objects.filter(invoice__in=invoices).values("invoice_id").annotate(
            total_ht=Coalesce(Sum(line_ht), ZERO_AMOUNT, output_field=MONEY_FIELD),
            total_tax=Coalesce(Sum(line_tax), ZERO_AMOUNT, output_field=MONEY_FIELD),
        )
    }
    paid_amounts = dict(
        Payment.objects.filter(invoice__in=invoices).values("invoice_id")
        .annotate(total=Sum("amount"))
        .values_list("invoice_id", "total")
    )
    today = timezone.localdate()
    summaries = []
    for invoice in invoices.values(
        "id",
        "invoice_number",
        "supplier_id",
        "supplier__company_name",
        "invoice_date",
        "due_date",
    ):
        totals = line_totals.get(invoice["id"], {})
        total_ht = totals.get("total_ht") or Decimal("0.00")
        total_tax = totals.get("total_tax") or Decimal("0.00")
        total = total_ht + total_tax
        paid = paid_amounts.get(invoice["id"]) or Decimal("0.00")
        balance = max(total - paid, Decimal("0.00"))
        if balance == 0 and total > 0:
            status = Invoice.PaymentStatus.PAID
        elif paid > 0:
            status = Invoice.PaymentStatus.PARTIALLY_PAID
        elif invoice["due_date"] < today:
            status = Invoice.PaymentStatus.OVERDUE
        else:
            status = Invoice.PaymentStatus.UNPAID
        summaries.append(
            {
                "id": invoice["id"],
                "invoice_number": invoice["invoice_number"],
                "supplier_id": invoice["supplier_id"],
                "supplier": invoice["supplier__company_name"],
                "invoice_date": invoice["invoice_date"],
                "due_date": invoice["due_date"],
                "total_ht": total_ht,
                "total_tax": total_tax,
                "total_ttc": total,
                "amount_paid": paid,
                "balance_due": balance,
                "status": status,
            }
        )
    return summaries


class ReportPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100


class DashboardView(APIView):
    permission_classes = [CanManageProcurement]

    @extend_schema(
        responses={
            200: PolymorphicProxySerializer(
                component_name="DashboardResponse",
                serializers=[DashboardSerializer, BuyerDashboardSerializer],
                resource_type_field_name=None,
            )
        }
    )
    def get(self, request):
        today = timezone.localdate()
        month_index = today.year * 12 + today.month - 1 - 11
        start_year, start_month_index = divmod(month_index, 12)
        chart_start = date(start_year, start_month_index + 1, 1)
        if request.user.role != User.Role.ADMINISTRATEUR:
            return Response(self._buyer_dashboard(request.user, today, chart_start))

        line_ht, line_tax = _line_amount_expressions()
        purchase_lines = PurchaseOrderLine.objects.filter(
            order__status__in=PURCHASE_STATUSES
        )
        total_purchases = purchase_lines.aggregate(
            ht=Coalesce(Sum(line_ht), ZERO_AMOUNT, output_field=MONEY_FIELD),
            tax=Coalesce(Sum(line_tax), ZERO_AMOUNT, output_field=MONEY_FIELD),
        )
        monthly = (
            purchase_lines.filter(order__order_date__gte=chart_start)
            .annotate(month=TruncMonth("order__order_date"))
            .values("month")
            .annotate(
                total_ht=Coalesce(Sum(line_ht), ZERO_AMOUNT, output_field=MONEY_FIELD),
                total_tax=Coalesce(Sum(line_tax), ZERO_AMOUNT, output_field=MONEY_FIELD),
            )
            .order_by("month")
        )
        top_suppliers = (
            purchase_lines.values(
                "order__supplier_id",
                "order__supplier__company_name",
            )
            .annotate(
                total_ht=Coalesce(Sum(line_ht), ZERO_AMOUNT, output_field=MONEY_FIELD),
                total_tax=Coalesce(Sum(line_tax), ZERO_AMOUNT, output_field=MONEY_FIELD),
            )
            .order_by("-total_ht", "order__supplier__company_name")[:5]
        )
        status_counts = dict(
            PurchaseOrder.objects.values("status")
            .annotate(total=Count("id"))
            .values_list("status", "total")
        )
        invoices = _invoice_summaries()
        overdue = [
            item
            for item in invoices
            if item["balance_due"] > 0 and item["due_date"] < today
        ]
        due_soon = [
            item
            for item in invoices
            if item["balance_due"] > 0
            and today <= item["due_date"] <= today + timedelta(days=7)
        ]
        pending_since = today - timedelta(days=30)
        old_pending = list(
            PurchaseOrder.objects.filter(
                status=PurchaseOrder.Status.PENDING,
                order_date__lte=pending_since,
            )
            .annotate(supplier_name=F("supplier__company_name"))
            .values(
                "id",
                "order_number",
                "order_date",
                "supplier_name",
                "expected_delivery_date",
                "status",
            )
            .order_by("order_date")[:10]
        )
        overdue_deliveries = list(
            PurchaseOrder.objects.filter(
                status__in=(
                    PurchaseOrder.Status.APPROVED,
                    PurchaseOrder.Status.IN_DELIVERY,
                    PurchaseOrder.Status.PARTIALLY_DELIVERED,
                ),
                expected_delivery_date__lt=today,
            )
            .annotate(supplier_name=F("supplier__company_name"))
            .values(
                "id",
                "order_number",
                "order_date",
                "supplier_name",
                "expected_delivery_date",
                "status",
            )
            .order_by("expected_delivery_date")[:10]
        )
        return Response(
            {
                "total_suppliers": Supplier.objects.filter(is_deleted=False).count(),
                "active_suppliers": Supplier.objects.filter(
                    is_deleted=False,
                    status=Supplier.Status.ACTIVE,
                ).count(),
                "inactive_suppliers": Supplier.objects.filter(
                    is_deleted=False,
                ).exclude(status=Supplier.Status.ACTIVE).count(),
                "orders_in_progress": PurchaseOrder.objects.filter(
                    status__in=[
                        PurchaseOrder.Status.PENDING,
                        PurchaseOrder.Status.APPROVED,
                        PurchaseOrder.Status.IN_DELIVERY,
                        PurchaseOrder.Status.PARTIALLY_DELIVERED,
                    ]
                ).count(),
                "unpaid_invoices": sum(
                    item["balance_due"] > 0 for item in invoices
                ),
                "total_purchases": total_purchases["ht"] + total_purchases["tax"],
                "alerts": {
                    "overdue_invoices": overdue[:10],
                    "due_soon_invoices": due_soon[:10],
                    "old_pending_orders": old_pending,
                    "overdue_deliveries": overdue_deliveries,
                },
                "purchases_by_month": [
                    {
                        "month": item["month"].strftime("%Y-%m"),
                        "total": item["total_ht"] + item["total_tax"],
                    }
                    for item in monthly
                ],
                "top_suppliers": [
                    {
                        "supplier": item["order__supplier__company_name"],
                        "total": item["total_ht"] + item["total_tax"],
                    }
                    for item in top_suppliers
                ],
                "orders_by_status": [
                    {"status": status, "label": label, "total": status_counts.get(status, 0)}
                    for status, label in PurchaseOrder.Status.choices
                ],
            }
        )

    def _buyer_dashboard(self, user, today, chart_start):
        orders = PurchaseOrder.objects.filter(created_by=user)
        status_counts = dict(
            orders.values("status")
            .annotate(total=Count("id"))
            .values_list("status", "total")
        )

        purchase_lines = PurchaseOrderLine.objects.filter(
            order__created_by=user,
            order__status__in=PURCHASE_STATUSES,
        )
        line_ht, line_tax = _line_amount_expressions()
        purchase_totals = purchase_lines.aggregate(
            ht=Coalesce(Sum(line_ht), ZERO_AMOUNT, output_field=MONEY_FIELD),
            tax=Coalesce(Sum(line_tax), ZERO_AMOUNT, output_field=MONEY_FIELD),
        )
        monthly_totals = {
            item["month"].strftime("%Y-%m"): item["total_ht"] + item["total_tax"]
            for item in (
                purchase_lines.filter(
                    order__order_date__gte=chart_start,
                    order__order_date__lte=today,
                )
                .annotate(month=TruncMonth("order__order_date"))
                .values("month")
                .annotate(
                    total_ht=Coalesce(Sum(line_ht), ZERO_AMOUNT, output_field=MONEY_FIELD),
                    total_tax=Coalesce(Sum(line_tax), ZERO_AMOUNT, output_field=MONEY_FIELD),
                )
                .order_by("month")
            )
        }
        purchases_by_month = []
        for offset in range(12):
            month_index = chart_start.year * 12 + chart_start.month - 1 + offset
            year, month_index = divmod(month_index, 12)
            month = date(year, month_index + 1, 1)
            month_key = month.strftime("%Y-%m")
            purchases_by_month.append(
                {"month": month_key, "total": monthly_totals.get(month_key, Decimal("0.00"))}
            )

        invoices = Invoice.objects.filter(
            Q(order__created_by=user)
            | Q(order__isnull=True, created_by=user)
        )
        invoice_summaries = _invoice_summaries(queryset=invoices)
        recent_orders = list(
            orders.select_related("supplier")
            .prefetch_related("lines")
            [:8]
        )
        status_labels = dict(PurchaseOrder.Status.choices)
        return {
            "total_orders": orders.count(),
            "pending_orders": status_counts.get(PurchaseOrder.Status.PENDING, 0),
            "approved_orders": status_counts.get(PurchaseOrder.Status.APPROVED, 0),
            "deliveries_to_receive": sum(
                status_counts.get(status, 0)
                for status in (
                    PurchaseOrder.Status.APPROVED,
                    PurchaseOrder.Status.IN_DELIVERY,
                    PurchaseOrder.Status.PARTIALLY_DELIVERED,
                )
            ),
            "unpaid_invoices": sum(
                item["balance_due"] > 0 for item in invoice_summaries
            ),
            "total_purchases": purchase_totals["ht"] + purchase_totals["tax"],
            "purchases_by_month": purchases_by_month,
            "orders_by_status": [
                {
                    "status": status,
                    "label": label,
                    "total": status_counts.get(status, 0),
                }
                for status, label in PurchaseOrder.Status.choices
            ],
            "recent_orders": [
                {
                    "id": order.id,
                    "order_number": order.order_number,
                    "supplier_name": order.supplier.company_name,
                    "order_date": order.order_date,
                    "expected_delivery_date": order.expected_delivery_date,
                    "status": order.status,
                    "status_label": status_labels[order.status],
                    "total_ttc": order.total_ttc,
                    "lines": [
                        {
                            "product_name": line.product_name,
                            "quantity": line.quantity,
                            "unit_price": line.unit_price,
                            "tax_rate": line.tax_rate,
                        }
                        for line in order.lines.all()
                    ],
                }
                for order in recent_orders
            ],
        }


class SupplierSpendingReportView(APIView):
    permission_classes = [CanManageProcurement]

    @extend_schema(
        parameters=[EXPORT_PARAMETER],
        responses=SupplierSpendingSerializer(many=True),
    )
    def get(self, request):
        line_ht, line_tax = _line_amount_expressions()
        lines = _date_filter(
            PurchaseOrderLine.objects.filter(order__status__in=PURCHASE_STATUSES),
            "order__order_date",
            request,
            supplier_field="order__supplier_id",
        )
        grouped = (
            lines.values("order__supplier_id", "order__supplier__company_name")
            .annotate(
                total_ht=Coalesce(Sum(line_ht), ZERO_AMOUNT, output_field=MONEY_FIELD),
                total_tax=Coalesce(Sum(line_tax), ZERO_AMOUNT, output_field=MONEY_FIELD),
            )
            .order_by("-total_ht", "order__supplier__company_name")
        )
        rows = [
            {
                "supplier_id": item["order__supplier_id"],
                "supplier": item["order__supplier__company_name"],
                "total_ht": item["total_ht"],
                "total_tax": item["total_tax"],
                "total_ttc": item["total_ht"] + item["total_tax"],
            }
            for item in grouped
        ]
        exported = export_report_response(
            request,
            "Dépenses par fournisseur",
            "depenses-par-fournisseur",
            rows,
            [
                ("supplier", "Fournisseur"),
                ("total_ht", "Total HT"),
                ("total_tax", "Taxes"),
                ("total_ttc", "Total TTC"),
            ],
        )
        if exported:
            return exported
        return Response(rows)


class MonthlyPurchasesReportView(APIView):
    permission_classes = [CanManageProcurement]

    @extend_schema(
        parameters=[EXPORT_PARAMETER],
        responses=MonthlyPurchaseSerializer(many=True),
    )
    def get(self, request):
        raw_year = request.query_params.get("year", str(timezone.localdate().year))
        if not raw_year.isdecimal() or len(raw_year) != 4:
            raise ValidationError({"year": "L'année doit être au format AAAA."})
        year = int(raw_year)
        line_ht, line_tax = _line_amount_expressions()
        purchase_lines = _date_filter(
            PurchaseOrderLine.objects.filter(
                order__order_date__year=year,
                order__status__in=PURCHASE_STATUSES,
            ),
            "order__order_date",
            request,
            supplier_field="order__supplier_id",
        )
        grouped = (
            purchase_lines
            .annotate(month=TruncMonth("order__order_date"))
            .values("month")
            .annotate(
                total_ht=Coalesce(Sum(line_ht), ZERO_AMOUNT, output_field=MONEY_FIELD),
                total_tax=Coalesce(Sum(line_tax), ZERO_AMOUNT, output_field=MONEY_FIELD),
            )
            .order_by("month")
        )
        rows = [
            {
                "month": item["month"].strftime("%Y-%m"),
                "total_ht": item["total_ht"],
                "total_tax": item["total_tax"],
                "total_ttc": item["total_ht"] + item["total_tax"],
            }
            for item in grouped
        ]
        exported = export_report_response(
            request,
            f"Achats par mois — {year}",
            f"achats-par-mois-{year}",
            rows,
            [
                ("month", "Mois"),
                ("total_ht", "Total HT"),
                ("total_tax", "Taxes"),
                ("total_ttc", "Total TTC"),
            ],
        )
        if exported:
            return exported
        return Response(rows)


class UnpaidInvoicesReportView(APIView):
    permission_classes = [CanManageProcurement]

    @extend_schema(
        parameters=[EXPORT_PARAMETER],
        responses=InvoiceSummaryPageSerializer,
    )
    def get(self, request):
        invoices = [
            item for item in _invoice_summaries(request) if item["balance_due"] > 0
        ]
        exported = export_report_response(
            request,
            "Factures impayées",
            "factures-impayees",
            invoices,
            [
                ("invoice_number", "N° facture"),
                ("supplier", "Fournisseur"),
                ("invoice_date", "Date facture"),
                ("due_date", "Échéance"),
                ("total_ttc", "Total TTC"),
                ("amount_paid", "Montant payé"),
                ("balance_due", "Reste dû"),
                ("status", "Statut"),
            ],
        )
        if exported:
            return exported
        paginator = ReportPagination()
        page = paginator.paginate_queryset(invoices, request, view=self)
        return paginator.get_paginated_response(page)


class PriceComparisonReportView(APIView):
    permission_classes = [CanManageProcurement]

    @extend_schema(
        parameters=[EXPORT_PARAMETER],
        responses=PriceComparisonPageSerializer,
    )
    def get(self, request):
        queryset = _date_filter(
            PurchaseOrderLine.objects.filter(order__status__in=PURCHASE_STATUSES),
            "order__order_date",
            request,
            supplier_field="order__supplier_id",
        )
        product = request.query_params.get("product", "").strip()
        if product:
            queryset = queryset.filter(product_name__icontains=product)
        comparison = (
            queryset.values("product_name")
            .annotate(
                supplier_id=F("order__supplier_id"),
                supplier=F("order__supplier__company_name"),
                average_price=Avg("unit_price"),
            )
            .values("product_name", "supplier_id", "supplier", "average_price")
            .order_by("product_name", "supplier")
        )
        if request.query_params.get("export"):
            exported = export_report_response(
                request,
                "Comparaison des prix",
                "comparaison-des-prix",
                list(comparison),
                [
                    ("product_name", "Produit"),
                    ("supplier", "Fournisseur"),
                    ("average_price", "Prix unitaire moyen"),
                ],
            )
            if exported:
                return exported
        paginator = ReportPagination()
        page = paginator.paginate_queryset(comparison, request, view=self)
        return paginator.get_paginated_response(page)
