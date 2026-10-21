from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from invoices.models import Invoice, InvoiceLine
from orders.models import PurchaseOrder
from payments.models import Payment
from suppliers.models import Supplier


class InvoiceBalanceTests(TestCase):
    def test_totals_balance_and_status_reflect_partial_payment(self):
        supplier = Supplier.objects.create(company_name="Fournisseur Facture Test")
        order = PurchaseOrder.objects.create(
            order_number="BC-2026-INVOICE-TEST",
            supplier=supplier,
            order_date=date.today(),
        )
        invoice = Invoice.objects.create(
            supplier=supplier,
            order=order,
            invoice_number="FACT-TEST-001",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=14),
        )
        InvoiceLine.objects.create(
            invoice=invoice,
            product_name="Prestation test",
            quantity=2,
            unit_price=Decimal("100.00"),
            tax_rate=Decimal("20.00"),
        )

        self.assertEqual(invoice.total_ht, Decimal("200.00"))
        self.assertEqual(invoice.total_tax, Decimal("40.00"))
        self.assertEqual(invoice.total_ttc, Decimal("240.00"))
        self.assertEqual(invoice.balance_due, Decimal("240.00"))

        Payment.objects.create(
            invoice=invoice,
            payment_date=date.today(),
            amount=Decimal("65.00"),
            method=Payment.Method.BANK_TRANSFER,
        )

        self.assertEqual(invoice.amount_paid, Decimal("65.00"))
        self.assertEqual(invoice.balance_due, Decimal("175.00"))
        self.assertEqual(invoice.status, Invoice.PaymentStatus.PARTIALLY_PAID)
