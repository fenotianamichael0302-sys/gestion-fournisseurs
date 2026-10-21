"""Crée un jeu de démonstration sans identifiants par défaut."""
from getpass import getpass
from datetime import timedelta

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from invoices.models import Invoice, InvoiceLine
from orders.models import PurchaseOrder, PurchaseOrderLine
from payments.models import Payment
from suppliers.models import Supplier


class Command(BaseCommand):
    help = "Crée des comptes et des données métier de démonstration."

    def add_arguments(self, parser):
        parser.add_argument("--admin-username", default="demo_admin")
        parser.add_argument("--buyer-username", default="demo_buyer")
        parser.add_argument(
            "--admin-password",
            help="Mot de passe admin (visible dans la liste des processus).",
        )
        parser.add_argument(
            "--buyer-password",
            help="Mot de passe acheteur (visible dans la liste des processus).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        admin = self._get_or_create_user(
            username=options["admin_username"],
            role=User.Role.ADMINISTRATEUR,
            password=options["admin_password"],
            is_admin=True,
        )
        buyer = self._get_or_create_user(
            username=options["buyer_username"],
            role=User.Role.ACHETEUR,
            password=options["buyer_password"],
            is_admin=False,
        )

        supplier, _ = Supplier.objects.get_or_create(
            company_name="Fournisseur Demo - Materiel",
            defaults={
                "contact_name": "Contact Demo",
                "email": "materiel@example.test",
                "phone": "+261 20 00 000 01",
                "street": "10 rue de la Demo",
                "city": "Antananarivo",
                "postal_code": "101",
                "country": "Madagascar",
                "tax_id": "DEMO-NIF-001",
            },
        )
        second_supplier, _ = Supplier.objects.get_or_create(
            company_name="Fournisseur Demo - Services",
            defaults={
                "contact_name": "Contact Services",
                "email": "services@example.test",
                "city": "Antananarivo",
                "country": "Madagascar",
                "tax_id": "DEMO-NIF-002",
            },
        )

        today = timezone.localdate()
        order = self._get_or_create_order(
            order_number=f"BC-DEMO-{today.year}-0001",
            supplier=supplier,
            created_by=buyer,
            order_date=today - timedelta(days=4),
            expected_delivery_date=today + timedelta(days=10),
            product_name="Ordinateur portable de demonstration",
        )
        self._get_or_create_order(
            order_number=f"BC-DEMO-{today.year}-0002",
            supplier=second_supplier,
            created_by=buyer,
            order_date=today - timedelta(days=2),
            expected_delivery_date=today + timedelta(days=14),
            product_name="Prestation de maintenance",
        )

        invoice, _ = Invoice.objects.get_or_create(
            supplier=supplier,
            invoice_number="FACT-DEMO-001",
            defaults={
                "order": order,
                "invoice_date": today - timedelta(days=2),
                "due_date": today + timedelta(days=28),
                "created_by": buyer,
                "notes": "Facture de demonstration",
            },
        )
        if invoice.supplier_id != supplier.id or invoice.order_id != order.id:
            raise CommandError(
                "La facture FACT-DEMO-001 existe déjà avec des données différentes."
            )
        if not invoice.lines.exists():
            InvoiceLine.objects.create(
                invoice=invoice,
                product_name="Ordinateur portable de demonstration",
                quantity=3,
                unit_price="100.00",
                tax_rate="20.00",
            )

        payment_reference = "REGLEMENT-DEMO-001"
        if (
            invoice.balance_due > 0
            and not Payment.objects.filter(
                invoice=invoice,
                reference=payment_reference,
            ).exists()
        ):
            Payment.objects.create(
                invoice=invoice,
                payment_date=today,
                amount="75.00",
                method=Payment.Method.BANK_TRANSFER,
                reference=payment_reference,
                recorded_by=buyer,
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Jeu de démonstration prêt : "
                f"{admin.username}, {buyer.username}, 2 fournisseurs, "
                "2 commandes, 1 facture et 1 paiement partiel."
            )
        )

    def _get_or_create_user(self, *, username, role, password, is_admin):
        user = User.objects.filter(username=username).first()
        if user:
            if user.role != role or not user.is_active:
                raise CommandError(
                    f"L'utilisateur {username!r} existe déjà avec un rôle "
                    "différent ou est désactivé ; aucune modification effectuée."
                )
            return user

        if password is None:
            password = getpass(f"Mot de passe pour {username} : ")
            confirmation = getpass("Confirmez le mot de passe : ")
            if password != confirmation:
                raise CommandError("Les mots de passe ne correspondent pas.")
        if not password:
            raise CommandError(f"Un mot de passe est requis pour {username}.")

        user = User(
            username=username,
            email=f"{username}@example.test",
            first_name="Compte",
            last_name="Demo",
            role=role,
            is_staff=is_admin,
            is_superuser=is_admin,
        )
        try:
            validate_password(password, user)
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from exc
        user.set_password(password)
        user.save()
        return user

    def _get_or_create_order(
        self,
        *,
        order_number,
        supplier,
        created_by,
        order_date,
        expected_delivery_date,
        product_name,
    ):
        order, _ = PurchaseOrder.objects.get_or_create(
            order_number=order_number,
            defaults={
                "supplier": supplier,
                "created_by": created_by,
                "order_date": order_date,
                "expected_delivery_date": expected_delivery_date,
                "status": PurchaseOrder.Status.PENDING,
                "terms": "Conditions de demonstration",
                "notes": "Commande creee par seed_demo.",
            },
        )
        if order.supplier_id != supplier.id:
            raise CommandError(
                f"La commande {order_number} existe déjà pour un autre fournisseur."
            )
        if not order.lines.exists():
            PurchaseOrderLine.objects.create(
                order=order,
                product_name=product_name,
                quantity=3,
                unit_price="100.00",
                tax_rate="20.00",
            )
        return order
