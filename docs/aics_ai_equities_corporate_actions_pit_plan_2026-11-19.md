# AICS AI Equities — evidence gate for corporate actions and historical membership

**Research only.** The seven Nasdaq historical quote JSON responses (441 rows) are original-byte checked but are retrospectively served data, not historical market vintages. They do not establish when splits, dividends, corporate name/ticker changes, delistings, or membership were known.

## Required primary-source coverage

For each of NVDA, MSFT, GOOGL, AMZN, META, ORCL, MU the new gap audit requests three independently attributable facets: (1) corporate action history, including **explicit proof of absence** where a time window contains no actions; (2) security identity and ticker change history; (3) historical membership in the research basket or benchmark, with effective timestamps. Seven securities × three facets = 21 provenance slots, **not** 21 PIT certifications.

Source leads (do not imply data access):

- Official Nasdaq corporate action descriptions: https://www.nasdaq.com/products/data/equities/corporate-action-solutions
- Nasdaq Daily List format: https://nasdaqtrader.com/content/technicalSupport/specifications/dataproducts/dlcompletespec.pdf
- SEC EDGAR issuer disclosures, with **available_at = filed_at + 14 calendar days**: https://www.sec.gov/edgar/search/

No licensed Nasdaq historical actions, historical composition roster, contemporaneous provider release attestations, or redistribution permission is documented in this repository. Current retroactive quote history cannot substitute for any of them.

## Implementation

`scripts/aics_audit_ai_equities_action_pit.py` reads the immutable registry `aics_data/source_registry/ai_equities_action_pit_registry_2026-11-19.json`. Empty `original_evidence_records` means **missing**, never an implicit zero events assertion. Later legally obtained raw documents must have local original bytes, matching SHA-256, source URL, economic coverage dates, publication and capture timestamps, and SEC embargo dates where applicable.

Even when local originals are rehashed, they remain **local sources only, NOT independently historical PIT**. The audit never calculates adjusted prices, an AICS node score, the total index, or predictive skill. Unit tests cover malformed chronology, source tampering, missing roster, duplicate records, SEC +14 days, and forged certifications.

AICS status stays 22/66 milestones (33.3%), AI Equities 2/6, independent certifications 0/11, index N/A, OOS not validated. This audit adds a verified diagnostic, not a new milestone.

## SEC issuer identity anti-mislabel gate (19 November 2026)

The source intake now cross-checks an SEC archived filing URL’s numerical CIK directory against the independently maintained seven-issuer CIK roster used by `scripts/aics_collect_public_chain_sec_filings.py`. A rehashed Microsoft SEC original cannot satisfy an NVIDIA corporate-action source slot merely because its URL and SHA-256 are valid. The accession directory must have the canonical 18-digit form; an impossible publication-before-filing chronology is also rejected. Focused synthetic-only regression cases cover a matching-issuer archived original, a different-issuer source, a malformed accession, and a release-before-filing claim.

This controls *issuer provenance of locally archived originals*, not the historical absence of corporate actions or legally permitted PIT. No new source evidence or model score was added; the 21 historical facets still need independent attestation, all seven research equities remain 2/6, AICS remains 22/66 (33.3%), and certification remains 0/11.

## Two NVIDIA SEC original split filings independently rehashed (19 November 2026)

A separate evidence-only collector, `scripts/aics_collect_nvda_split_sec_originals.py`, now re-downloads the **complete original 8-K submissions** for NVIDIA's May 22 2024 split announcement and June 7 2024 legal effectuation. It checks original issuer CIK `1045810`, exact accession/form/filed date/primary document identity, embedded split event text and original SHA-256. The May filing documents the *prospective* 10:1 split; the June filing confirms it became effective June 7, 2024 at 16:01 Eastern Time. The first expected trading session on the new basis was June 10.

| Source | Full SEC original bytes | SHA-256 | Strict AICS SEC+14 availability |
|---|---:|---|---|
| [May 22 8-K, 0001045810-24-000113](https://www.sec.gov/Archives/edgar/data/1045810/000104581024000113/nvda-20240522.htm) | 664,599 | `573766d04062164181061703da05e0c4e5984fedf190c68222f23f6487a44a8d` | **2024-06-05** |
| [June 7 8-K, 0001045810-24-000144](https://www.sec.gov/Archives/edgar/data/1045810/000104581024000144/nvda-20240607.htm) | 166,014 | `249aae37369da9451cc512733ffd65202e8d675cea56dc5e12ad2edf1c7fd010` | **2024-06-21** |

The [source-capture GitHub workflow](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44496137457) passed, and original artifact **14515686627** was separately downloaded into a container and independently SHA-256 verified including ZIP CRC; ZIP digest `ae2f0a0acde34886e5f43c8d8bc472ecf0c0f1b1ca672f9132524fdb3d37cd1c`. Permanent non-promotional [receipt](../aics_data/research/nvda_2024_split_two_sec_originals_rehash_2026-11-19.json). CI also passes after pinning **both** original source hashes and anti-fabrication tests.

**Evidence boundary:** This is **one issuer-specific paired split event**, not a historical action calendar for all 7 names. The 21 required historical facet slots in the unmodified primary action PIT registry have not been independently completed; no retroactive Nasdaq price adjustment, historical basket return, silent "no action" claim, model score or milestone is created. The conservative SEC+14 rule distinguishes the announcement's **June 5** eligibility from the separate effectuation filing's **June 21** eligibility. These two dates must never be silently merged or backdated.
