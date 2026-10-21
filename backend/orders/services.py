from django.db import transaction
from django.utils import timezone

from orders.models import OrderNumberSequence, PurchaseOrder, PurchaseOrderLine


@transaction.atomic
def create_purchase_order(*, validated_data, created_by):
    lines = validated_data.pop("lines")
    order_date = validated_data.get("order_date") or timezone.localdate()
    year = order_date.year
    sequence, _ = OrderNumberSequence.objects.select_for_update().get_or_create(
        year=year
    )
    number = sequence.next_number
    sequence.next_number += 1
    sequence.save(update_fields=["next_number"])

    order = PurchaseOrder.objects.create(
        order_number=f"BC-{year}-{number:04d}",
        created_by=created_by,
        **validated_data,
    )
    for line_data in lines:
        PurchaseOrderLine.objects.create(order=order, **line_data)
    return order
