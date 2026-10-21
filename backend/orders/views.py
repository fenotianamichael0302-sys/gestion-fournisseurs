from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import filters, viewsets
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status as http_status
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, OpenApiRequest

from accounts.models import User
from accounts.permissions import CanManageProcurement, IsAdministrator
from orders.models import PurchaseOrder
from orders.serializers import PurchaseOrderSerializer
from orders.serializers import DeliverySerializer
from orders.models import Delivery
from orders.pdf import purchase_order_pdf


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    serializer_class = PurchaseOrderSerializer
    permission_classes = [CanManageProcurement]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["order_number", "supplier__company_name"]
    ordering_fields = ["order_date", "status", "order_number"]
    ordering = ["-order_date", "-id"]

    def get_queryset(self):
        queryset = PurchaseOrder.objects.select_related(
            "supplier", "created_by"
        ).prefetch_related("lines")
        user = getattr(self.request, "user", None)
        if user and user.is_authenticated and user.role != User.Role.ADMINISTRATEUR:
            queryset = queryset.filter(created_by=user)
        supplier_id = self.request.query_params.get("supplier")
        if supplier_id:
            if not supplier_id.isdecimal():
                raise ValidationError({"supplier": "Un identifiant numérique est requis."})
            queryset = queryset.filter(supplier_id=int(supplier_id))
        status = self.request.query_params.get("status")
        if status:
            statuses = status.split(",")
            if any(value not in PurchaseOrder.Status.values for value in statuses):
                raise ValidationError({"status": "Statut de commande inconnu."})
            queryset = queryset.filter(status__in=statuses)
        return queryset

    def perform_update(self, serializer):
        order = serializer.instance
        if (
            self.request.user.role != User.Role.ADMINISTRATEUR
            and order.created_by_id != self.request.user.id
        ):
            raise PermissionDenied("Vous ne pouvez modifier que vos propres brouillons.")
        serializer.save()

    def _lock_order(self):
        return get_object_or_404(
            PurchaseOrder.objects.select_for_update(),
            pk=self.kwargs["pk"],
        )

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, CanManageProcurement])
    def submit(self, request, *args, **kwargs):
        with transaction.atomic():
            order = self._lock_order()
            if order.created_by_id != request.user.id:
                raise PermissionDenied("Seul le créateur peut soumettre cette commande.")
            if order.status != PurchaseOrder.Status.DRAFT:
                raise ValidationError({"status": "Seul un brouillon peut être soumis."})
            if not order.lines.exists():
                raise ValidationError({"lines": "Une commande doit contenir au moins une ligne."})
            order.status = PurchaseOrder.Status.PENDING
            order.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAdministrator])
    def approve(self, request, *args, **kwargs):
        with transaction.atomic():
            order = self._lock_order()
            if order.created_by_id == request.user.id:
                raise PermissionDenied("Vous ne pouvez pas valider votre propre commande.")
            if order.status != PurchaseOrder.Status.PENDING:
                raise ValidationError(
                    {"status": "Seule une commande en attente peut être validée."}
                )
            order.status = PurchaseOrder.Status.APPROVED
            order.approved_by = request.user
            order.approved_at = timezone.now()
            order.rejection_reason = ""
            order.rejected_by = None
            order.rejected_at = None
            order.save(
                update_fields=[
                    "status",
                    "approved_by",
                    "approved_at",
                    "rejection_reason",
                    "rejected_by",
                    "rejected_at",
                    "updated_at",
                ]
            )
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAdministrator])
    @extend_schema(request=OpenApiRequest({"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]}))
    def reject(self, request, *args, **kwargs):
        reason = request.data.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ValidationError({"reason": "Le motif du refus est obligatoire."})
        with transaction.atomic():
            order = self._lock_order()
            if order.created_by_id == request.user.id:
                raise PermissionDenied("Vous ne pouvez pas refuser votre propre commande.")
            if order.status != PurchaseOrder.Status.PENDING:
                raise ValidationError(
                    {"status": "Seule une commande en attente peut être refusée."}
                )
            order.status = PurchaseOrder.Status.REJECTED
            order.rejected_by = request.user
            order.rejected_at = timezone.now()
            order.rejection_reason = reason.strip()
            order.save(
                update_fields=[
                    "status",
                    "rejected_by",
                    "rejected_at",
                    "rejection_reason",
                    "updated_at",
                ]
            )
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, *args, **kwargs):
        with transaction.atomic():
            order = self._lock_order()
            if (
                request.user.role != User.Role.ADMINISTRATEUR
                and order.created_by_id != request.user.id
            ):
                raise PermissionDenied("Vous ne pouvez annuler que vos propres commandes.")
            if order.status not in (
                PurchaseOrder.Status.DRAFT,
                PurchaseOrder.Status.PENDING,
            ):
                raise ValidationError(
                    {"status": "Seul un brouillon ou une commande en attente peut être annulé."}
                )
            order.status = PurchaseOrder.Status.CANCELLED
            order.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(order).data, status=http_status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="pdf")
    @extend_schema(responses={(200, "application/pdf"): OpenApiTypes.BINARY})
    def pdf(self, request, *args, **kwargs):
        return purchase_order_pdf(self.get_object())


class DeliveryViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = DeliverySerializer
    permission_classes = [CanManageProcurement]

    def get_queryset(self):
        queryset = Delivery.objects.select_related(
            "order", "order__supplier", "created_by"
        ).prefetch_related("lines", "lines__order_line")
        user = getattr(self.request, "user", None)
        if user and user.is_authenticated and user.role != User.Role.ADMINISTRATEUR:
            queryset = queryset.filter(created_by=user)
        order_id = self.request.query_params.get("order")
        if order_id:
            if not order_id.isdecimal():
                raise ValidationError({"order": "Un identifiant numérique est requis."})
            queryset = queryset.filter(order_id=int(order_id))
        return queryset
