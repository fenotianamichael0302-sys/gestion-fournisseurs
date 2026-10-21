from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from invoices.models import Invoice, InvoiceLine
from orders.models import PurchaseOrder, PurchaseOrderLine
from suppliers.models import Supplier


class ProcurementReportTests(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(
            username="reports-buyer",
            role=User.Role.ACHETEUR,
        )
        self.admin = User.objects.create_user(
            username="reports-admin",
            role=User.Role.ADMINISTRATEUR,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.buyer)
        self.active_supplier = Supplier.objects.create(company_name="Active report supplier")
        self.inactive_supplier = Supplier.objects.create(
            company_name="Inactive report supplier",
            status=Supplier.Status.INACTIVE,
        )
        self._create_order(
            "BC-REPORT-DRAFT",
            self.active_supplier,
            "Draft product",
            PurchaseOrder.Status.DRAFT,
        )
        self._create_order(
            "BC-REPORT-APPROVED",
            self.active_supplier,
            "Approved product",
            PurchaseOrder.Status.APPROVED,
        )

    def _create_order(self, number, supplier, product, status):
        order = PurchaseOrder.objects.create(
            order_number=number,
            supplier=supplier,
            order_date=date.today(),
            status=status,
            created_by=self.buyer,
        )
        PurchaseOrderLine.objects.create(
            order=order,
            product_name=product,
            quantity=2,
            unit_price="100.00",
            tax_rate="20.00",
        )
        return order

    def test_dashboard_and_spending_reports_use_confirmed_orders_and_supplier_status(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get("/api/reports/dashboard/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["total_suppliers"], 2)
        self.assertEqual(response.data["active_suppliers"], 1)
        self.assertEqual(response.data["inactive_suppliers"], 1)
        self.assertEqual(response.data["total_purchases"], Decimal("240.00"))
        self.assertEqual(response.data["orders_in_progress"], 1)
        self.assertIn("overdue_deliveries", response.data["alerts"])

        response = self.client.get("/api/reports/spending-by-supplier/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["total_ttc"], Decimal("240.00"))

        response = self.client.get("/api/reports/price-comparison/")
        self.assertEqual(response.status_code, 200, response.data)
        products = {item["product_name"] for item in response.data["results"]}
        self.assertEqual(products, {"Approved product"})

    def test_buyer_dashboard_is_scoped_to_the_authenticated_buyer(self):
        other_buyer = User.objects.create_user(
            username="other-reports-buyer",
            role=User.Role.ACHETEUR,
        )
        other_order = self._create_order(
            "BC-OTHER-BUYER",
            self.active_supplier,
            "Other buyer product",
            PurchaseOrder.Status.APPROVED,
        )
        other_order.created_by = other_buyer
        other_order.save(update_fields=["created_by"])
        own_invoice = Invoice.objects.create(
            supplier=self.active_supplier,
            order=PurchaseOrder.objects.get(order_number="BC-REPORT-APPROVED"),
            invoice_number="INV-REPORT-OWN",
            invoice_date=date.today(),
            due_date=date.today(),
            created_by=self.buyer,
        )
        InvoiceLine.objects.create(
            invoice=own_invoice,
            product_name="Own invoice item",
            quantity=1,
            unit_price="100.00",
            tax_rate="20.00",
        )
        other_invoice = Invoice.objects.create(
            supplier=self.active_supplier,
            order=other_order,
            invoice_number="INV-REPORT-OTHER",
            invoice_date=date.today(),
            due_date=date.today(),
            created_by=other_buyer,
        )
        InvoiceLine.objects.create(
            invoice=other_invoice,
            product_name="Other invoice item",
            quantity=1,
            unit_price="500.00",
            tax_rate="20.00",
        )

        response = self.client.get("/api/reports/dashboard/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["total_orders"], 2)
        self.assertEqual(response.data["pending_orders"], 0)
        self.assertEqual(response.data["approved_orders"], 1)
        self.assertEqual(response.data["deliveries_to_receive"], 1)
        self.assertEqual(response.data["unpaid_invoices"], 1)
        self.assertEqual(response.data["total_purchases"], Decimal("240.00"))
        self.assertEqual(len(response.data["purchases_by_month"]), 12)
        self.assertEqual(
            sum(item["total"] for item in response.data["orders_by_status"]),
            2,
        )
        self.assertEqual(
            [item["order_number"] for item in response.data["recent_orders"]],
            ["BC-REPORT-APPROVED", "BC-REPORT-DRAFT"],
        )
        self.assertEqual(
            response.data["recent_orders"][0]["lines"][0]["product_name"],
            "Approved product",
        )

        private_order_response = self.client.get(f"/api/orders/{other_order.id}/")
        self.assertEqual(private_order_response.status_code, 404)

    def test_dashboard_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/reports/dashboard/")
        self.assertIn(response.status_code, (401, 403))
