from datetime import date

from django.utils.dateparse import parse_date
from rest_framework import serializers, viewsets

from accounts.permissions import IsAdministrator
from audit.models import AuditLog
from audit.serializers import AuditLogSerializer


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related("actor", "content_type")
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdministrator]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        actor_id = params.get("user")
        if actor_id:
            if not actor_id.isdecimal():
                raise serializers.ValidationError({"user": "Un identifiant numérique est requis."})
            queryset = queryset.filter(actor_id=int(actor_id))
        action = params.get("action")
        if action:
            valid_actions = AuditLog.Action.values
            if action not in valid_actions:
                raise serializers.ValidationError({"action": "Action d'audit inconnue."})
            queryset = queryset.filter(action=action)
        for parameter, lookup in (("date_from", "created_at__date__gte"), ("date_to", "created_at__date__lte")):
            value = params.get(parameter)
            if value:
                parsed = parse_date(value)
                if not isinstance(parsed, date):
                    raise serializers.ValidationError(
                        {parameter: "La date doit respecter le format AAAA-MM-JJ."}
                    )
                queryset = queryset.filter(**{lookup: parsed})
        return queryset
