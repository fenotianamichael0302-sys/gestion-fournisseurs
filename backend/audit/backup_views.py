"""Actions d'administration liées aux sauvegardes."""
import logging
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import APIException
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdministrator
from audit.models import AuditLog


logger = logging.getLogger(__name__)


class DatabaseBackupResultSerializer(serializers.Serializer):
    file_name = serializers.CharField()
    size_bytes = serializers.IntegerField()
    created_at = serializers.DateTimeField()


class BackupUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "La sauvegarde de la base de données a échoué."
    default_code = "backup_failed"


class DatabaseBackupView(APIView):
    permission_classes = [IsAuthenticated, IsAdministrator]

    @extend_schema(
        request=None,
        responses={
            status.HTTP_201_CREATED: DatabaseBackupResultSerializer,
            status.HTTP_503_SERVICE_UNAVAILABLE: OpenApiResponse(
                description="La commande de sauvegarde a échoué."
            ),
        },
    )
    def post(self, request):
        try:
            backup_path = Path(call_command("backup_db"))
        except CommandError as exc:
            logger.exception("La commande de sauvegarde MySQL a échoué.")
            raise BackupUnavailable(str(exc)) from exc

        audit_entry = AuditLog.objects.create(
            actor=request.user,
            action=AuditLog.Action.CREATE,
            object_repr=f"Sauvegarde MySQL {backup_path.name}",
            new_values={
                "file_name": backup_path.name,
                "size_bytes": backup_path.stat().st_size,
            },
        )
        return Response(
            {
                "file_name": backup_path.name,
                "size_bytes": audit_entry.new_values["size_bytes"],
                "created_at": audit_entry.created_at,
            },
            status=status.HTTP_201_CREATED,
        )
