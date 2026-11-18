#!/usr/bin/env python3
"""Archive official Investor Relations evidence for AICS without PIT/score promotion.

Daily retrieval archives raw *current* IR pages by SHA-256 and watches official IR
landing pages for prospective new reports. This is NOT a historical webpage
archive, does NOT prove the original publication timestamp, and never emits
node stress scores, an AICS number, probability forecasts, or trading signals.

SEC-filed figures remain embargoed until filed_at + 14 calendar days and must
be independently checked against original filing bytes and accession metadata.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
from html.parser import HTMLParser
import json
import os
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urldefrag
from urllib.request import Request, urlopen

DEFAULT_REGISTRY = Path("aics_data/source_registry/ir_priority_insurers_spv_neoclouds_2026-11-18.json")
DEFAULT_OUTPUT = Path("aics_data/source_evidence/ir_priority")
HOSTS = frozenset({
    "www.metlife.com", "investor.metlife.com", "investor.prudential.com",
    "investors.coreweave.com", "nebius.com", "ir.applieddigital.com",
    "investor.equinix.com", "equinix.mediaroom.com"
})
CANDIDATE_NODES = frozenset({"Insurers", "SPV", "Neoclouds"})
MAX_BYTES = 8_000_000
DISCOVERY_PATTERN = re.compile(
    r"(quarter|financial|earning|results|investor|filing|facility|credit|financing|"
    r"debt|lease|joint venture|capital|2026)", re.IGNORECASE
)
IR_INDEX = {
    "MetLife": "https://investor.metlife.com/news/Financial-Press-Releases/default.aspx",
    "Prudential Financial": "https://investor.prudential.com/",
    "CoreWeave": "https://investors.coreweave.com/news/default.aspx",
    "Nebius Group": "https://nebius.com/investor-hub",
    "Applied Digital": "https://ir.applieddigital.com/news-events/press-releases",
    "Equinix": "https://investor.equinix.com/",
}


def check_url(url: str) -> bool:
    try:
        u = urlsplit(url)
        return (u.scheme == "https" and u.hostname in HOSTS
                and u.username is None and u.password is None
                and u.port in (None, 443) and not u.fragment)
    except (ValueError, TypeError):
        return False


def load_registry(path: Path, as_of: dt.date) -> dict:
    reg = json.loads(path.read_text(encoding="utf-8"))
    if reg.get("schema_version") != "aics-ir-primary-candidates-v1":
        raise ValueError("wrong IR registry version")
    entries = reg.get("source_entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("no source entries")
    unique_ids, unique_urls = set(), set()
    for e in entries:
        if (not isinstance(e, dict)
                or e.get("candidate_node") not in CANDIDATE_NODES
                or not isinstance(e.get("source_id"), str)
                or not re.fullmatch(r"[A-Z0-9_]{4,64}", e["source_id"])
                or e["source_id"] in unique_ids
                or e.get("url") in unique_urls
                or not check_url(e.get("url"))
                or e.get("certified_metrics") != []
                or e.get("disclosure_basis") != "issuer_release_not_sec_filing"):
            raise ValueError("invalid, duplicate, or promoted IR source")
        claimed = dt.date.fromisoformat(e["publication_date_claim"])
        if claimed > as_of:
            # Valid future-dated entries can be retained, but never fetched yet.
            pass
        if e.get("period_end") is not None:
            ended = dt.date.fromisoformat(e["period_end"])
            if ended > claimed:
                raise ValueError("period ended after declared publication")
        unique_ids.add(e["source_id"])
        unique_urls.add(e["url"])
    policy = reg.get("policy", {})
    if (not isinstance(policy, dict)
            or policy.get("never_auto_certify") is not True
            or policy.get("all_candidate_score_eligible") is not False
            or policy.get("index_aics") is not None
            or policy.get("predictive_skill_score") is not None):
        raise ValueError("unsafe registry certification policy")
    return reg


def retrieve(url: str, user_agent: str, opener=urlopen) -> tuple[bytes, str, str]:
    if not check_url(url):
        raise ValueError("source host not allowlisted")
    req = Request(url, headers={
        "User-Agent": user_agent or "AICS primary IR research collector",
        "Accept": "text/html,application/xhtml+xml",
    })
    with opener(req, timeout=35) as resp:
        final_url = resp.geturl()
        if not check_url(final_url):
            raise ValueError("unsafe primary-source redirect")
        ctype = resp.headers.get("Content-Type", "").lower()
        if "text/html" not in ctype and "application/xhtml+xml" not in ctype:
            raise ValueError("unexpected content type")
        raw = resp.read(MAX_BYTES + 1)
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError("empty or oversized source")
    if b"<html" not in raw[:8192].lower() and b"<!doctype html" not in raw[:8192].lower():
        raise ValueError("missing HTML structure")
    return raw, final_url, ctype


class AnchorExtractor(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.links: list[tuple[str, str]] = []
        self._href = None
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href:
            url, _fragment = urldefrag(urljoin(self.base_url, self._href))
            txt = " ".join("".join(self._text).split())
            if (check_url(url) and urlsplit(url).hostname == urlsplit(self.base_url).hostname
                    and txt and DISCOVERY_PATTERN.search(txt)):
                self.links.append((url, txt[:220]))
        if tag == "a":
            self._href = None
            self._text = []


def discover_links(body: bytes, base_url: str, limit: int = 20) -> list[dict]:
    parser = AnchorExtractor(base_url)
    parser.feed(body.decode("utf-8", errors="replace"))
    seen, found = set(), []
    for url, title in parser.links:
        if url in seen or url == base_url:
            continue
        seen.add(url)
        found.append({"url": url, "anchor_text": title,
                      "release_date_verified": False, "score_eligible": False,
                      "discovery_status": "REQUIRES_MANUAL_RELEASE_REVIEW"})
        if len(found) >= limit:
            break
    return found


def archive(outdir: Path, raw: bytes) -> tuple[str, str]:
    sha = hashlib.sha256(raw).hexdigest()
    raw_dir = outdir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / (sha + ".html")
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() != sha:
        raise ValueError("existing raw source tampered")
    if not path.exists():
        path.write_bytes(raw)
    return sha, str(path)


def run(registry: Path, output_dir: Path, as_of: dt.date,
        user_agent: str = "", opener=urlopen, landing_pages: dict | None = None) -> dict:
    info = load_registry(registry, as_of)
    output_dir.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    items = []
    for e in info["source_entries"]:
        entry = {
            "source_id": e["source_id"],
            "issuer": e["issuer"],
            "candidate_node": e["candidate_node"],
            "role": e["role"],
            "url": e["url"],
            "period_end": e["period_end"],
            "publication_date_claim": e["publication_date_claim"],
            "retrieved_at_utc": now,
            "status": "not_fetched",
            "historical_publication_date_independently_verified": False,
            "sec_available_at_verified": False,
            "pit_verified": False,
            "numeric_values_extracted": False,
            "score_eligible": False,
        }
        if dt.date.fromisoformat(e["publication_date_claim"]) > as_of:
            entry["status"] = "future_publication_excluded"
        else:
            try:
                raw, final_url, ctype = retrieve(e["url"], user_agent, opener=opener)
                sha, path = archive(output_dir, raw)
                entry.update(status="archived_current_ir_unverified", sha256=sha,
                             raw_path=path, bytes=len(raw), final_url=final_url,
                             content_type=ctype)
            except Exception as exc:
                entry.update(status="fetch_failed", error=type(exc).__name__)
        items.append(entry)

    watches = []
    for issuer, url in (landing_pages if landing_pages is not None else IR_INDEX).items():
        entry = {"issuer": issuer, "url": url, "retrieved_at_utc": now,
                 "status": "not_fetched", "new_report_date_proven": False,
                 "score_eligible": False, "discovered_links": []}
        try:
            raw, final_url, ctype = retrieve(url, user_agent, opener=opener)
            sha, path = archive(output_dir, raw)
            entry.update(status="index_archived_unverified", sha256=sha, raw_path=path,
                         bytes=len(raw), final_url=final_url, content_type=ctype,
                         discovered_links=discover_links(raw, final_url))
        except Exception as exc:
            entry.update(status="fetch_failed", error=type(exc).__name__)
        watches.append(entry)
    manifest = {
        "schema_version": "aics-ir-capture-v1",
        "as_of": as_of.isoformat(),
        "retrieved_at_utc": now,
        "registry_sha256": hashlib.sha256(registry.read_bytes()).hexdigest(),
        "candidate_count": len(items),
        "archived_candidates": sum(i["status"] == "archived_current_ir_unverified" for i in items),
        "landing_pages_checked": len(watches),
        "landing_pages_archived": sum(w["status"] == "index_archived_unverified" for w in watches),
        "candidates": items, "landing_pages": watches,
        "all_reports_historically_pit_verified": False,
        "independently_certified_nodes": 0,
        "node_scores": {"Insurers": None, "Neoclouds": None, "SPV": None},
        "index_aics": None, "predictive_skill_score": None,
        "promotion": "BLOCKED", "trades_created": False,
        "limits": [
            "Live landing-page links are discovery leads, not authenticated dated releases.",
            "IR publication_date_claim is unverified as original historical timestamp.",
            "SEC-derived data require filed_at + 14 calendar days on original filing.",
            "Equinix reports and Nebius loan are financing/SPV proxies only.",
            "No source is promoted into scores without an independent PIT audit."
        ],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    return manifest


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    p.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--as-of", type=dt.date.fromisoformat,
                   default=dt.datetime.now(dt.timezone.utc).date())
    args = p.parse_args()
    data = run(args.registry, args.out, args.as_of, os.getenv("AICS_IR_USER_AGENT", ""))
    print(json.dumps({
        "archived_candidates": data["archived_candidates"],
        "total_candidates": data["candidate_count"],
        "landing_pages_archived": data["landing_pages_archived"],
        "index_aics": None, "promotion": "BLOCKED"
    }))
    return 0 if (data["archived_candidates"] > 0 or data["landing_pages_archived"] > 0) else 2


if __name__ == "__main__":
    raise SystemExit(main())
