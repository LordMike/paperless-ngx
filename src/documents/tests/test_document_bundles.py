from __future__ import annotations

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from documents.bundles import BundleItemInput
from documents.bundles import add_document_to_bundle
from documents.bundles import create_bundle
from documents.bundles import remove_membership
from documents.bundles import reorder_bundle
from documents.models import DocumentBundle
from documents.models import DocumentBundleMembership
from documents.tests.factories import DocumentFactory


class TestDocumentBundleModel(TestCase):
    def test_create_bundle_generates_id_and_sequential_memberships(self):
        docs = [DocumentFactory(title=f"Document {i}") for i in range(3)]

        bundle = create_bundle(
            items=[BundleItemInput(document=document) for document in docs],
        )

        self.assertRegex(bundle.bundle_id, r"^A[0-9A-Z]{3}$")
        self.assertEqual(
            list(bundle.memberships.values_list("document_id", "order_id")),
            [(docs[0].id, 1), (docs[1].id, 2), (docs[2].id, 3)],
        )

    def test_reject_duplicate_bundle_id(self):
        DocumentBundle.objects.create(bundle_id="A87")

        with self.assertRaises(IntegrityError):
            DocumentBundle.objects.create(bundle_id="A87")

    def test_reject_duplicate_document_membership(self):
        doc = DocumentFactory()
        bundle = create_bundle(items=[BundleItemInput(document=doc)])

        with self.assertRaises(ValidationError):
            add_document_to_bundle(bundle=bundle, document=doc)

    def test_reject_duplicate_order_id(self):
        docs = [DocumentFactory() for _ in range(2)]
        bundle = create_bundle(items=[BundleItemInput(document=docs[0])])

        with self.assertRaises(IntegrityError):
            DocumentBundleMembership.objects.create(
                bundle=bundle,
                document=docs[1],
                order_id=1,
                bundle_item_name="duplicate order",
            )

    def test_reject_same_document_in_different_bundle_for_mvp(self):
        doc = DocumentFactory()
        create_bundle(items=[BundleItemInput(document=doc)])

        with self.assertRaises(ValidationError):
            create_bundle(items=[BundleItemInput(document=doc)])

    def test_remove_last_membership_deletes_bundle_but_not_document(self):
        doc = DocumentFactory()
        bundle = create_bundle(items=[BundleItemInput(document=doc)])
        membership = bundle.memberships.get()

        remove_membership(membership)

        self.assertFalse(DocumentBundle.objects.filter(pk=bundle.pk).exists())
        self.assertTrue(type(doc).objects.filter(pk=doc.pk).exists())

    def test_deleting_document_removes_last_membership_and_bundle(self):
        doc = DocumentFactory()
        bundle = create_bundle(items=[BundleItemInput(document=doc)])

        doc.delete()

        self.assertFalse(DocumentBundle.objects.filter(pk=bundle.pk).exists())
        self.assertFalse(DocumentBundleMembership.objects.exists())

    def test_reorder_rewrites_sequential_order(self):
        docs = [DocumentFactory() for _ in range(3)]
        bundle = create_bundle(
            items=[BundleItemInput(document=document) for document in docs],
        )
        membership_ids = list(
            bundle.memberships.order_by("-order_id").values_list("id", flat=True),
        )

        reorder_bundle(bundle=bundle, membership_ids=membership_ids)

        self.assertEqual(
            list(bundle.memberships.order_by("order_id").values_list("id", flat=True)),
            membership_ids,
        )


class TestDocumentBundleAPI(APITestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_superuser(username="bundle_admin")
        self.client.force_authenticate(user=self.user)

    def test_document_detail_and_list_include_bundle(self):
        docs = [
            DocumentFactory(title="mail body"),
            DocumentFactory(title="Policy schedule"),
            DocumentFactory(title="General terms"),
        ]
        bundle = create_bundle(
            items=[
                BundleItemInput(document=docs[0], bundle_item_name="mail body"),
                BundleItemInput(
                    document=docs[1],
                    bundle_item_name="Policy schedule.pdf",
                ),
                BundleItemInput(
                    document=docs[2],
                    bundle_item_name="General terms.pdf",
                ),
            ],
            bundle_id="A87",
        )

        detail = self.client.get(f"/api/documents/{docs[1].pk}/").data
        self.assertEqual(detail["bundle"]["id"], bundle.id)
        self.assertEqual(detail["bundle"]["bundle_id"], "A87")
        self.assertEqual(detail["bundle"]["current_order_id"], 2)
        self.assertEqual(
            [item["bundle_item_name"] for item in detail["bundle"]["items"]],
            ["mail body", "Policy schedule.pdf", "General terms.pdf"],
        )

        response = self.client.get("/api/documents/", {"bundle_id": "A87"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)
        self.assertIn("bundle", response.data["results"][0])

        bundles = self.client.get(
            "/api/bundles/",
            {"bundle_id__icontains": "A8", "ordering": "-created"},
        )
        self.assertEqual(bundles.status_code, status.HTTP_200_OK)
        self.assertEqual(bundles.data["count"], 1)
        self.assertEqual(bundles.data["results"][0]["bundle_id"], "A87")
        self.assertEqual(bundles.data["results"][0]["document_count"], 3)

    def test_bundle_api_returns_ordered_members_and_rejects_duplicate_document(self):
        docs = [DocumentFactory(title="A"), DocumentFactory(title="B")]

        response = self.client.post(
            "/api/bundles/",
            {"documents": [doc.pk for doc in docs]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            [item["order_id"] for item in response.data["items"]],
            [1, 2],
        )

        duplicate = self.client.post(
            f"/api/bundles/{response.data['id']}/documents/",
            {"document": docs[0].pk},
            format="json",
        )
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)
