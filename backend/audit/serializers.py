from rest_framework import serializers

from audit.models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", read_only=True)
    action_label = serializers.CharField(source="get_action_display", read_only=True)
    content_type_name = serializers.CharField(source="content_type.model", read_only=True)

    class Meta:
        model = AuditLog
        fields = (
            "id",
            "actor",
            "actor_username",
            "action",
            "action_label",
            "content_type_name",
            "object_id",
            "object_repr",
            "old_values",
            "new_values",
            "ip_address",
            "created_at",
        )
