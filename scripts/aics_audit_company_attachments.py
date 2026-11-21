"""Reconcile private source attachments with each company in the frozen AICS roster."""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from zipfile import ZipFile

from scripts.aics_reconcile_company_universe import (
    OMI,
    PDF_SHA256,
    REGISTRY,
    TELEGRAM_CLAIMS,
    telegram_membership,
)

PRINTED_NAMES = {"JPMorgan Chase": "JP Morgan Chase", "Nebius Group": "Nebius"}
RECEIPT = Path("aics_data/research/company_attachment_review_2026-11-19.json")


def normalized(text):
    return " " + re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip() + " "


def pdf_pages(raw):
    if hashlib.sha256(raw).hexdigest() != PDF_SHA256:
        raise ValueError("Wrong edition of the OMI PDF")
    result = subprocess.run(
        ["pdftotext", "-raw", "-enc", "UTF-8", "-", "-"], input=raw,
        capture_output=True, check=True,
    )
    pages = result.stdout.decode().split("\f")
    if len(pages) != 89 or pages[-1].strip():
        raise ValueError("Expected exactly 88 physical PDF pages")
    return [normalized(page) for page in pages[:-1]]


def check_screenshots(archive, claims):
    expected = {row["filename"]: row["sha256"] for row in claims["telegram_source"]["images"]}
    if len(expected) != 11:
        raise ValueError("Expected 11 distinct registered screenshots")
    with ZipFile(archive) as bundle:
        members = [name for name in bundle.namelist() if name.lower().endswith(".jpg")]
        if sorted(members) != sorted("telegram_originals/" + name for name in expected):
            raise ValueError("Telegram archive member inventory differs from the registered images")
        manifest = json.loads(bundle.read("SHA256_evidence_manifest.json"))["images"]
        if len(manifest) != len(expected) or {row["name"] for row in manifest} != set(expected):
            raise ValueError("Telegram manifest has missing or repeated entries")
        for row in manifest:
            name = row["name"]
            data = bundle.read("telegram_originals/" + name)
            if (len(data) != row["bytes"]
                    or not hashlib.sha256(data).hexdigest() == row["sha256"] == expected[name]):
                raise ValueError("Screenshot hash or size mismatch: " + name)
    return expected


def audit(pdf, archive):
    registry = json.loads(REGISTRY.read_text())
    claims = json.loads(TELEGRAM_CLAIMS.read_text())
    pages = pdf_pages(pdf.read_bytes())
    images = check_screenshots(archive, claims)
    rows = []
    mentions = 0
    for issuer in registry["companies"]:
        name = issuer["name"]
        if issuer["origin"] == OMI:
            printed = PRINTED_NAMES.get(name, name)
            refs = issuer["original_pdf_pages"]
            if not refs or not all(1 <= page <= len(pages) and normalized(printed) in pages[page - 1] for page in refs):
                raise ValueError("A cited PDF page does not contain the expected issuer: " + name)
            rows.append({"name": name, "printed_name": printed, "physical_pdf_pages": refs})
            mentions += len(refs)
        else:
            refs = issuer["telegram_image_ids"]
            if not refs or any(ref not in images for ref in refs):
                raise ValueError("Missing registered screenshot for " + name)
            rows.append({"name": name, "registered_transcription_images": refs})
    return {
        "review_date": "2026-11-19", "pdf_sha256": PDF_SHA256, "pdf_pages": len(pages),
        "telegram_zip_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "screenshot_hashes_matched_to_registry_and_zip_manifest": len(images),
        "omi_company_page_references_matched": mentions, "companies": rows,
        "telegram_scope": telegram_membership(registry["companies"], claims),
        "scope": "PDF name occurrences and bytes behind the existing visual Telegram transcription",
        "contractual_exposures_verified_by_attachments": False, "index_aics": None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--telegram-zip", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=RECEIPT)
    args = parser.parse_args()
    result = audit(args.pdf, args.telegram_zip)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(result['companies'])} issuers, {result['omi_company_page_references_matched']} OMI page references, "
          f"{result['screenshot_hashes_matched_to_registry_and_zip_manifest']} Telegram image hashes")


if __name__ == "__main__":
    main()
