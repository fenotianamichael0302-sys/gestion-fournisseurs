from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from orders.models import Delivery, PurchaseOrder, PurchaseOrderLine
from suppliers.models import Supplier


class PurchaseOrderTotalsTests(TestCase):
    def test_line_and_order_totals_include_tax(self):
        supplier = Supplier.objects.create(company_name="Fournisseur Test")
        order = PurchaseOrder.objects.create(
            order_number="BC-2026-TEST",
            supplier=supplier,
            order_date=date(2026, 1, 2),
        )
        PurchaseOrderLine.objects.create(
            order=order,
            product_name="Produit test",
            quantity=2,
            unit_price=Decimal("125.00"),
            tax_rate=Decimal("20.00"),
        )

        self.assertEqual(order.total_ht, Decimal("250.00"))
        self.assertEqual(order.total_tax, Decimal("50.00"))
        self.assertEqual(order.total_ttc, Decimal("300.00"))


class PurchaseOrderWorkflowTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="workflow-admin",
            role=User.Role.ADMINISTRATEUR,
        )
        self.buyer = User.objects.create_user(
            username="workflow-buyer",
            role=User.Role.ACHETEUR,
        )
        self.supplier = Supplier.objects.create(company_name="Workflow Supplier")
        self.client = APIClient()

    def create_order(self, user):
        self.client.force_authenticate(user=user)
        response = self.client.post(
            "/api/orders/",
            {
                "supplier": self.supplier.pk,
                "lines": [
                    {
                        "product_name": "Ordinateur",
                        "quantity": "10",
                        "unit_price": "2000000.00",
                        "tax_rate": "0.00",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["total_ttc"], "20000000.00")
        return response.data["id"]

    def test_buyer_submits_and_admin_approves_with_audit_metadata(self):
        order_id = self.create_order(self.buyer)
        order = PurchaseOrder.objects.get(pk=order_id)
        self.assertEqual(order.status, PurchaseOrder.Status.DRAFT)

        response = self.client.post(f"/api/orders/{order_id}/approve/", {}, format="json")
        self.assertEqual(response.status_code, 403)

        response = self.client.post(f"/api/orders/{order_id}/submit/", {}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        order.refresh_from_db()
        self.assertEqual(order.status, PurchaseOrder.Status.PENDING)

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(f"/api/orders/{order_id}/approve/", {}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        order.refresh_from_db()
        self.assertEqual(order.status, PurchaseOrder.Status.APPROVED)
        self.assertEqual(order.approved_by, self.admin)
        self.assertIsNotNone(order.approved_at)

    def test_rejection_requires_and_preserves_a_reason(self):
        order_id = self.create_order(self.buyer)
        self.client.post(f"/api/orders/{order_id}/submit/", {}, format="json")
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            f"/api/orders/{order_id}/reject/",
            {"reason": "  "},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

        response = self.client.post(
            f"/api/orders/{order_id}/reject/",
            {"reason": "Budget non disponible"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        order = PurchaseOrder.objects.get(pk=order_id)
        self.assertEqual(order.status, PurchaseOrder.Status.REJECTED)
        self.assertEqual(order.rejection_reason, "Budget non disponible")
        self.assertEqual(order.rejected_by, self.admin)
        self.assertIsNotNone(order.rejected_at)

    def test_order_status_cannot_be_changed_by_patch_and_pending_order_is_locked(self):
        order_id = self.create_order(self.buyer)
        response = self.client.patch(
            f"/api/orders/{order_id}/",
            {"status": PurchaseOrder.Status.APPROVED},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)
        order = PurchaseOrder.objects.get(pk=order_id)
        self.assertEqual(order.status, PurchaseOrder.Status.DRAFT)

        self.client.post(f"/api/orders/{order_id}/submit/", {}, format="json")
        response = self.client.patch(
            f"/api/orders/{order_id}/",
            {"notes": "Modification après soumission"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        order.refresh_from_db()
        self.assertEqual(order.notes, "")

    def test_creator_cannot_approve_own_order_even_if_administrator(self):
        order_id = self.create_order(self.admin)
        self.client.post(f"/api/orders/{order_id}/submit/", {}, format="json")
        response = self.client.post(f"/api/orders/{order_id}/approve/", {}, format="json")
        self.assertEqual(response.status_code, 403)


class DeliveryTrackingTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="delivery-admin",
            role=User.Role.ADMINISTRATEUR,
        )
        self.buyer = User.objects.create_user(
            username="delivery-buyer",
            role=User.Role.ACHETEUR,
        )
        self.supplier = Supplier.objects.create(company_name="Delivery Supplier")
        self.client = APIClient()

    def create_order(self):
        self.client.force_authenticate(user=self.buyer)
        response = self.client.post(
            "/api/orders/",
            {
                "supplier": self.supplier.pk,
                "lines": [
                    {
                        "product_name": "Ordinateur",
                        "quantity": "10",
                        "unit_price": "2000000.00",
                        "tax_rate": "0.00",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        return response.data["id"]

    def approve_order(self):
        order_id = self.create_order()
        self.client.post(f"/api/orders/{order_id}/submit/", {}, format="json")
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(f"/api/orders/{order_id}/approve/", {}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        order = PurchaseOrder.objects.get(pk=order_id)
        return order, order.lines.get()

    def test_delivery_updates_order_only_from_recorded_accepted_quantities(self):
        order, order_line = self.approve_order()
        self.client.force_authenticate(user=self.buyer)
        payload = {
            "order": order.pk,
            "delivery_date": date.today().isoformat(),
            "lines": [
                {
                    "order_line": order_line.pk,
                    "quantity_received": "6.000",
                    "quantity_damaged": "1.000",
                    "quantity_missing": "2.000",
                    "notes": "Un article endommagé.",
                }
            ],
        }
        response = self.client.post("/api/deliveries/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        order.refresh_from_db()
        self.assertEqual(order.status, PurchaseOrder.Status.PARTIALLY_DELIVERED)
        self.assertEqual(Delivery.objects.count(), 1)

        payload["lines"][0].update(
            quantity_received="5.000",
            quantity_damaged="0.000",
            quantity_missing="0.000",
            notes="",
        )
        response = self.client.post("/api/deliveries/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        order.refresh_from_db()
        self.assertEqual(order.status, PurchaseOrder.Status.DELIVERED)

    def test_delivery_rejects_unapproved_and_excess_quantities(self):
        order_id = self.create_order()
        line = PurchaseOrder.objects.get(pk=order_id).lines.get()
        payload = {
            "order": order_id,
            "delivery_date": date.today().isoformat(),
            "lines": [{"order_line": line.pk, "quantity_received": "1.000"}],
        }
        response = self.client.post("/api/deliveries/", payload, format="json")
        self.assertEqual(response.status_code, 400)

        order, line = self.approve_order()
        payload.update(
            order=order.pk,
            lines=[{"order_line": line.pk, "quantity_received": "10.001"}],
        )
        self.client.force_authenticate(user=self.buyer)
        response = self.client.post("/api/deliveries/", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Delivery.objects.count(), 0)
        order.refresh_from_db()
        self.assertEqual(order.status, PurchaseOrder.Status.APPROVED)
