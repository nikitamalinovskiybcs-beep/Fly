"""Research-only parser for publicly rendered Leonteq product pages."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Callable

import requests
from bs4 import BeautifulSoup


@dataclass(frozen=True)
class LeonteqPublicRecord:
    isin: str | None
    title: str | None
    product_type: str | None
    issuer: str | None
    underlyings: tuple[str, ...]
    barrier_pct: float | None
    memory_effect: bool | None
    initial_fixing: str | None
    issue_date: str | None
    expiry: str | None
    bid: float | None
    ask: float | None
    source_url: str
    retrieved_at: str
    evidence_class: str = "public_product_page"
    outcome_status: str = "missing_verified_outcome"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _text(soup: BeautifulSoup) -> str:
    return " ".join(soup.get_text(" ", strip=True).split())


def _value(text: str, label: str, next_label: str) -> str | None:
    match = re.search(
        rf"{re.escape(label)}\s+(.+?)(?=\s+{re.escape(next_label)}\b|$)",
        text,
        flags=re.IGNORECASE,
    )
    return match.group(1).strip() if match else None


def _date_value(text: str, label: str) -> str | None:
    match = re.search(
        rf"{re.escape(label)}\s+(\d{{1,2}}\s+[A-Za-z]+\s+\d{{4}})",
        text,
        flags=re.IGNORECASE,
    )
    return match.group(1) if match else None


def _iso_date_value(text: str, label: str) -> str | None:
    match = re.search(
        rf"{re.escape(label)}\s+(\d{{4}}-\d{{2}}-\d{{2}})",
        text,
        flags=re.IGNORECASE,
    )
    return match.group(1) if match else None


def _number_value(text: str, label: str) -> float | None:
    match = re.search(
        rf"{re.escape(label)}\s+(?:EUR|CHF|USD)?\s*"
        rf"([0-9][0-9.,]*)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    raw = match.group(1).replace(" ", "")
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif raw.count(".") > 1:
        raw = raw.replace(".", "")
    try:
        return float(raw)
    except ValueError:
        return None


def parse_leonteq_public_page(
    html: str,
    source_url: str,
    retrieved_at: str | None = None,
) -> LeonteqPublicRecord:
    """Parse stable terms exposed in a public Leonteq product page."""

    soup = BeautifulSoup(html, "html.parser")
    text = _text(soup)
    isin_match = re.search(r"\b(?:CH|XS|IT|LU)\d{10}\b", text)
    barrier_match = re.search(r"Barrier\s*([0-9]+(?:[.,][0-9]+)?)%", text)
    memory_match = re.search(r"Memory effect\s+(Yes|No)", text, re.IGNORECASE)
    title = soup.title.get_text(" ", strip=True) if soup.title else None
    title_underlyings = ()
    if title:
        title_match = re.search(
            r"Express Certificate on (.+?)\s*\|\s*(?:CH|XS|IT|LU)\d{10}",
            title,
            flags=re.IGNORECASE,
        )
        if title_match:
            title_underlyings = tuple(
                item.strip() for item in title_match.group(1).split(",") if item.strip()
            )
    underlyings = tuple(
        dict.fromkeys(
            anchor.get_text(" ", strip=True)
            for anchor in soup.select('a[href*="/underlyings/"]')
            if anchor.get_text(" ", strip=True)
        )
    )
    underlyings = underlyings or title_underlyings
    retrieved = retrieved_at or datetime.now(timezone.utc).isoformat()
    issuer = _value(text, "Issuer", "Product type")
    if issuer:
        issuer = re.split(
            r"\s+(?:Currency|Issue date|Collateral agent|Settlement type)\b",
            issuer,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip()
    return LeonteqPublicRecord(
        isin=isin_match.group(0) if isin_match else None,
        title=title,
        product_type="Phoenix Autocallable" if "Phoenix Autocallable" in text else None,
        issuer=issuer,
        underlyings=underlyings,
        barrier_pct=float(barrier_match.group(1).replace(",", "."))
        if barrier_match
        else None,
        memory_effect=(
            memory_match.group(1).lower() == "yes" if memory_match else None
        ),
        initial_fixing=_date_value(text, "Initial fixing")
        or _iso_date_value(text, "Initial fixing"),
        issue_date=_date_value(text, "Issue date")
        or _iso_date_value(text, "Issue date"),
        expiry=_date_value(text, "Expiry") or _iso_date_value(text, "Expiry"),
        bid=_number_value(text, "Bid"),
        ask=_number_value(text, "Ask"),
        source_url=source_url,
        retrieved_at=retrieved,
    )


def fetch_leonteq_public_page(
    source_url: str,
    *,
    get: Callable[..., requests.Response] = requests.get,
    timeout_seconds: float = 30.0,
) -> LeonteqPublicRecord:
    """Fetch and parse one public page without fallback or provider substitution."""

    response = get(source_url, timeout=timeout_seconds)
    response.raise_for_status()
    return parse_leonteq_public_page(response.text, source_url)
