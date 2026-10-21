"""Routes principales du projet."""
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)
from rest_framework.routers import DefaultRouter

from accounts.views import UserAdminViewSet
from accounts.views import (
    BuyerRegistrationView,
    CurrentUserView,
    RateLimitedTokenBlacklistView,
    RateLimitedTokenObtainPairView,
    RateLimitedTokenRefreshView,
)
from audit.views import AuditLogViewSet
from audit.backup_views import DatabaseBackupView
from invoices.views import InvoiceViewSet
from orders.views import DeliveryViewSet, PurchaseOrderViewSet
from payments.views import PaymentViewSet
from reports.views import (
    DashboardView,
    MonthlyPurchasesReportView,
    PriceComparisonReportView,
    SupplierSpendingReportView,
    UnpaidInvoicesReportView,
)
from suppliers.views import SupplierEvaluationViewSet, SupplierQuoteViewSet, SupplierViewSet


router = DefaultRouter()
router.register("users", UserAdminViewSet, basename="user")
router.register("suppliers", SupplierViewSet, basename="supplier")
router.register("supplier-evaluations", SupplierEvaluationViewSet, basename="supplier-evaluation")
router.register("quotes", SupplierQuoteViewSet, basename="quote")
router.register("orders", PurchaseOrderViewSet, basename="order")
router.register("deliveries", DeliveryViewSet, basename="delivery")
router.register("invoices", InvoiceViewSet, basename="invoice")
router.register("payments", PaymentViewSet, basename="payment")
router.register("audit", AuditLogViewSet, basename="audit")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/register/", BuyerRegistrationView.as_view(), name="buyer-register"),
    path("api/auth/me/", CurrentUserView.as_view(), name="current-user"),
    path("api/admin/backup/", DatabaseBackupView.as_view(), name="database-backup"),
    path("api/", include(router.urls)),
    path("api/reports/dashboard/", DashboardView.as_view(), name="report-dashboard"),
    path(
        "api/reports/spending-by-supplier/",
        SupplierSpendingReportView.as_view(),
        name="report-spending-by-supplier",
    ),
    path(
        "api/reports/monthly-purchases/",
        MonthlyPurchasesReportView.as_view(),
        name="report-monthly-purchases",
    ),
    path(
        "api/reports/unpaid-invoices/",
        UnpaidInvoicesReportView.as_view(),
        name="report-unpaid-invoices",
    ),
    path(
        "api/reports/price-comparison/",
        PriceComparisonReportView.as_view(),
        name="report-price-comparison",
    ),
    path(
        "api/auth/token/",
        RateLimitedTokenObtainPairView.as_view(),
        name="token-obtain-pair",
    ),
    path(
        "api/auth/token/refresh/",
        RateLimitedTokenRefreshView.as_view(),
        name="token-refresh",
    ),
    path(
        "api/auth/token/blacklist/",
        RateLimitedTokenBlacklistView.as_view(),
        name="token-blacklist",
    ),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]
