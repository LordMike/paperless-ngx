from __future__ import annotations

from collections import OrderedDict
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count
from django.db.models import Prefetch
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import CharFilter
from django_filters.rest_framework import DjangoFilterBackend
from django_filters.rest_framework import FilterSet
from rest_framework import serializers
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from documents.bundles import BundleItemInput
from documents.bundles import add_document_to_bundle
from documents.bundles import assert_can_change_bundle
from documents.bundles import assert_can_change_documents
from documents.bundles import can_view_document
from documents.bundles import create_bundle
from documents.bundles import generate_bundle_id
from documents.bundles import normalize_bundle_id
from documents.bundles import remove_membership
from documents.bundles import reorder_bundle
from documents.bundles import touch_bundle_documents
from documents.bundles import update_membership
from documents.bundles import visible_documents_queryset
from documents.filters import CHAR_KWARGS
from documents.filters import DATETIME_KWARGS
from documents.filters import ID_KWARGS
from documents.models import Document
from documents.models import DocumentBundle
from documents.models import DocumentBundleMembership


class DocumentBundlePagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100000

    def _get_api_version(self) -> int:
        request = getattr(self, "request", None)
        default_version = settings.REST_FRAMEWORK["DEFAULT_VERSION"]
        return int(request.version if request else default_version)

    def _should_include_all(self) -> bool:
        return self._get_api_version() < 10

    def get_paginated_response(self, data):
        response_data = [
            ("count", self.page.paginator.count),
            ("next", self.get_next_link()),
            ("previous", self.get_previous_link()),
        ]
        if self._should_include_all():
            response_data.append(
                ("all", self.page.paginator.object_list.values_list("pk", flat=True)),
            )
        response_data.append(("results", data))

        return Response(OrderedDict(response_data))

    def get_paginated_response_schema(self, schema):
        response_schema = super().get_paginated_response_schema(schema)
        if self._should_include_all():
            response_schema["properties"]["all"] = {
                "type": "array",
                "example": "[1, 2, 3]",
                "items": {"type": "integer"},
            }
        else:
            response_schema["properties"].pop("all", None)
        return response_schema


class DocumentBundleItemSummarySerializer(serializers.Serializer[dict[str, Any]]):
    membership_id = serializers.IntegerField()
    document = serializers.IntegerField()
    order_id = serializers.IntegerField()
    bundle_item_name = serializers.CharField()
    bundle_item_type = serializers.CharField()
    created = serializers.DateTimeField()
    title = serializers.CharField(allow_blank=True)


class DocumentBundleSummarySerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.IntegerField()
    name = serializers.CharField(allow_blank=True)
    bundle_id = serializers.CharField()
    current_membership_id = serializers.IntegerField()
    current_order_id = serializers.IntegerField()
    current_bundle_item_name = serializers.CharField()
    current_bundle_item_type = serializers.CharField()
    current_membership_created = serializers.DateTimeField()
    items = DocumentBundleItemSummarySerializer(many=True)


class DocumentBundleMembershipSerializer(serializers.ModelSerializer):
    document_title = serializers.CharField(source="document.title", read_only=True)

    class Meta:
        model = DocumentBundleMembership
        fields = (
            "id",
            "document",
            "document_title",
            "order_id",
            "bundle_item_name",
            "bundle_item_type",
            "created",
        )
        read_only_fields = ("id", "order_id", "created", "document_title")


class DocumentBundleCreateItemSerializer(serializers.Serializer):
    document = serializers.PrimaryKeyRelatedField(queryset=Document.objects.all())
    bundle_item_name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=256,
    )
    bundle_item_type = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=128,
    )


