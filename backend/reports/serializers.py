from rest_framework import serializers


class InvoiceSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    invoice_number = serializers.CharField()
    supplier_id = serializers.IntegerField()
    supplier_name = serializers.CharField()
    invoice_date = serializers.DateField()
    due_date = serializers.DateField()
    total_ht = serializers.DecimalField(max_digits=24, decimal_places=2)
    total_tax = serializers.DecimalField(max_digits=24, decimal_places=2)
    total_ttc = serializers.DecimalField(max_digits=24, decimal_places=2)
    amount_paid = serializers.DecimalField(max_digits=24, decimal_places=2)
    balance_due = serializers.DecimalField(max_digits=24, decimal_places=2)
    status = serializers.CharField()


class OldPendingOrderSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    order_number = serializers.CharField()
    order_date = serializers.DateField()
    supplier_name = serializers.CharField()
    expected_delivery_date = serializers.DateField(allow_null=True, required=False)
    status = serializers.CharField(required=False)


class DashboardAlertsSerializer(serializers.Serializer):
    overdue_invoices = InvoiceSummarySerializer(many=True)
    due_soon_invoices = InvoiceSummarySerializer(many=True)
    old_pending_orders = OldPendingOrderSerializer(many=True)
    overdue_deliveries = OldPendingOrderSerializer(many=True)


class MonthlySeriesSerializer(serializers.Serializer):
    month = serializers.CharField()
    total = serializers.DecimalField(max_digits=24, decimal_places=2)


class TopSupplierSerializer(serializers.Serializer):
    supplier = serializers.CharField()
    total = serializers.DecimalField(max_digits=24, decimal_places=2)


class OrderStatusSerializer(serializers.Serializer):
    status = serializers.CharField()
    label = serializers.CharField()
    total = serializers.IntegerField()


class DashboardSerializer(serializers.Serializer):
    total_suppliers = serializers.IntegerField()
    active_suppliers = serializers.IntegerField()
    inactive_suppliers = serializers.IntegerField()
    orders_in_progress = serializers.IntegerField()
    unpaid_invoices = serializers.IntegerField()
    total_purchases = serializers.DecimalField(max_digits=24, decimal_places=2)
    alerts = DashboardAlertsSerializer()
    purchases_by_month = MonthlySeriesSerializer(many=True)
    top_suppliers = TopSupplierSerializer(many=True)
    orders_by_status = OrderStatusSerializer(many=True)


class BuyerOrderLineSerializer(serializers.Serializer):
    product_name = serializers.CharField()
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3)
    unit_price = serializers.DecimalField(max_digits=14, decimal_places=2)
    tax_rate = serializers.DecimalField(max_digits=5, decimal_places=2)


class BuyerRecentOrderSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    order_number = serializers.CharField()
    supplier_name = serializers.CharField()
    order_date = serializers.DateField()
    expected_delivery_date = serializers.DateField(allow_null=True)
    status = serializers.CharField()
    status_label = serializers.CharField()
    total_ttc = serializers.DecimalField(max_digits=24, decimal_places=2)
    lines = BuyerOrderLineSerializer(many=True)


class BuyerDashboardSerializer(serializers.Serializer):
    total_orders = serializers.IntegerField()
    pending_orders = serializers.IntegerField()
    approved_orders = serializers.IntegerField()
    deliveries_to_receive = serializers.IntegerField()
    unpaid_invoices = serializers.IntegerField()
    total_purchases = serializers.DecimalField(max_digits=24, decimal_places=2)
    purchases_by_month = MonthlySeriesSerializer(many=True)
    orders_by_status = OrderStatusSerializer(many=True)
    recent_orders = BuyerRecentOrderSerializer(many=True)


class SupplierSpendingSerializer(serializers.Serializer):
    supplier_id = serializers.IntegerField()
    supplier = serializers.CharField()
    total_ht = serializers.DecimalField(max_digits=24, decimal_places=2)
    total_tax = serializers.DecimalField(max_digits=24, decimal_places=2)
    total_ttc = serializers.DecimalField(max_digits=24, decimal_places=2)


class MonthlyPurchaseSerializer(serializers.Serializer):
    month = serializers.CharField()
    total_ht = serializers.DecimalField(max_digits=24, decimal_places=2)
    total_tax = serializers.DecimalField(max_digits=24, decimal_places=2)
    total_ttc = serializers.DecimalField(max_digits=24, decimal_places=2)


class InvoiceSummaryPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = InvoiceSummarySerializer(many=True)


class PriceComparisonSerializer(serializers.Serializer):
    product_name = serializers.CharField()
    supplier_id = serializers.IntegerField()
    supplier = serializers.CharField()
    average_price = serializers.DecimalField(max_digits=14, decimal_places=2)


class PriceComparisonPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = PriceComparisonSerializer(many=True)
