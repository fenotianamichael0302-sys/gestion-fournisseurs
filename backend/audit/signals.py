import json

from django.core.serializers.json import DjangoJSONEncoder
from django.db.models.fields.files import FieldFile
from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.contrib.contenttypes.models import ContentType

from accounts.models import User
from audit.middleware import current_request
from audit.models import AuditLog
from invoices.models import Invoice, InvoiceLine
from orders.models import Delivery, DeliveryLine, PurchaseOrder, PurchaseOrderLine
from payments.models import Payment
from suppliers.models import Supplier, SupplierEvaluation, SupplierQuote


AUDITED_MODELS = (
    User,
    Supplier,
    SupplierEvaluation,
    SupplierQuote,
    PurchaseOrder,
    PurchaseOrderLine,
    Delivery,
    DeliveryLine,
    Invoice,
    InvoiceLine,
    Payment,
)
SENSITIVE_FIELDS = {"password", "bank_account", "swift"}


def _snapshot(instance):
    values = {}
    for field in instance._meta.concrete_fields:
        if field.name in SENSITIVE_FIELDS or field.attname in SENSITIVE_FIELDS:
            continue
        value = getattr(instance, field.attname)
        values[field.attname] = value.name if isinstance(value, FieldFile) else value
    return json.loads(json.dumps(values, cls=DjangoJSONEncoder))


def _request_metadata():
    request = current_request.get()
    if request is None:
        return None, None
    actor = request.user if request.user.is_authenticated else None
    return actor, request.META.get("REMOTE_ADDR")


def _record(instance, action, old_values=None, new_values=None, using="default"):
    actor, ip_address = _request_metadata()
    if action == AuditLog.Action.UPDATE and old_values is not None and new_values is not None:
        changed = {
            key
            for key in old_values.keys() | new_values.keys()
            if old_values.get(key) != new_values.get(key)
        }
        if not changed:
            return
        old_values = {key: old_values.get(key) for key in changed}
        new_values = {key: new_values.get(key) for key in changed}
        if "status" in changed:
            action = AuditLog.Action.STATUS_CHANGE

    AuditLog.objects.using(using).create(
        actor=actor,
        action=action,
        content_type=ContentType.objects.db_manager(using).get_for_model(instance),
        object_id=str(instance.pk),
        object_repr=str(instance)[:255],
        old_values=old_values,
        new_values=new_values,
        ip_address=ip_address,
    )


def _invoice_payment_state(invoice):
    values = {
        "status": invoice.status,
        "amount_paid": invoice.amount_paid,
        "balance_due": invoice.balance_due,
    }
    return json.loads(json.dumps(values, cls=DjangoJSONEncoder))


def _record_invoice_payment_changes(before_states, using):
    for invoice_id, old_values in before_states.items():
        invoice = Invoice.objects.using(using).get(pk=invoice_id)
        _record(
            invoice,
            AuditLog.Action.UPDATE,
            old_values=old_values,
            new_values=_invoice_payment_state(invoice),
            using=using,
        )


def _connect_model(model):
    def capture_old_values(instance, using, raw, **_kwargs):
        del _kwargs
        if raw:
            return
        if instance.pk is None:
            instance._audit_old_values = None
            return
        try:
            previous = model.objects.using(using).get(pk=instance.pk)
        except model.DoesNotExist:
            instance._audit_old_values = None
        else:
            instance._audit_old_values = _snapshot(previous)

    def record_save(instance, created, using, raw, **_kwargs):
        del _kwargs
        if raw:
            return
        old_values = getattr(instance, "_audit_old_values", None)
        if created or old_values is None:
            _record(
                instance,
                AuditLog.Action.CREATE,
                new_values=_snapshot(instance),
                using=using,
            )
        else:
            _record(
                instance,
                AuditLog.Action.UPDATE,
                old_values=old_values,
                new_values=_snapshot(instance),
                using=using,
            )

    def record_delete(instance, using, **_kwargs):
        del _kwargs
        _record(
            instance,
            AuditLog.Action.DELETE,
            old_values=_snapshot(instance),
            using=using,
        )

    pre_save.connect(
        capture_old_values,
        sender=model,
        weak=False,
        dispatch_uid=f"audit-pre-save-{model._meta.label_lower}",
    )
    post_save.connect(
        record_save,
        sender=model,
        weak=False,
        dispatch_uid=f"audit-post-save-{model._meta.label_lower}",
    )
    post_delete.connect(
        record_delete,
        sender=model,
        weak=False,
        dispatch_uid=f"audit-post-delete-{model._meta.label_lower}",
    )


def _capture_payment_state(instance, using, raw, **_kwargs):
    del _kwargs
    if raw:
        return
    before_states = {}
    if instance.pk:
        previous = Payment.objects.using(using).get(pk=instance.pk)
        previous_invoice = Invoice.objects.using(using).get(pk=previous.invoice_id)
        before_states[previous_invoice.pk] = _invoice_payment_state(previous_invoice)
    if instance.invoice_id not in before_states:
        invoice = Invoice.objects.using(using).get(pk=instance.invoice_id)
        before_states[invoice.pk] = _invoice_payment_state(invoice)
    instance._audit_invoice_payment_states = before_states


def _capture_deleted_payment_state(instance, using, **_kwargs):
    del _kwargs
    invoice = Invoice.objects.using(using).get(pk=instance.invoice_id)
    instance._audit_invoice_payment_states = {
        invoice.pk: _invoice_payment_state(invoice)
    }


def _record_payment_invoice_changes(instance, using, **_kwargs):
    del _kwargs
    before_states = getattr(instance, "_audit_invoice_payment_states", {})
    _record_invoice_payment_changes(before_states, using)


def register_signals():
    for model in AUDITED_MODELS:
        _connect_model(model)
    pre_save.connect(
        _capture_payment_state,
        sender=Payment,
        weak=False,
        dispatch_uid="audit-payment-invoice-pre-save",
    )
    post_save.connect(
        _record_payment_invoice_changes,
        sender=Payment,
        weak=False,
        dispatch_uid="audit-payment-invoice-post-save",
    )
    pre_delete.connect(
        _capture_deleted_payment_state,
        sender=Payment,
        weak=False,
        dispatch_uid="audit-payment-invoice-pre-delete",
    )
    post_delete.connect(
        _record_payment_invoice_changes,
        sender=Payment,
        weak=False,
        dispatch_uid="audit-payment-invoice-post-delete",
    )
