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