class DocumentBundleSerializer(serializers.ModelSerializer):
    document_count = serializers.IntegerField(read_only=True)
    items = DocumentBundleMembershipSerializer(
        source="memberships",
        many=True,
        read_only=True,
    )
    documents = serializers.PrimaryKeyRelatedField(
        queryset=Document.objects.all(),
        many=True,
        write_only=True,
        required=False,
    )
    create_items = DocumentBundleCreateItemSerializer(
        many=True,
        write_only=True,
        required=False,
    )

    class Meta:
        model = DocumentBundle
        fields = (
            "id",
            "name",
            "bundle_id",
            "created",
            "document_count",
            "items",
            "documents",
            "create_items",
        )
        read_only_fields = ("id", "created", "document_count", "items")
        extra_kwargs = {"bundle_id": {"required": False}}

    def validate_bundle_id(self, value):
        return normalize_bundle_id(value)

    def validate(self, attrs):
        if (
            self.instance is None
            and not attrs.get("documents")
            and not attrs.get("create_items")
        ):
            raise serializers.ValidationError(
                {"documents": "A bundle must contain at least one document."},
            )
        return attrs

    def create(self, validated_data):
        documents = validated_data.pop("documents", None)
        create_items = validated_data.pop("create_items", None)
        bundle_id = validated_data.get("bundle_id")
        name = validated_data.get("name")

        if create_items:
            items = [
                BundleItemInput(
                    document=item["document"],
                    bundle_item_name=item.get("bundle_item_name"),
                    bundle_item_type=item.get("bundle_item_type"),
                )
                for item in create_items
            ]
        else:
            items = [BundleItemInput(document=document) for document in documents]

        try:
            return create_bundle(items=items, bundle_id=bundle_id, name=name)
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.messages)

    def update(self, instance, validated_data):
        update_fields = []
        if "name" in validated_data and validated_data["name"] != instance.name:
            instance.name = validated_data["name"]
            update_fields.append("name")
        bundle_id = validated_data.get("bundle_id")
        if bundle_id is not None and bundle_id != instance.bundle_id:
            instance.bundle_id = bundle_id
            update_fields.append("bundle_id")
        if update_fields:
            instance.save(update_fields=update_fields)
            touch_bundle_documents(
                instance.memberships.values_list("document_id", flat=True),
            )
        return instance


class DocumentBundleAddDocumentSerializer(serializers.Serializer):
    document = serializers.PrimaryKeyRelatedField(queryset=Document.objects.all())
    bundle_item_name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=256,
    )
    bundle_item_type = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=128,
    )


class DocumentBundleCreateForDocumentSerializer(serializers.Serializer):
    document = serializers.PrimaryKeyRelatedField(queryset=Document.objects.all())
    name = serializers.CharField(required=False, allow_blank=True, max_length=128)
    bundle_id = serializers.CharField(required=False, allow_blank=True, max_length=32)
    bundle_item_name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=256,
    )
    bundle_item_type = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=128,
    )

    def validate_bundle_id(self, value):
        if not value:
            return value
        normalized = normalize_bundle_id(value)
        if DocumentBundle.objects.filter(bundle_id=normalized).exists():
            raise serializers.ValidationError(
                "Document bundle with this bundle ID already exists.",
            )
        return normalized


class DocumentBundleMoveDocumentSerializer(serializers.Serializer):
    membership = serializers.PrimaryKeyRelatedField(
        queryset=DocumentBundleMembership.objects.select_related("document", "bundle"),
    )
    bundle_item_name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=256,
    )
    bundle_item_type = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=128,
    )


class DocumentBundleMembershipUpdateSerializer(serializers.Serializer):
    bundle_item_name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=256,
    )
    bundle_item_type = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=128,
    )


class DocumentBundleReorderSerializer(serializers.Serializer):
    membership_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False,
    )


class DocumentBundleFilterSet(FilterSet):
    q = CharFilter(method="filter_name_or_bundle_id")
    bundle_id__icontains = CharFilter(
        field_name="bundle_id",
        lookup_expr="icontains",
    )
    name__icontains = CharFilter(field_name="name", lookup_expr="icontains")

    def filter_name_or_bundle_id(self, queryset, name, value):
        return queryset.filter(
            Q(bundle_id__icontains=value) | Q(name__icontains=value),
        )

    class Meta:
        model = DocumentBundle
        fields = {
            "id": ID_KWARGS,
            "name": CHAR_KWARGS,
            "bundle_id": CHAR_KWARGS,
            "created": DATETIME_KWARGS,
        }


def bundle_membership_prefetch() -> Prefetch:
    return Prefetch(
        "bundle_memberships",
        queryset=DocumentBundleMembership.objects.select_related("bundle"),
    )


