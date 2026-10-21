from io import StringIO
from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from accounts.models import User
from accounts.permissions import CanManageProcurement, CanManageSuppliers, IsAdministrator
from invoices.models import Invoice
from orders.models import PurchaseOrder
from payments.models import Payment
from suppliers.models import Supplier


class RolePermissionTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin",
            password="test-password",
            role=User.Role.ADMINISTRATEUR,
        )
        self.buyer = User.objects.create_user(
            username="buyer",
            password="test-password",
            role=User.Role.ACHETEUR,
        )
        factory = APIRequestFactory()
        self.get_request = factory.get("/api/orders/")
        self.delete_request = factory.delete("/api/orders/1/")

    def test_procurement_permissions_allow_buyers_but_restrict_hard_delete(self):
        get_request = self.get_request
        get_request.user = self.buyer
        delete_request = self.delete_request
        delete_request.user = self.buyer
        admin_delete_request = APIRequestFactory().delete("/api/orders/1/")
        admin_delete_request.user = self.admin

        permission = CanManageProcurement()
        self.assertTrue(permission.has_permission(get_request, SimpleNamespace()))
        self.assertFalse(permission.has_permission(delete_request, SimpleNamespace()))
        self.assertTrue(
            permission.has_permission(admin_delete_request, SimpleNamespace())
        )

    def test_supplier_management_is_read_only_for_buyers(self):
        request = APIRequestFactory().delete("/api/suppliers/1/")
        request.user = self.buyer

        permission = CanManageSuppliers()
        self.assertFalse(
            permission.has_permission(request, SimpleNamespace())
        )
        request = APIRequestFactory().get("/api/suppliers/")
        request.user = self.buyer
        self.assertTrue(permission.has_permission(request, SimpleNamespace()))

    def test_audit_permission_is_administrator_only(self):
        request = APIRequestFactory().get("/api/audit/")
        request.user = self.admin
        permission = IsAdministrator()
        self.assertTrue(permission.has_permission(request, SimpleNamespace()))

        request.user = self.buyer
        self.assertFalse(permission.has_permission(request, SimpleNamespace()))
        request.user = AnonymousUser()
        self.assertFalse(permission.has_permission(request, SimpleNamespace()))


class DemoSeedCommandTests(TestCase):
    def test_seed_demo_is_repeatable_and_creates_separate_roles(self):
        options = {
            "admin_username": "demo_admin",
            "buyer_username": "demo_buyer",
            "admin_password": "Valid-Admin-Pass-948!",
            "buyer_password": "Valid-Buyer-Pass-529!",
            "stdout": StringIO(),
        }
        call_command("seed_demo", **options)
        call_command("seed_demo", **options)

        admin = User.objects.get(username="demo_admin")
        buyer = User.objects.get(username="demo_buyer")
        self.assertEqual(admin.role, User.Role.ADMINISTRATEUR)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.check_password(options["admin_password"]))
        self.assertEqual(buyer.role, User.Role.ACHETEUR)
        self.assertFalse(buyer.is_superuser)
        self.assertEqual(Supplier.objects.count(), 2)
        self.assertEqual(PurchaseOrder.objects.count(), 2)
        self.assertEqual(Invoice.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 1)
