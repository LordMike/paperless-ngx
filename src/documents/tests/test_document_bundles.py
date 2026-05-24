from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from documents.bundles import BundleItemInput
from documents.bundles import add_document_to_bundle
from documents.bundles import create_bundle
from documents.bundles import generate_bundle_id
from documents.bundles import remove_membership
from documents.bundles import reorder_bundle
from documents.bundles import update_membership
from documents.models import DocumentBundle
from documents.models import DocumentBundleMembership
from documents.tests.factories import DocumentFactory


class TestDocumentBundleModel(TestCase):
    def _reset_modified(self, docs):
        baseline = timezone.now() - timedelta(days=1)
        type(docs[0]).objects.filter(pk__in=[doc.pk for doc in docs]).update(
            modified=baseline,
        )
        return baseline

    def _modified_values(self, docs):
        return dict(
            type(docs[0])
            .objects.filter(pk__in=[doc.pk for doc in docs])
            .values_list("pk", "modified"),
        )

    def _sent_document_ids(self, send_mock):
        return [call.kwargs["document"].pk for call in send_mock.call_args_list]

    def test_create_bundle_generates_id_and_sequential_memberships(self):
        docs = [DocumentFactory(title=f"Document {i}") for i in range(3)]

        bundle = create_bundle(
            items=[BundleItemInput(document=document) for document in docs],
        )

        self.assertEqual(bundle.bundle_id, "BND-001")
        self.assertEqual(
            list(bundle.memberships.values_list("document_id", "order_id")),
            [(docs[0].id, 1), (docs[1].id, 2), (docs[2].id, 3)],
        )

    def test_generate_bundle_id_uses_base36_suffix(self):
        DocumentBundle.objects.create(bundle_id="BND-009")

        self.assertEqual(generate_bundle_id(), "BND-00A")

    def test_generate_bundle_id_uses_latest_valid_generated_id_as_seed(self):
        DocumentBundle.objects.create(bundle_id="BND-00A")
        DocumentBundle.objects.create(bundle_id="BND-00Z")

        self.assertEqual(generate_bundle_id(), "BND-010")

    def test_generate_bundle_id_ignores_invalid_generated_suffix(self):
        DocumentBundle.objects.create(bundle_id="BND-009")
        DocumentBundle.objects.create(bundle_id="BND-ABC-")

        self.assertEqual(generate_bundle_id(), "BND-00A")

    def test_generate_bundle_id_ignores_user_supplied_ids(self):
        DocumentBundle.objects.create(bundle_id="INS-2026-001")

        self.assertEqual(generate_bundle_id(), "BND-001")

    def test_generate_bundle_id_skips_existing_candidate_batch(self):
        now = timezone.now()
        seed = DocumentBundle.objects.create(bundle_id="BND-000")
        for suffix in (
            "001",
            "002",
            "003",
            "004",
            "005",
            "006",
            "007",
            "008",
            "009",
            "00A",
            "00B",
            "00C",
            "00D",
            "00E",
            "00F",
            "00G",
            "00H",
            "00I",
            "00J",
            "00K",
        ):
            DocumentBundle.objects.create(bundle_id=f"BND-{suffix}")
        DocumentBundle.objects.exclude(pk=seed.pk).update(
            created=now - timedelta(days=1),
        )
        DocumentBundle.objects.filter(pk=seed.pk).update(created=now)

        self.assertEqual(generate_bundle_id(), "BND-00L")

    def test_create_bundle_retries_generated_id_after_insert_race(self):
        doc = DocumentFactory()
        real_create = DocumentBundle.objects.create
        calls = 0

        def create_with_race(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise IntegrityError("simulated generated ID race")
            return real_create(*args, **kwargs)

        with (
            mock.patch(
                "documents.bundles.generate_bundle_id",
                side_effect=["BND-001", "BND-002"],
            ),
            mock.patch.object(
                DocumentBundle.objects,
                "create",
                side_effect=create_with_race,
            ),
        ):
            bundle = create_bundle(items=[BundleItemInput(document=doc)])

        self.assertEqual(bundle.bundle_id, "BND-002")
        self.assertEqual(calls, 2)

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

    def test_create_bundle_touches_documents_and_emits_updates(self):
        docs = [DocumentFactory() for _ in range(2)]
        baseline = self._reset_modified(docs)

        with mock.patch("documents.bundles.document_updated.send") as send:
            with self.captureOnCommitCallbacks(execute=True):
                create_bundle(items=[BundleItemInput(document=doc) for doc in docs])

        self.assertTrue(
            all(
                modified > baseline for modified in self._modified_values(docs).values()
            ),
        )
        self.assertCountEqual(self._sent_document_ids(send), [doc.pk for doc in docs])

    def test_update_membership_noop_does_not_touch_documents(self):
        docs = [DocumentFactory() for _ in range(2)]
        bundle = create_bundle(items=[BundleItemInput(document=doc) for doc in docs])
        baseline = self._reset_modified(docs)
        membership = bundle.memberships.order_by("order_id").first()

        with mock.patch("documents.bundles.document_updated.send") as send:
            with self.captureOnCommitCallbacks(execute=True):
                update_membership(
                    membership=membership,
                    bundle_item_name=membership.bundle_item_name,
                    bundle_item_type=membership.bundle_item_type,
                )

        self.assertEqual(
            set(self._modified_values(docs).values()),
            {baseline},
        )
        send.assert_not_called()

    def test_update_membership_touches_all_bundle_documents(self):
        docs = [DocumentFactory() for _ in range(2)]
        bundle = create_bundle(items=[BundleItemInput(document=doc) for doc in docs])
        baseline = self._reset_modified(docs)
        membership = bundle.memberships.order_by("order_id").first()

        with mock.patch("documents.bundles.document_updated.send") as send:
            with self.captureOnCommitCallbacks(execute=True):
                update_membership(
                    membership=membership,
                    bundle_item_name="new label",
                )

        self.assertTrue(
            all(
                modified > baseline for modified in self._modified_values(docs).values()
            ),
        )
        self.assertCountEqual(self._sent_document_ids(send), [doc.pk for doc in docs])

    def test_reorder_noop_does_not_touch_documents(self):
        docs = [DocumentFactory() for _ in range(3)]
        bundle = create_bundle(items=[BundleItemInput(document=doc) for doc in docs])
        membership_ids = list(
            bundle.memberships.order_by("order_id").values_list("id", flat=True),
        )
        baseline = self._reset_modified(docs)

        with mock.patch("documents.bundles.document_updated.send") as send:
            with self.captureOnCommitCallbacks(execute=True):
                reorder_bundle(bundle=bundle, membership_ids=membership_ids)

        self.assertEqual(
            set(self._modified_values(docs).values()),
            {baseline},
        )
        send.assert_not_called()

    def test_reorder_touches_all_bundle_documents(self):
        docs = [DocumentFactory() for _ in range(3)]
        bundle = create_bundle(items=[BundleItemInput(document=doc) for doc in docs])
        membership_ids = list(
            bundle.memberships.order_by("-order_id").values_list("id", flat=True),
        )
        baseline = self._reset_modified(docs)

        with mock.patch("documents.bundles.document_updated.send") as send:
            with self.captureOnCommitCallbacks(execute=True):
                reorder_bundle(bundle=bundle, membership_ids=membership_ids)

        self.assertTrue(
            all(
                modified > baseline for modified in self._modified_values(docs).values()
            ),
        )
        self.assertCountEqual(self._sent_document_ids(send), [doc.pk for doc in docs])

    def test_remove_membership_touches_removed_and_remaining_documents(self):
        docs = [DocumentFactory() for _ in range(2)]
        bundle = create_bundle(items=[BundleItemInput(document=doc) for doc in docs])
        baseline = self._reset_modified(docs)
        membership = bundle.memberships.get(document=docs[0])

        with mock.patch("documents.bundles.document_updated.send") as send:
            with self.captureOnCommitCallbacks(execute=True):
                remove_membership(membership)

        self.assertTrue(
            all(
                modified > baseline for modified in self._modified_values(docs).values()
            ),
        )
        self.assertCountEqual(self._sent_document_ids(send), [doc.pk for doc in docs])


class TestDocumentBundleAPI(APITestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_superuser(username="bundle_admin")
        self.client.force_authenticate(user=self.user)

    def _reset_modified(self, docs):
        baseline = timezone.now() - timedelta(days=1)
        type(docs[0]).objects.filter(pk__in=[doc.pk for doc in docs]).update(
            modified=baseline,
        )
        return baseline

    def _modified_values(self, docs):
        return dict(
            type(docs[0])
            .objects.filter(pk__in=[doc.pk for doc in docs])
            .values_list("pk", "modified"),
        )

    def _sent_document_ids(self, send_mock):
        return [call.kwargs["document"].pk for call in send_mock.call_args_list]

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
            name="Policy package",
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
            {"q": "A8", "ordering": "-created"},
        )
        self.assertEqual(bundles.status_code, status.HTTP_200_OK)
        self.assertEqual(bundles.data["count"], 1)
        self.assertEqual(bundles.data["results"][0]["bundle_id"], "A87")
        self.assertEqual(bundles.data["results"][0]["document_count"], 3)

        bundles = self.client.get("/api/bundles/", {"q": "Policy"})
        self.assertEqual(bundles.status_code, status.HTTP_200_OK)
        self.assertEqual(bundles.data["count"], 1)

    def test_bundle_api_returns_ordered_members_and_rejects_duplicate_document(self):
        docs = [DocumentFactory(title="A"), DocumentFactory(title="B")]

        response = self.client.post(
            "/api/bundles/",
            {
                "documents": [doc.pk for doc in docs],
                "bundle_id": "A90",
                "name": "Contract package",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["bundle_id"], "A90")
        self.assertEqual(response.data["name"], "Contract package")
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

    def test_suggest_id_create_for_document_and_move_document(self):
        docs = [
            DocumentFactory(title="Schedule"),
            DocumentFactory(title="Terms"),
        ]
        source = create_bundle(
            items=[BundleItemInput(document=docs[0], bundle_item_name="schedule")],
            bundle_id="A91",
        )
        target = create_bundle(
            items=[BundleItemInput(document=docs[1], bundle_item_name="terms")],
            bundle_id="A92",
        )
        membership = source.memberships.get()

        suggested = self.client.get("/api/bundles/suggest_id/")
        self.assertEqual(suggested.status_code, status.HTTP_200_OK)
        self.assertRegex(suggested.data["bundle_id"], r"^BND-[0-9A-Z]{3,}$")

        moved = self.client.post(
            f"/api/bundles/{target.pk}/move_document/",
            {"membership": membership.pk},
            format="json",
        )
        self.assertEqual(moved.status_code, status.HTTP_200_OK)
        self.assertEqual(moved.data["document"], docs[0].pk)
        self.assertEqual(moved.data["bundle_item_name"], "schedule")
        self.assertFalse(DocumentBundle.objects.filter(pk=source.pk).exists())
        self.assertEqual(target.memberships.count(), 2)

        created = self.client.post(
            "/api/bundles/create_for_document/",
            {
                "document": docs[0].pk,
                "bundle_id": "A93",
                "name": "New package",
            },
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(created.data["bundle_id"], "A93")
        self.assertEqual(created.data["name"], "New package")
        self.assertEqual(created.data["items"][0]["document"], docs[0].pk)
        self.assertEqual(target.memberships.count(), 1)

    def test_bundle_patch_noop_does_not_touch_documents(self):
        docs = [DocumentFactory(title="A"), DocumentFactory(title="B")]
        bundle = create_bundle(
            items=[BundleItemInput(document=doc) for doc in docs],
            bundle_id="A94",
            name="Package",
        )
        baseline = self._reset_modified(docs)

        with mock.patch("documents.bundles.document_updated.send") as send:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.patch(
                    f"/api/bundles/{bundle.pk}/",
                    {"bundle_id": "A94", "name": "Package"},
                    format="json",
                )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(self._modified_values(docs).values()), {baseline})
        send.assert_not_called()

    def test_bundle_patch_touches_all_documents_when_display_changes(self):
        docs = [DocumentFactory(title="A"), DocumentFactory(title="B")]
        bundle = create_bundle(
            items=[BundleItemInput(document=doc) for doc in docs],
            bundle_id="A95",
            name="Package",
        )
        baseline = self._reset_modified(docs)

        with mock.patch("documents.bundles.document_updated.send") as send:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.patch(
                    f"/api/bundles/{bundle.pk}/",
                    {"name": "Updated package"},
                    format="json",
                )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            all(
                modified > baseline for modified in self._modified_values(docs).values()
            ),
        )
        self.assertCountEqual(self._sent_document_ids(send), [doc.pk for doc in docs])

    def test_bundle_delete_touches_former_documents_without_deleting_them(self):
        docs = [DocumentFactory(title="A"), DocumentFactory(title="B")]
        bundle = create_bundle(
            items=[BundleItemInput(document=doc) for doc in docs],
            bundle_id="A96",
        )
        baseline = self._reset_modified(docs)

        with mock.patch("documents.bundles.document_updated.send") as send:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.delete(f"/api/bundles/{bundle.pk}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(DocumentBundle.objects.filter(pk=bundle.pk).exists())
        self.assertTrue(
            all(type(docs[0]).objects.filter(pk=doc.pk).exists() for doc in docs),
        )
        self.assertTrue(
            all(
                modified > baseline for modified in self._modified_values(docs).values()
            ),
        )
        self.assertCountEqual(self._sent_document_ids(send), [doc.pk for doc in docs])