def serialize_document_bundle(document: Document, user) -> dict[str, Any] | None:
    prefetched_cache = getattr(document, "_prefetched_objects_cache", None)
    prefetched_memberships = (
        prefetched_cache.get("bundle_memberships")
        if isinstance(prefetched_cache, dict)
        else None
    )
    if prefetched_memberships is not None:
        memberships = list(prefetched_memberships)
    else:
        memberships = list(
            document.bundle_memberships.select_related("bundle").all()[:1],
        )
    if not memberships:
        return None

    membership = memberships[0]
    bundle = membership.bundle
    bundle_memberships = bundle.memberships.select_related("document").order_by(
        "order_id",
    )
    items = [
        {
            "membership_id": item.id,
            "document": item.document_id,
            "order_id": item.order_id,
            "bundle_item_name": item.bundle_item_name,
            "bundle_item_type": item.bundle_item_type,
            "created": item.created,
            "title": item.document.title,
        }
        for item in bundle_memberships
        if user is None or can_view_document(user, item.document)
    ]
    return {
        "id": bundle.id,
        "name": bundle.name,
        "bundle_id": bundle.bundle_id,
        "current_membership_id": membership.id,
        "current_order_id": membership.order_id,
        "current_bundle_item_name": membership.bundle_item_name,
        "current_bundle_item_type": membership.bundle_item_type,
        "current_membership_created": membership.created,
        "items": items,
    }


