# AICS Private Credit — 3 original SEC issuer disclosures, 18 verified values

**As of:** 2026-11-19. **Node:** Private Credit, fixed weight **150 of 1050**. **Model use:** Research only, `index_aics=null`, `promotion=BLOCKED`.

## Evidence executed and independently checked

- **ARCC:** 5 reporting-period entries, 10 percentage observations (cost and fair-value) from original 2025Q4–2026Q3 SEC disclosures, including 2024Q4 comparison only first released in 2026. See `aics_data/research/arcc_q4_sec_corrected_nonaccrual_sources_2026-11-18.json`.
- **OBDC:** 3 reporting quarters, 6 percentages from three original SEC Form 8-K / EX-99.1 pairs and their index pages; six HTML originals independently hashed. Original ZIP SHA-256 `3af6fc515102edefe4e533f431b87bc87c25b87d6565616ace3fcc2ca07141e8`. See `aics_data/research/obdc_original_nonaccrual_source_receipt_2026-11-19.json`.
- **BXSL:** 2026Q3 SEC 8-K, original filing index and EX-99.1 with explanatory footnote, 2 percentages. **2.8% non-accrual at amortized cost; 2.1% at fair market value.** Three HTML originals rehashed; original ZIP SHA-256 `d34ba8b21eac65f8ba83d23ddd9572ba6d6ac8227a5415b6b90e7f3dcc924950`. See `aics_data/research/bxsl_original_nonaccrual_source_receipt_2026-11-19.json`.

**Verified aggregate source inventory:** 3 issuers × varying available quarters = **9 issuer-period entries**, **18 separately disclosed numeric measures**. They are not 18 independent months or observations of a sector index.

[Three-issuer source archive rehash and numeric comparison — passed 7 tests](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44417102811). Original result artifact `14479124178`; four independent SEC original ZIP rehashes successful.

## Latest comparable quarter — Q3 2026

| Issuer | Non-accrual as % of amortized cost | Non-accrual as % of fair value | SEC filed | AICS candidate available_at |
|---|---:|---:|---|---|
| ARCC | 2.4% | 1.4% | 2026-10-27 | 2026-11-10 |
| OBDC | 2.9% | 0.8% | 2026-11-04 | 2026-11-18 |
| BXSL | 2.8% | 2.1% | 2026-11-04 | 2026-11-18 |

Reported denominators and portfolios differ among issuers and between cost/fair metrics. **No issuer-averaged rate, portfolio weight, 0–100 score or hot-node count** was created.

## PIT and remaining blockers

- Exact **SEC +14 calendar days** applies to the original filing date. BXSL Q3 and OBDC Q3 could not be admitted to an AICS November 17 evaluation; **November 18** is the first eligible candidate date.
- ARCC 2024-12-31 source comparative appeared in its SEC February 2026 release. Its number is *not* a 2024 publication and must not be backdated.
- Original filings are independently hashed by source bytes, but their current archive retrieval does not independently attest the first historical live publication timestamp or an untouched OOS experiment.
- Listed BDCs are a limited proxy for parts of private credit. Private AI-credit or SPV exposure coverage, reinsurance, issuer universe, consistent denominator definitions, default rates and vintages are not established.
- **Technical AICS milestone count stays 22/66 = 33.3%, PIT-certified 0/11, index AICS unavailable.** A 24-month genuine untouched predictive holdout and approved stress-score methodology must precede certification.

**Follow-on:** Acquire additional named private-credit BDC issuer original SEC filing periods and unambiguous first-publication histories; predefine eligible issuer universe, normalize cost vs fair exposures, then obtain independent source-to-score and OOS review. No synthetic backfill.
