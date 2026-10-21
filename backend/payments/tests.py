from datetime import date, timedelta

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from invoices.models import Invoice, InvoiceLine
from payments.models import Payment
from payments.serializers import PaymentSerializer
from suppliers.models import Supplier


class PaymentValidationTests(TestCase):
    def test_payment_cannot_exceed_invoice_balance(self):
        supplier = Supplier.objects.create(company_name="Fournisseur Paiement Test")
        invoice = Invoice.objects.create(
            supplier=supplier,
            invoice_number="FACT-PAYMENT-TEST",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=14),
        )
        InvoiceLine.objects.create(
            invoice=invoice,
            product_name="Produit facture",
            quantity=1,
            unit_price="100.00",
            tax_rate="20.00",
        )
        serializer = PaymentSerializer(
            data={
                "invoice": invoice.id,
                "payment_date": date.today().isoformat(),
                "amount": "120.01",
                "method": "VIREMENT",
                "reference": "REF-OVER-BALANCE",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("amount", serializer.errors)


class PaymentDuplicateReferenceTests(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(
            username="payment-buyer",
            role=User.Role.ACHETEUR,
        )
        supplier = Supplier.objects.create(company_name="Duplicate Payment Supplier")
        self.invoice = Invoice.objects.create(
            supplier=supplier,
            invoice_number="FACT-DUPLICATE-REF",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=14),
        )
        InvoiceLine.objects.create(
            invoice=self.invoice,
            product_name="Service",
            quantity=1,
            unit_price="200.00",
            tax_rate="0.00",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.buyer)

    def test_duplicate_nonempty_payment_reference_is_rejected(self):
        payload = {
            "invoice": self.invoice.pk,
            "payment_date": date.today().isoformat(),
            "amount": "50.00",
            "method": "VIREMENT",
            "reference": "BANK-TRANSFER-001",
        }
        without_reference = {key: value for key, value in payload.items() if key != "reference"}
        response = self.client.post("/api/payments/", without_reference, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("reference", response.data)

        response = self.client.post("/api/payments/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        response = self.client.post("/api/payments/", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("reference", response.data)
        self.assertEqual(Payment.objects.filter(invoice=self.invoice).count(), 1)