class DocumentBundleViewSet(ModelViewSet[DocumentBundle]):
    model = DocumentBundle
    queryset = DocumentBundle.objects.all()
    serializer_class = DocumentBundleSerializer
    pagination_class = DocumentBundlePagination
    permission_classes = (IsAuthenticated,)
    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
    )
    filterset_class = DocumentBundleFilterSet
    ordering_fields = ("name", "bundle_id", "created", "document_count")

    def get_queryset(self):
        visible_documents = visible_documents_queryset(self.request.user)
        visible_memberships = DocumentBundleMembership.objects.filter(
            document__in=visible_documents,
        ).select_related("document")
        return (
            DocumentBundle.objects.filter(memberships__document__in=visible_documents)
            .annotate(
                document_count=Count(
                    "memberships",
                    filter=Q(memberships__document__in=visible_documents),
                    distinct=True,
                ),
            )
            .distinct()
            .prefetch_related(
                Prefetch(
                    "memberships",
                    queryset=visible_memberships.order_by("order_id"),
                ),
            )
            .order_by("bundle_id")
        )

    @action(methods=["get"], detail=False, url_path="suggest_id")
    def suggest_id(self, request):
        return Response({"bundle_id": generate_bundle_id()})

    def _raise_permission_error(self):
        raise PermissionDenied(_("Insufficient document permissions."))

    def _check_change_bundle(self, bundle: DocumentBundle) -> None:
        try:
            assert_can_change_bundle(self.request.user, bundle)
        except PermissionError:
            self._raise_permission_error()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        documents = serializer.validated_data.get("documents") or [
            item["document"]
            for item in serializer.validated_data.get("create_items", [])
        ]
        try:
            assert_can_change_documents(request.user, documents)
            bundle = serializer.save()
        except PermissionError:
            self._raise_permission_error()
        except DjangoValidationError as e:
            raise ValidationError(e.messages)
        response_serializer = self.get_serializer(bundle)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        bundle = self.get_object()
        self._check_change_bundle(bundle)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        bundle = self.get_object()
        self._check_change_bundle(bundle)
        document_ids = list(bundle.memberships.values_list("document_id", flat=True))
        bundle.delete()
        touch_bundle_documents(document_ids)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(methods=["post"], detail=True, url_path="documents")
    def add_document(self, request, pk=None):
        bundle = self.get_object()
        self._check_change_bundle(bundle)
        serializer = DocumentBundleAddDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = serializer.validated_data["document"]
        try:
            assert_can_change_documents(request.user, [document])
            membership = add_document_to_bundle(
                bundle=bundle,
                document=document,
                bundle_item_name=serializer.validated_data.get("bundle_item_name"),
                bundle_item_type=serializer.validated_data.get("bundle_item_type"),
            )
        except PermissionError:
            self._raise_permission_error()
        except DjangoValidationError as e:
            raise ValidationError(e.messages)
        return Response(
            DocumentBundleMembershipSerializer(membership).data,
            status=status.HTTP_201_CREATED,
        )

    @action(methods=["post"], detail=False, url_path="create_for_document")
    def create_for_document(self, request):
        serializer = DocumentBundleCreateForDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = serializer.validated_data["document"]
        try:
            assert_can_change_documents(request.user, [document])
            with transaction.atomic():
                membership = (
                    DocumentBundleMembership.objects.select_related("bundle")
                    .filter(document=document)
                    .first()
                )
                touch_document_ids = {document.pk}
                if membership:
                    assert_can_change_bundle(request.user, membership.bundle)
                    touch_document_ids.update(
                        membership.bundle.memberships.values_list(
                            "document_id",
                            flat=True,
                        ),
                    )
                    remove_membership(membership, touch_documents=False)
                bundle = create_bundle(
                    items=[
                        BundleItemInput(
                            document=document,
                            bundle_item_name=serializer.validated_data.get(
                                "bundle_item_name",
                            ),
                            bundle_item_type=serializer.validated_data.get(
                                "bundle_item_type",
                            ),
                        ),
                    ],
                    bundle_id=serializer.validated_data.get("bundle_id") or None,
                    name=serializer.validated_data.get("name"),
                    touch_documents=False,
                )
                touch_bundle_documents(touch_document_ids)
        except PermissionError:
            self._raise_permission_error()
        except DjangoValidationError as e:
            raise ValidationError(e.messages)
        return Response(
            self.get_serializer(bundle).data,
            status=status.HTTP_201_CREATED,
        )

    @action(methods=["post"], detail=True, url_path="move_document")
    def move_document(self, request, pk=None):
        target_bundle = self.get_object()
        serializer = DocumentBundleMoveDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = serializer.validated_data["membership"]
        source_bundle = membership.bundle
        if source_bundle.pk == target_bundle.pk:
            return Response(DocumentBundleMembershipSerializer(membership).data)
        try:
            self._check_change_bundle(source_bundle)
            self._check_change_bundle(target_bundle)
            document = membership.document
            assert_can_change_documents(request.user, [document])
            with transaction.atomic():
                touch_document_ids = set(
                    source_bundle.memberships.values_list("document_id", flat=True),
                )
                bundle_item_name = serializer.validated_data.get(
                    "bundle_item_name",
                    membership.bundle_item_name,
                )
                bundle_item_type = serializer.validated_data.get(
                    "bundle_item_type",
                    membership.bundle_item_type,
                )
                remove_membership(membership, touch_documents=False)
                new_membership = add_document_to_bundle(
                    bundle=target_bundle,
                    document=document,
                    bundle_item_name=bundle_item_name,
                    bundle_item_type=bundle_item_type,
                    touch_documents=False,
                )
                touch_document_ids.update(
                    target_bundle.memberships.values_list("document_id", flat=True),
                )
                touch_bundle_documents(touch_document_ids)
        except PermissionError:
            self._raise_permission_error()
        except DjangoValidationError as e:
            raise ValidationError(e.messages)
        return Response(DocumentBundleMembershipSerializer(new_membership).data)

    @action(
        methods=["patch", "delete"],
        detail=True,
        url_path=r"documents/(?P<membership_pk>[^/.]+)",
    )
    def document(self, request, pk=None, membership_pk=None):
        bundle = self.get_object()
        self._check_change_bundle(bundle)
        membership = get_object_or_404(
            DocumentBundleMembership.objects.select_related("document", "bundle"),
            pk=membership_pk,
            bundle=bundle,
        )
        if request.method.lower() == "delete":
            remove_membership(membership)
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = DocumentBundleMembershipUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = update_membership(
            membership=membership,
            bundle_item_name=serializer.validated_data.get("bundle_item_name"),
            bundle_item_type=serializer.validated_data.get("bundle_item_type"),
        )
        return Response(DocumentBundleMembershipSerializer(membership).data)

    @action(methods=["patch"], detail=True, url_path="order")
    def reorder(self, request, pk=None):
        bundle = self.get_object()
        self._check_change_bundle(bundle)
        serializer = DocumentBundleReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            reorder_bundle(
                bundle=bundle,
                membership_ids=serializer.validated_data["membership_ids"],
            )
        except DjangoValidationError as e:
            raise ValidationError(e.messages)
        return Response(self.get_serializer(bundle).data)
