from datetime import date

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from orders.models import PurchaseOrder
from suppliers.models import Supplier, SupplierQuote


class SupplierEvaluationTests(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(
            username="evaluation-buyer",
            role=User.Role.ACHETEUR,
        )
        self.supplier = Supplier.objects.create(company_name="Evaluated Supplier")
        self.order = PurchaseOrder.objects.create(
            order_number="BC-EVALUATION-001",
            supplier=self.supplier,
            order_date=date.today(),
            status=PurchaseOrder.Status.DELIVERED,
            created_by=self.buyer,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.buyer)

    def test_evaluation_requires_delivered_order_and_appears_in_supplier_indicators(self):
        response = self.client.post(
            "/api/supplier-evaluations/",
            {
                "supplier": self.supplier.pk,
                "order": self.order.pk,
                "quality_rating": 5,
                "delivery_rating": 4,
                "price_rating": 3,
                "reliability_rating": 5,
                "comment": "Livraison conforme.",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)

        response = self.client.get(f"/api/suppliers/{self.supplier.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["evaluation_count"], 1)
        self.assertEqual(response.data["quality_rating"], 5)
        self.assertEqual(response.data["delivery_rating"], 4)
        self.assertEqual(response.data["price_rating"], 3)
        self.assertEqual(response.data["reliability_rating"], 5)

    def test_order_must_be_delivered_and_only_one_rating_per_user_and_order(self):
        self.order.status = PurchaseOrder.Status.PENDING
        self.order.save(update_fields=["status"])
        payload = {
            "supplier": self.supplier.pk,
            "order": self.order.pk,
            "quality_rating": 5,
            "delivery_rating": 5,
            "price_rating": 5,
            "reliability_rating": 5,
        }
        response = self.client.post(
            "/api/supplier-evaluations/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, 400)

        self.order.status = PurchaseOrder.Status.DELIVERED
        self.order.save(update_fields=["status"])
        response = self.client.post("/api/supplier-evaluations/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        response = self.client.post("/api/supplier-evaluations/", payload, format="json")
        self.assertEqual(response.status_code, 400)


class SupplierQuoteTests(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(
            username="quote-buyer",
            role=User.Role.ACHETEUR,
        )
        self.supplier = Supplier.objects.create(company_name="Quote Supplier")
        self.second_supplier = Supplier.objects.create(company_name="Quote Supplier 2")
        self.inactive_supplier = Supplier.objects.create(
            company_name="Inactive Quote Supplier",
            status=Supplier.Status.INACTIVE,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.buyer)

    def test_requesting_and_comparing_quotes_records_real_responses_only(self):
        response = self.client.post(
            "/api/quotes/request/",
            {
                "product_name": "Ordinateur portable",
                "quantity": "10",
                "supplier_ids": [self.supplier.pk, self.second_supplier.pk],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(
            {offer["status"] for offer in response.data},
            {SupplierQuote.Status.REQUESTED},
        )
        comparison_id = response.data[0]["comparison_id"]
        self.assertEqual(response.data[1]["comparison_id"], comparison_id)

        quote_id = response.data[0]["id"]
        response = self.client.post(
            f"/api/quotes/{quote_id}/receive/",
            {
                "unit_price": "2000000.00",
                "tax_rate": "20.00",
                "delivery_days": 14,
                "quality_rating": 4,
                "payment_terms": "Paiement à 30 jours.",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], SupplierQuote.Status.RECEIVED)
        self.assertEqual(response.data["unit_price"], "2000000.00")
        self.assertIsNotNone(response.data["received_at"])

        response = self.client.get(f"/api/quotes/?comparison={comparison_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)

    def test_quote_request_requires_active_unique_suppliers_and_decline_reason(self):
        payload = {
            "product_name": "Ordinateur portable",
            "quantity": "1",
            "supplier_ids": [self.supplier.pk, self.supplier.pk],
        }
        response = self.client.post("/api/quotes/request/", payload, format="json")
        self.assertEqual(response.status_code, 400)

        payload["supplier_ids"] = [self.inactive_supplier.pk]
        response = self.client.post("/api/quotes/request/", payload, format="json")
        self.assertEqual(response.status_code, 400)

        payload["supplier_ids"] = [self.supplier.pk]
        response = self.client.post("/api/quotes/request/", payload, format="json")
        quote_id = response.data[0]["id"]
        response = self.client.post(
            f"/api/quotes/{quote_id}/decline/",
            {"notes": ""},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            f"/api/quotes/{quote_id}/decline/",
            {"notes": "Indisponible"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], SupplierQuote.Status.DECLINED)


class SupplierAccessTests(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(
            username="supplier-readonly-buyer",
            role=User.Role.ACHETEUR,
        )
        self.admin = User.objects.create_user(
            username="supplier-admin",
            role=User.Role.ADMINISTRATEUR,
        )
        self.supplier = Supplier.objects.create(
            company_name="Sensitive Supplier",
            bank_name="Example Bank",
            bank_account="ACCOUNT-123",
            swift="EXAMPLEXX",
        )
        self.client = APIClient()

    def test_buyers_can_consult_but_not_manage_suppliers_or_view_bank_details(self):
        self.client.force_authenticate(user=self.buyer)
        response = self.client.get(f"/api/suppliers/{self.supplier.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("bank_name", response.data)
        self.assertNotIn("bank_account", response.data)
        self.assertNotIn("swift", response.data)

        response = self.client.patch(
            f"/api/suppliers/{self.supplier.pk}/",
            {"company_name": "Unauthorized change"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.supplier.refresh_from_db()
        self.assertEqual(self.supplier.company_name, "Sensitive Supplier")

        self.client.force_authenticate(user=self.admin)
        response = self.client.get(f"/api/suppliers/{self.supplier.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["bank_account"], "ACCOUNT-123")
