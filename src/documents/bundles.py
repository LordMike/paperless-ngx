from __future__ import annotations

import string
from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db import transaction
from django.db.models import Max

from documents.models import Document
from documents.models import DocumentBundle
from documents.models import DocumentBundleMembership
from documents.permissions import get_objects_for_user_owner_aware
from documents.permissions import has_perms_owner_aware

if TYPE_CHECKING:
    from collections.abc import Iterable

BUNDLE_ID_MAX_LENGTH = 32
BUNDLE_ID_ALLOWED_CHARS = set(string.ascii_uppercase + string.digits + "_-")


@dataclass(frozen=True)
class BundleItemInput:
    document: Document
    bundle_item_name: str | None = None


def normalize_bundle_id(bundle_id: str) -> str:
    normalized = bundle_id.strip().upper()
    if not normalized:
        raise ValidationError("Bundle ID is required.")
    if len(normalized) > BUNDLE_ID_MAX_LENGTH:
        raise ValidationError("Bundle ID must be 32 characters or fewer.")
    if any(char not in BUNDLE_ID_ALLOWED_CHARS for char in normalized):
        raise ValidationError(
            "Bundle ID may only contain A-Z, 0-9, underscores, and hyphens.",
        )
    return normalized


def _to_base36(value: int) -> str:
    alphabet = string.digits + string.ascii_uppercase
    if value == 0:
        return "0"
    result = ""
    while value:
        value, remainder = divmod(value, 36)
        result = alphabet[remainder] + result
    return result


def generate_bundle_id() -> str:
    max_id = DocumentBundle.objects.aggregate(max_id=Max("id"))["max_id"] or 0
    start = max_id
    for offset in range(10000):
        candidate = f"A{_to_base36(start + offset).zfill(3)}"
        if not DocumentBundle.objects.filter(bundle_id=candidate).exists():
            return candidate
    raise ValidationError("Could not generate a unique bundle ID.")


def default_bundle_item_name(document: Document) -> str:
    return str(
        document.title
        or document.original_filename
        or document.filename
        or str(document.pk),
    )


def _coerce_items(items: Iterable[BundleItemInput]) -> list[BundleItemInput]:
    coerced = list(items)
    if not coerced:
        raise ValidationError("A bundle must contain at least one document.")
    return coerced


def _validate_documents_are_unbundled(documents: Iterable[Document]) -> None:
    document_ids = [document.pk for document in documents]
    bundled_document_ids = set(
        DocumentBundleMembership.objects.filter(document_id__in=document_ids)
        .values_list("document_id", flat=True)
        .distinct(),
    )
    if bundled_document_ids:
        raise ValidationError(
            f"Document(s) already belong to a bundle: {sorted(bundled_document_ids)}",
        )


def create_bundle(
    *,
    items: Iterable[BundleItemInput],
    bundle_id: str | None = None,
) -> DocumentBundle:
    items = _coerce_items(items)
    _validate_documents_are_unbundled(item.document for item in items)

    with transaction.atomic():
        normalized_bundle_id = normalize_bundle_id(bundle_id) if bundle_id else None
        for attempt in range(10):
            try:
                bundle = DocumentBundle.objects.create(
                    bundle_id=normalized_bundle_id or generate_bundle_id(),
                )
                break
            except IntegrityError:
                if normalized_bundle_id is not None or attempt == 9:
                    raise
        else:  # pragma: no cover
            raise ValidationError("Could not create bundle.")

        memberships = [
            DocumentBundleMembership(
                bundle=bundle,
                document=item.document,
                order_id=index,
                bundle_item_name=(
                    item.bundle_item_name or default_bundle_item_name(item.document)
                ),
            )
            for index, item in enumerate(items, start=1)
        ]
        DocumentBundleMembership.objects.bulk_create(memberships)
        return bundle


def add_document_to_bundle(
    *,
    bundle: DocumentBundle,
    document: Document,
    bundle_item_name: str | None = None,
) -> DocumentBundleMembership:
    _validate_documents_are_unbundled([document])
    with transaction.atomic():
        next_order_id = (
            DocumentBundleMembership.objects.filter(bundle=bundle).aggregate(
                max_order=Max("order_id"),
            )["max_order"]
            or 0
        ) + 1
        return DocumentBundleMembership.objects.create(
            bundle=bundle,
            document=document,
            order_id=next_order_id,
            bundle_item_name=bundle_item_name or default_bundle_item_name(document),
        )


def update_membership(
    *,
    membership: DocumentBundleMembership,
    bundle_item_name: str | None = None,
) -> DocumentBundleMembership:
    if bundle_item_name is not None:
        membership.bundle_item_name = bundle_item_name
        membership.save(update_fields=["bundle_item_name"])
    return membership


def reorder_bundle(
    *,
    bundle: DocumentBundle,
    membership_ids: list[int],
) -> None:
    with transaction.atomic():
        memberships = list(
            DocumentBundleMembership.objects.select_for_update()
            .filter(bundle=bundle)
            .order_by("order_id"),
        )
        current_ids = [membership.pk for membership in memberships]
        if sorted(current_ids) != sorted(membership_ids):
            raise ValidationError(
                "Reorder payload must include every bundle item once.",
            )

        by_id = {membership.pk: membership for membership in memberships}
        offset = max((membership.order_id for membership in memberships), default=0)
        for index, membership in enumerate(memberships, start=1):
            membership.order_id = offset + index
            membership.save(update_fields=["order_id"])
        for order_id, membership_id in enumerate(membership_ids, start=1):
            membership = by_id[membership_id]
            membership.order_id = order_id
            membership.save(update_fields=["order_id"])


def remove_membership(membership: DocumentBundleMembership) -> None:
    bundle = membership.bundle
    with transaction.atomic():
        membership.delete()
        remaining = list(
            DocumentBundleMembership.objects.filter(bundle=bundle).order_by("order_id"),
        )
        if not remaining:
            bundle.delete()
            return
        for order_id, remaining_membership in enumerate(remaining, start=1):
            if remaining_membership.order_id != order_id:
                remaining_membership.order_id = order_id
                remaining_membership.save(update_fields=["order_id"])


def remove_document_from_all_bundles(document: Document) -> None:
    memberships = list(
        DocumentBundleMembership.objects.select_related("bundle").filter(
            document=document,
        ),
    )
    for membership in memberships:
        remove_membership(membership)


def can_view_document(user, document: Document) -> bool:
    return has_perms_owner_aware(user, "view_document", document)


def can_change_document(user, document: Document) -> bool:
    return has_perms_owner_aware(user, "change_document", document)


def visible_documents_queryset(user):
    return get_objects_for_user_owner_aware(user, "view_document", Document)


def assert_can_change_documents(user, documents: Iterable[Document]) -> None:
    if not all(can_change_document(user, document) for document in documents):
        raise PermissionError("Insufficient document permissions.")


def assert_can_change_bundle(user, bundle: DocumentBundle) -> None:
    documents = [
        membership.document
        for membership in DocumentBundleMembership.objects.filter(bundle=bundle)
        .select_related("document")
        .all()
    ]
    assert_can_change_documents(user, documents)
