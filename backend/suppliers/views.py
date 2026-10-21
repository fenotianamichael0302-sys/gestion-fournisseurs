import uuid

from django.db.models import Avg, Count
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import filters, mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from accounts.permissions import CanManageProcurement, CanManageSuppliers
from suppliers.models import Supplier, SupplierEvaluation, SupplierQuote
from suppliers.serializers import (
    QuoteRequestBatchSerializer,
    QuoteResponseSerializer,
    SupplierEvaluationSerializer,
    SupplierQuoteSerializer,
    SupplierSerializer,
)


class SupplierViewSet(viewsets.ModelViewSet):
    serializer_class = SupplierSerializer
    permission_classes = [CanManageSuppliers]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["company_name", "contact_name", "email", "tax_id", "city"]
    ordering_fields = ["company_name", "city", "country", "created_at"]
    ordering = ["company_name", "id"]

    def get_queryset(self):
        queryset = Supplier.objects.filter(is_deleted=False).annotate(
            evaluation_count=Count("evaluations"),
            quality_rating=Avg("evaluations__quality_rating"),
            delivery_rating=Avg("evaluations__delivery_rating"),
            price_rating=Avg("evaluations__price_rating"),
            reliability_rating=Avg("evaluations__reliability_rating"),
        )
        status = self.request.query_params.get("status")
        if status:
            if status not in Supplier.Status.values:
                raise ValidationError({"status": "Statut de fournisseur inconnu."})
            queryset = queryset.filter(status=status)
        return queryset

    def perform_destroy(self, instance):
        instance.soft_delete(user=self.request.user)


class SupplierEvaluationViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = SupplierEvaluationSerializer
    permission_classes = [CanManageProcurement]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["created_at", "quality_rating", "delivery_rating", "price_rating"]
    ordering = ["-created_at", "-id"]

    def get_queryset(self):
        queryset = SupplierEvaluation.objects.select_related(
            "supplier", "order", "evaluated_by"
        )
        supplier_id = self.request.query_params.get("supplier")
        if supplier_id:
            if not supplier_id.isdecimal():
                raise ValidationError({"supplier": "Un identifiant numérique est requis."})
            queryset = queryset.filter(supplier_id=int(supplier_id))
        return queryset

    def perform_create(self, serializer):
        serializer.save(evaluated_by=self.request.user)


class SupplierQuoteViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = SupplierQuoteSerializer
    permission_classes = [CanManageProcurement]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["product_name", "supplier__company_name", "notes"]
    ordering_fields = ["requested_at", "unit_price", "delivery_days", "status"]
    ordering = ["-requested_at", "-id"]

    def _get_locked_quote(self):
        quote = get_object_or_404(
            self.filter_queryset(self.get_queryset()).select_for_update(),
            pk=self.kwargs["pk"],
        )
        self.check_object_permissions(self.request, quote)
        return quote

    def get_queryset(self):
        queryset = SupplierQuote.objects.select_related("supplier", "requested_by")
        comparison_id = self.request.query_params.get("comparison")
        if comparison_id:
            try:
                comparison_id = uuid.UUID(comparison_id)
            except ValueError as exc:
                raise ValidationError(
                    {"comparison": "Identifiant de comparaison invalide."}
                ) from exc
            queryset = queryset.filter(comparison_id=comparison_id)
        supplier_id = self.request.query_params.get("supplier")
        if supplier_id:
            if not supplier_id.isdecimal():
                raise ValidationError({"supplier": "Un identifiant numérique est requis."})
            queryset = queryset.filter(supplier_id=int(supplier_id))
        quote_status = self.request.query_params.get("status")
        if quote_status:
            if quote_status not in SupplierQuote.Status.values:
                raise ValidationError({"status": "Statut de devis inconnu."})
            queryset = queryset.filter(status=quote_status)
        return queryset

    @action(detail=False, methods=["post"], url_path="request")
    @transaction.atomic
    def request_quotes(self, request):
        serializer = QuoteRequestBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comparison_id = uuid.uuid4()
        offers = [
            SupplierQuote.objects.create(
                comparison_id=comparison_id,
                supplier=supplier,
                product_name=serializer.validated_data["product_name"],
                quantity=serializer.validated_data["quantity"],
                requested_by=request.user,
            )
            for supplier in serializer.validated_data["supplier_ids"]
        ]
        return Response(
            SupplierQuoteSerializer(offers, many=True, context=self.get_serializer_context()).data,
            status=201,
        )

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def receive(self, request, *args, **kwargs):
        quote = self._get_locked_quote()
        if quote.status != SupplierQuote.Status.REQUESTED:
            raise ValidationError({"status": "Seul un devis demandé peut être renseigné."})
        response_serializer = QuoteResponseSerializer(data=request.data)
        response_serializer.is_valid(raise_exception=True)
        for field, value in response_serializer.validated_data.items():
            setattr(quote, field, value)
        quote.status = SupplierQuote.Status.RECEIVED
        quote.received_at = timezone.now()
        quote.save()
        return Response(self.get_serializer(quote).data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def decline(self, request, *args, **kwargs):
        quote = self._get_locked_quote()
        if quote.status != SupplierQuote.Status.REQUESTED:
            raise ValidationError({"status": "Seul un devis demandé peut être refusé."})
        notes = request.data.get("notes")
        if not isinstance(notes, str) or not notes.strip():
            raise ValidationError({"notes": "Le motif du refus est obligatoire."})
        quote.status = SupplierQuote.Status.DECLINED
        quote.notes = notes.strip()
        quote.received_at = timezone.now()
        quote.save(update_fields=["status", "notes", "received_at"])
        return Response(self.get_serializer(quote).data)
