from django.contrib.auth.models import User

from documents.bundles import BundleItemInput
from documents.bundles import create_bundle
from documents.models import Document
from documents.models import DocumentBundle

USER = "bundleadmin"
PASSWORD = "bundlepass"
DEMO_BUNDLES = {
    "INS-2026-001": [
        (
            "Bundle demo - Insurance mail body",
            "mail body",
            "Email cover letter for the insurance policy package.",
        ),
        (
            "Bundle demo - Policy schedule",
            "Policy schedule.pdf",
            "Policy schedule for the insurance package.",
        ),
        (
            "Bundle demo - General terms 2026",
            "General terms 2026.pdf",
            "General insurance terms for 2026.",
        ),
        (
            "Bundle demo - Price notice",
            "Price notice.pdf",
            "Price notice for the insurance package.",
        ),
    ],
    "HR-2026-001": [
        (
            "Bundle demo - Employment contract",
            "employment contract",
            "Employment contract text.",
        ),
        (
            "Bundle demo - Ownership agreement",
            "ownership agreement",
            "Ownership agreement text.",
        ),
        (
            "Bundle demo - Vesting appendix",
            "vesting appendix",
            "Appendix A vesting terms.",
        ),
    ],
    "CLAIM-2026-001": [
        (
            "Bundle demo - Claim cover letter",
            "claim cover letter",
            "Cover letter for a claim package.",
        ),
        (
            "Bundle demo - Repair estimate",
            "Repair estimate.pdf",
            "Repair estimate document.",
        ),
        (
            "Bundle demo - Photos inventory",
            "Photos inventory.pdf",
            "Inventory of submitted claim photos.",
        ),
    ],
}


def write_demo_pdf(document, body):
    document.source_path.parent.mkdir(parents=True, exist_ok=True)
    title = document.title.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    text = body.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 18 Tf 72 740 Td ({title}) Tj 0 -32 Td /F1 11 Tf ({text}) Tj ET"
    stream_bytes = stream.encode("ascii", errors="replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length "
        + str(len(stream_bytes)).encode("ascii")
        + b" >>\nstream\n"
        + stream_bytes
        + b"\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for object_id, payload in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{object_id} 0 obj\n".encode("ascii"))
        output.extend(payload)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer << /Root 1 0 R /Size {len(objects) + 1} >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii"),
    )
    document.source_path.write_bytes(output)


user, _ = User.objects.get_or_create(
    username=USER,
    defaults={
        "email": "bundleadmin@example.com",
        "is_staff": True,
        "is_superuser": True,
    },
)
user.email = "bundleadmin@example.com"
user.is_staff = True
user.is_superuser = True
user.set_password(PASSWORD)
user.save()

DocumentBundle.objects.filter(bundle_id__in=DEMO_BUNDLES.keys()).delete()
Document.objects.filter(title__startswith="Bundle demo - ").delete()

for bundle_id, entries in DEMO_BUNDLES.items():
    items = []
    for index, (title, item_name, content) in enumerate(entries, start=1):
        document = Document.objects.create(
            title=title,
            content=content,
            checksum=f"demo-{bundle_id.lower()}-{index}",
            mime_type="application/pdf",
            original_filename=item_name,
            owner=user,
        )
        write_demo_pdf(document, content)
        items.append(
            BundleItemInput(document=document, bundle_item_name=item_name),
        )
    create_bundle(items=items, bundle_id=bundle_id)

print(f"User: {USER} / {PASSWORD}")  # noqa: T201
print(f"Bundles: {', '.join(DEMO_BUNDLES)}")  # noqa: T201
