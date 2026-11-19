# AICS — бесшовная передача в ChatGPT Work / GPT-6.2 Astra

**Создано:** 2026-11-18. **Назначение:** стартовый контекст нового Work-сеанса, чтобы продолжать работу в проекте *Aucs* без повторной постановки задачи.

> **READ THIS FIRST.** Treat this as a handoff, not proof of market observations. Inspect live repository files and check that the branch and latest actions have not changed. Never hallucinate historical data, scores or certifications.

## 1. Главная цель

AICS — *AI Chain Stress*: 11-узловой финансовый индикатор распространения риска в AI-инфраструктуре. Подготовка материалов Инвестиционному комитету **30 ноября 2026 года**. Пользователь хочет автономное поочерёдное продвижение всех узлов, максимум реальных первичных источников, реплицируемую аналитику, GitHub commits и **видимую шкалу 0–100%**. Не требуй повторных согласований на обычные read/write/test шаги; для рискованных/необратимых действий и секретов следуй разрешениям среды.

**GitHub:** [nikitamalinovskiybcs-beep/Fly](https://github.com/nikitamalinovskiybcs-beep/Fly), branch `devin/1779618014-quant-risk-framework`. Это источник истины для кода, реестров и истории GitHub Actions. Выбирать и открыть именно эту ветку, не пушить случайно в default и не переписывать историю без разрешения.

## 2. Константы, которые нельзя менять

| Node | Weight |
|---|---:|
| Private Credit | 150 |
| Insurers | 125 |
| UST 30Y | 125 |
| Neoclouds | 100 |
| AI Equities | 100 |
| Hyperscalers | 100 |
| SPV | 100 |
| Repo | 100 |
| Power/Data Centers | 50 |
| Semiconductors Supply | 50 |
| AI Demand | 50 |
| **Total** | **1050** |

Each node score on 0–100. `H=count(node_score>60)`.
`M=clip(1+0.20*clip(H-2,0,1)+0.05*max(0,H-3),1,1.35)`.
`raw=sum(weight*score/100)`; `AICS=raw*M`.
Internal research thresholds `<450` entry, `450–500` watch, `>500` exit-to-cash; **NEVER act on such signals when uncertified**.

- No invented observations, synthetic historical backfill, future leakage, or score values.
- `SEC.available_at = filed_at + 14 calendar days`, strictly. IR release dates alone do not certify SEC PIT.
- Revised FRED series must use dated ALFRED vintages; current companyfacts and lookback alone do not prove original vintages.
- Strict source trail: original raw document, SHA-256, as-of/period end, publication/filing and available_at, issuer identity, factual units.
- Do not add values across current receivables, conditional guarantees, undrawn commitments, lease liabilities and market-value equity (stocks/flows overlap).
- At least 24 months of genuinely untouched OOS and independently reviewed source-to-score mapping before certification.
- No fake accuracy/skill score. Distinguish *research indicator* from node stress score.

## 3. Verifiable project state AS OF 2026-11-18

- `aics_data/progress/status.json`: **22 / 66 milestones = 33.3% technical workflow progress**, **0 / 11 independently certified**, `index_aics=null`.
- `docs/aics_progress.md`: human-readable bar and 11-node rows; `aics_data/progress/evidence_milestones_2026-11-18.json`: source-linked ledger.
- Raw candidate evidence stage (2/6) documented for **11 of 11** nodes; **AI Equities** now has seven independently rehashed Nasdaq JSON originals (441 genuine rows, current 2026-11-18 capture), which do NOT establish historical PIT, historical membership, source license or audited scores.
- No node has separately proven independently verified historic PIT, validated 0–100 stress score, untouched 24-month OOS, and certification.
- Archived ALFRED monthly research snapshots: DGS30, SOFR, BAMLH0A0HYM2, BAMLH0A3HYC (4 × 24 monthly). Authentic provider vintage attestation remains open.
- True current-period IR originals were downloaded to GitHub Actions artifacts and SHA-256 rechecked. **Artifacts expire after 30 days**; permanently preserve legally permitted raw source bytes and repeat source audits. Files named `aics_data/progress/*receipt*.json` pin source SHA evidence; receipt != historical PIT.

Read direct files and latest GitHub Actions job logs on every session; the above counts are a dated snapshot, not a promise of what is currently passing.

## 4. Key working code and registries

- `scripts/aics_progress_dashboard.py` + `tests/test_aics_progress_dashboard.py`: fail-closed technical progress, six steps × 11 nodes.
- `scripts/aics_collect_insurers_sec.py` + `scripts/aics_verify_insurers_sec_evidence.py`: MET and PRU SEC companyfacts/submissions with `filings.files` appendices; candidate accounting XBRL, NOT primary-model stress score.
- `scripts/aics_collect_spv_neocloud_sec.py`: date-controlled SEC originals; CRWV 2026 Q3 10-Q filed 2026-11-12 **excluded until 2026-11-26**.
- `scripts/aics_collect_priority_ir.py` and `.github/workflows/aics-research-safety.yml`: official IR originals for multiple issuers and source hash receipts.
- `docs/aics_11_node_primary_source_registry_2026-11-18.md`: 11-node source plan.
- `aics_data/research/coreweave_q3_ir_interest_burden_2026-11-18.json`: research-only current-quarter 846 / 3661 = ~23.1% interest-to-revenue, NOT interest coverage, not AICS score.
- `aics_data/research/nebius_sec_6k_credit_facility_2026_10_22.json`: $3.5bn contractual facility, does not prove drawn amount or true SPV classification.
- `docs/aics_omi_brace_impact_2026_11_18_evidence_review.md`: OMI/AFREF 88-page October 2026 policy study, no direct source-to-score certification.
- `docs/aics_telegram_spydell_nvidia_financing_audit_2026-11-18.md`: 11 Telegram JPG screenshots, NVIDIA SEC 10-Q cross-check. Source images ZIP was shared in prior chat, NOT stored in GitHub.
- `aics_data/research/spydell_telegram_nvidia_circular_financing_claims_2026-11-18.json`: 23 entities, 28 claims, 12 possible counterparty edges, with verification statuses; some amounts were confirmed in NVIDIA SEC, other deal details are Telegram-only, NOT validated scores.
- `aics_data/research/aics_extended_company_universe_omi_telegram_2026-11-18.json`: **37 research-universe companies (26 OMI names + 11 unique Telegram-only entities)** mapped to existing nodes; project-specific finance/legal contracts remain largely unverified.
- `tests/test_aics_extended_company_universe.py`: prevent source-name discovery from automatically promoting market evidence.
- `tests/test_aics_telegram_spydell_claim_intake.py`: no double-counting, SEC vs Telegram labels.
- `scripts/aics_reconcile_company_universe.py` + `tests/test_aics_reconcile_company_universe.py`: 37-company / 3-project fail-closed secondary-source audit; `.github/workflows/aics-research-safety.yml` now runs it with the extended-universe tests. Passing run `44388937687`; **zero** new PIT milestones or scores.
- `docs/aics_37_company_reconciliation_2026-11-18.md`: committee-ready node candidate counts, exact provenance split and missing original-contract gates.
- **SEC primary source repair, verified in live GitHub Actions**: `AICS_SEC_USER_AGENT || EDGAR_IDENTITY` fallback in Neocloud/SPV and Insurers workflows; `python -m scripts.aics_verify_insurers_sec_evidence` fixes verifier import. Runs `44389973635` (4/4 eligible SEC HTML archived, CoreWeave 2026-11-12 10-Q still excluded until 2026-11-26) and `44390127352` (2/2 MET/PRU issuer sources, 6 SEC JSON originals, 2 history pages, 521 candidate XBRL rows, local SHA checks successful). No independent historical SEC companyfacts vintage or SPV contract certification. 
- `aics_data/research/sec_primary_archive_independent_rehash_2026_11_18.json`, `scripts/aics_validate_sec_rehash_receipt.py`, `tests/test_aics_validate_sec_rehash_receipt.py`, `docs/aics_sec_primary_rehash_and_asset_mix_2026_11_18.md`: independently rehashed temporary Actions ZIPs outside CI and pinned hashes; MET (2026Q2) AFS debt securities/GAAP assets 42.4276% and PRU (2026Q3) 41.8031% are different-period research composition metrics, NOT AI exposure or stress scores. Receipt validator is metadata-only and explicitly does not redo artifact bytes. 
- `aics_data/research/alfred_macro_archive_rehash_2026_11_18.json`, `scripts/aics_validate_alfred_macro_rehash.py`, `tests/test_aics_validate_alfred_macro_rehash.py`, `docs/aics_macro_alfred_rehash_2026_11_18.md`: independent rehash of existing 4 ALFRED CSV snapshots (96 month-ends, 165,913 rows). Public-domain candidate as-of observations DGS30 5.59% -> 5.32% (-27 bp), SOFR 3.88% -> 3.94% (+6 bp) from Sep to Oct 2026 month-end as-of snapshots. ICE BofA series retained as hashes/counts only due license restrictions. All provider PIT attestation and AICS scores blocked.
- `aics_data/research/omi_brace_impact_original_pdf_sha_receipt_2026-11-18.json`: exact original user's OMI PDF SHA-256 `466b8a875752c85e23a41d5e33ad985c44f437ddc5cf801e132310c4e28bff60`. Partner-hosted copy is not byte-identical.
- `aics_data/source_registry/*`: official IR and SEC documents; sources might be current-only, not as-of historical.

## 4b. Current unresolved gates / CI scope

- Archive rehashes prove local source-bundle integrity but not original historical provider-release dates, current companyfacts revision history, executed project recourse, or investment-grade model skill.
- Several raw-source ZIP artifacts expire on **2026-12-18**. Secure legally permitted long-term retention before expiration; licensed ICE top-level data are not approved for public republication.
- AICS research safety tests, invariant tests, ALFRED metadata gate and SEC source workflows have passed after the targeted fixes; **Phoenix CI still fails on broad repository Ruff lint** (pre-existing unrelated codebase violations). Never report the whole repository's CI green.
- `aics_data/progress/status.json` stays **22/66 = 33.3% technical**, **0/11 certified**, `index_aics=null`. Do not increase for successfully fetched candidates or for receipt-guard tests.

## Follow-up on 19 November 2026

The [results across all 11 nodes as of 18 November](aics_results_as_of_2026-11-18.md) reconcile CoreWeave and Nebius financing to cash balances, distinguish disclosed customer payments from equity financing, and include the balances and parent guarantees of two CoreWeave borrowing subsidiaries. The same report gives the volatility of 30-year Treasury yield changes at 24 month ends using dated ALFRED observations checked against the Treasury calendar.

The [eleven-node source review](aics_observed_nodes_2026-11-19.md) reproduces dated issuer, Federal Reserve and macro observations and reconciles the Telegram transcript to the 37-name roster. The Nscale executed agreement identifies a specific SPV borrower, affiliate guarantor and contractual ceiling. Independent PIT, audited scoring and the 24-month OOS remain open for all eleven nodes.

## 19 November 2026 — Insurers raw-source replay checkpoint

- Insurers SEC integrity audit now re-extracts the research CSV from locally archived, SHA-256-checked SEC companyfacts, submissions and historical submission appendices with the original +14 calendar-day cutoff and original filing/accession metadata.
- A modified value or primary-document URL, even when an attacker recomputes the CSV hash and edits its manifest, fails the exact row replay. Added negative tests for both manipulations.
- Verified GitHub Actions at commit `f126a91f0050710486185c821af0547caac1913a`: [Insurers MET/PRU SEC source workflow](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44470456047) and [AICS research safety suite](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44470456021) both **success**.
- This is a local archival source-to-CSV consistency check, not an independent historical release-time archive or Level 3/private-credit exposure validation. Therefore **22/66 technical milestones, 0/11 PIT attested, 0/11 certified, index AICS null** remain unchanged.
- Further work: verify historical delivery/published-at with independent provenance and non-overlapping sector metrics before any Insurers node score.

## 19 November 2026 — Nscale two-SPV executed contract evidence

- Added an actual second executed Nscale credit agreement: **Ward County EX-10.23** (`0001193125-26-395475`) distinct from existing **North Carolina EX-10.24**. Ward: `Nscale Ward County Borrower SPV, LLC` borrower, `Nscale Ward County, LLC` affiliate guarantor; fixed delayed-draw commitments **$630m**, floating **$1.22bn**, overall ceiling **$1.85bn**; SEC +14 eligibility **2026-10-02**. Nscale Limited **limited** parent guarantees are mentioned, not monetary parent recourse.
- North Carolina separately limits $370m + $830m = **$1.2bn**. **$3.05bn is sum of two distinct facility ceilings only**, not drawn debt, guarantees or model exposure.
- New `scripts/aics_collect_nscale_ward_sec.py`, `tests/test_aics_collect_nscale_ward_sec.py` and `.github/workflows/aics-nscale-ward-original-sec.yml` enforce exact original SEC URLs, date cutoff, source wording, document contents, proper UTC retrieval timestamps, no numeric risk-model promotion, raw source SHA-256 and explicit no-PIT.
- GitHub successful actual original capture [run 44472197069](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44472197069), artifact 14505066061; the ZIP and both SEC HTML documents were independently rehashed **outside CI** in the working container. Durable SHA receipt `aics_data/research/nscale_ward_original_sec_independent_rehash_2026-11-19.json`; rehashed ZIP SHA-256 `784af25b39401b95700a91f0ac0047a2548f950e6d07b043ff07abbc1b5954b2`. Later code and [tests](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44472421043) and [capture](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44472420986) passed.
- The raw-source rehash is not independent historic provider release attestation. Original bytes still live in short-lived Actions artifacts. **22/66 technical milestones, 0/11 historic PIT attestation, 0/11 certified, `index_aics=null`** remain. Next: obtain original dated draw records and enforceable parent guarantee limits, and only after independent release-time PIT consider stage 3.

## 19 November 2026 — original Nscale Dell Financial Services obligations replay

- Existing rehashed S-1 original `ck0002110365-20260918.htm` proves DFS equipment lease financing for **the same two SPV borrowers** (Ward County and North Carolina), with **Nscale Global Holdings Ltd** as corporate guarantor on 18 April 2026. This guarantor is legally distinct from Nscale Limited's limited support under the Ward GPU credit agreement.
- As of **2026-09-04**, the original S-1 disclosed **40 fully executed payment schedules**, **approximate $2.54bn aggregate initial-term rent INCLUDING approx $34.8m financing charges**. These are distinct from the two GPU loan facility ceilings ($1.85bn and $1.2bn). **NEVER ADD the $2.54bn DFS initial-term rent to $3.05bn GPU lender commitments**. Drawn GPU principal, outstanding lease liability, amounts paid, and parent guarantee enforceability amount remain **null**.
- New evidence-only parser `scripts/aics_audit_nscale_dfs_s1.py`, negative tests `tests/test_aics_audit_nscale_dfs_s1.py`, and Nscale live SEC original workflow step. Successful [real-source CI](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44475562317), artifact 14505823806. ZIP and both original HTML rehashed independently outside Actions, permanent SHA and manifest `aics_data/research/nscale_dfs_s1_source_replay_rehash_2026-11-19.json`.
- We have additionally verified one original S-1 contains the 40 schedules and the DFS guaranty but the source was **retrieved retrospectively in November**; it does NOT establish independently archived September feed delivery. Certified PIT/OOS and the AICS score remain **BLOCKED**. Technical milestone count remains **22/66**.
- Next meaningful work: obtain actual facility draws (exact legal borrower, as-of date, source document) and documentary guarantee recourse limits; do not derive debt balance from signed ceilings or future lease rents.

## 19 November 2026 — Nscale S-1 actual historical drawn-debt discoveries

- Replayed the exact previously SHA-rehashed September 18 2026 SEC Nscale S-1. **Important advancement:** unlike the Ward/NC ceilings-only discoveries, this document reports historical *actual* borrowing for other legal borrowers:
  - `Nscale Services UK Ltd`, its *separate GPU Financing Facility*: **about $58.9m term loans drawn and outstanding as of March 31 2026**; about $1.4bn delayed-draw commitments still available. Do not assign either amount to Ward County or North Carolina.
  - `Nscale Global Holdings Limited`, *Macquarie Senior Facility*: **$70.1m drawn August 1 2025**, **$34.9m drawn January 30 2026**; **$105m historical utilizations**, NOT current outstanding balance; the facility includes a loan and LC component.
  - **Nscale consolidated debt carrying value $137.4m as of June 30 2026**. This is a distinct balance-sheet measure, **not** incremental to either historical utilization or to the DFS rental schedules.
- ALL three observations first pass AICS SEC `filed_at + 14 calendar days` on **2026-10-02**. Historical observation dates are NEVER source publication timestamps or grounds for backdating. Ward and NC *actual drawings* remain unknown/null. Do not add the three amounts, $3.05bn Ward+NC ceilings, or $2.54bn DFS rent.
- New reproducible `scripts/aics_audit_nscale_drawn_debt_s1.py` + `tests/test_aics_audit_nscale_drawn_debt_s1.py`, source-linked GitHub original SEC capture [successful run 44477086023](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44477086023). Original ZIP artifact **14506871907** was downloaded and independently SHA-rehashed outside Actions: ZIP **`eb51c5549d21624e27e634fc081167fa256b0506a05c3585fd66666c7371739f`**, replay JSON SHA256 **`3d1bd7c373017c86b58129d008b748fa66a209a8ec1b329f042b50bfe42a6c14`**. Detailed durable digest `aics_data/research/nscale_s1_historical_draws_original_rehash_2026-11-19.json`.
- No independent archived original release-time PIT, current Ward/NC drawings, enforceable parent guarantee amounts or untouched OOS. **22/66 technical milestones; 0/11 independently attested PIT/certified nodes; `index_aics=null`** remain. Next useful source research: date-specific drawdown schedules, principal repayments, legal-entity recourse for Ward/NC; otherwise proceed to Neoclouds/AI Equities historical PIT.

## 19 November 2026 — AI Equities real 2024 NVDA split event pair + seven current listings

- `scripts/aics_collect_nvda_split_sec_originals.py` + offline negative tests + `.github/workflows/aics-nvda-two-split-sec-originals.yml` downloaded **both genuine, complete original SEC NVIDIA 8-K submissions**. First announcement **2024-05-22** (`0001045810-24-000113`), AICS SEC+14 eligible **2024-06-05**; legal effectuation filing **2024-06-07** (`0001045810-24-000144`), separately eligible **2024-06-21**. 10:1 split; expected first split-basis trading on June 10. Do not backdate June 7 document or treat announcements, legal events, and market data as interchangeable.
- [Original SEC CI run 44496137457](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44496137457) success; Actions artifact **14515686627**, separately downloaded into a working container. Both raw full submissions checked *outside CI* against manifest SHA-256: May **`573766d04062164181061703da05e0c4e5984fedf190c68222f23f6487a44a8d`** (664,599 bytes); June **`249aae37369da9451cc512733ffd65202e8d675cea56dc5e12ad2edf1c7fd010`** (166,014 bytes). ZIP digest **`ae2f0a0acde34886e5f43c8d8bc472ecf0c0f1b1ca672f9132524fdb3d37cd1c`**. The exact source hashes are pinned in the collector; durable metadata `aics_data/research/nvda_2024_split_two_sec_originals_rehash_2026-11-19.json`.
- Established independent prospective listing intake with `.github/workflows/aics-ai-equities-prospective-directory.yml` on the existing `scripts/aics_collect_ai_equities_symbol_directory.py`. [Successful real capture 44496860842](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44496860842) observed seven research securities in two current Nasdaq Trader text directories on **2026-11-19T09:29:24Z**: NVDA, MSFT, GOOGL, AMZN, META, MU in `nasdaqlisted.txt`; ORCL in `otherlisted.txt` (source market code N). Both original raw bytes independently rehashed outside CI from artifact **14516045430**; digest `nasdaqlisted` **`5cda84ca84660408ecfcda5af7e8f8e8c5a519e754f33ad5a96d17f86e708b83`** (348,385 bytes), `otherlisted` **`3cc52144bcd516be7dad8b668d91b84ff6b56751d5fdf78d74c6e08284d69234`** (544,575 bytes), ZIP **`4df22b44e845a036801ad36702e86b90f0e6e7233533c4f80a5732850dae5a55`**. Durable metadata `aics_data/research/ai_equities_2026_11_19_nasdaq_current_directory_rehash.json`.
- **No historical PIT closure:** Original complete NVDA 8-K pair is one issuer-specific event, **not** historical corporate-action completeness. Two current exchange directories are only a **present snapshot**, not 2024-2026 security identity and benchmark membership. Venue file-creation wall-clock has no independently attested timezone, historic Nasdaq price-response vintages and license still missing. Do NOT create historical price corrections or synthetic series. 21 historical source facets remain unfilled in the separate immutable registry; **22/66 stages, 0/11 independently verified PIT, 0/11 certified, `index_aics=null`** unchanged. Raw SEC/venue bytes stay as time-limited 30-day Actions artifacts, SHA metadata preserved in GitHub.
- Next: obtain legally licensed dated full corporate-action histories and historical membership across **all seven securities**, with contemporaneous release attestation and independent 24-month OOS, without retroactive adjustment. Alternatively proceed with Neoclouds and Insurers primary actual cash/debt data per committee priorities.

## 19 November 2026 — CoreWeave actual two SPV debt amounts and distinct recourse

- Substantive verified debt, not contract-only ceilings: **CoreWeave 2026-06-30 10-Q** discloses **DDTL 4.0 $2,837m reported debt / $8,500m facility ceiling (33.38%)**, borrower `CoreWeave Compute Acquisition Co. VIII, LLC`, **non-recourse except limited customary carve-out guarantees**; **DDTL 5.0 $1,101m reported debt / $3,100m ceiling (35.52%)**, borrower `CoreWeave Financing DDTL V, LLC`, **unconditional parent guarantee**. Two separate same-date debt balances sum to **$3,938m**, versus two ceilings **$11,600m**, ratio **33.95%**. The total is NOT identical to any parent guarantee, likely loss, cash drawn, or risk score. Do not sum it with Nscale facilities, lease rent, other CoreWeave consolidated balances or unrelated equity/guarantees.
- Primary issuer CIK `1769628`, 10-Q accession `0001769628-26-000366`, **filed 2026-08-12**, **SEC +14 available 2026-08-26**. New `scripts/aics_coreweave_two_spv_debt.py` independently replays original SEC text, checks named SPV borrowers, legal recourse phrases, precise table values and source-to-research consistency; `tests/test_aics_coreweave_two_spv_debt.py` catches forged borrower, recourse, debt amounts or filing date.
- Original [GitHub Actions replay success](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44571253169), run **44571253169**, artifact **14553887671**. Full original 10-Q **12,588,161 bytes**, SHA256 `ca366091455e6f3262a98868d3e62cfaef28a667729df7253270fd75cdd8f687`; independently downloaded and rehashed full ZIP SHA `ae5597e2dacab3ce538c50d113db55597ea4c5919972d86bf2847f78de6dded0`, 2 exact replay research JSON SHA `e943978b8e8bb77136b4b29cd0fade4b87e26047faa778af4448bf0ff0493209`. Permanent metadata [`coreweave_two_spv_debt_original_independent_rehash_2026-11-19.json`](../aics_data/research/coreweave_two_spv_debt_original_independent_rehash_2026-11-19.json). Raw artifact expires 2026-12-19.
- **Gate stays OPEN:** retrospective verification of original SEC bytes is not contemporaneous release-time PIT attestation; original economic debt balance is dated June 30 not November 19, parent recourse amount unknown, and 24-month untouched OOS unavailable. No certified SPV/Neocloud node. **22/66 technical stages, 0/11 PIT and 0/11 certified, `index_aics=null`**.
- Next: determine exact drawn amounts on the same legal borrower and date for Nscale Ward/NC, or independently verify historical PIT delivery before any third-stage credit. Keep legal recourse per instrument rather than treating all SPV debt as guaranteed by one parent.

## 19 November 2026 — live 24-month joint UST 30Y / Repo descriptive audit

- Across the previously pinned **24** matching month ends (Nov 2024–Oct 2026), the real DGS30−SOFR (UST 30Y input) and SOFR−IORB (Repo input) can be joined **exactly at the same observation date**. No missing, synthetic, backfilled or interpolated rows; existing 20-daily-yield-change DGS30 sample SD from each original month's ALFRED vintage is also joined.
- Descriptive arithmetic: DGS30−SOFR **>100 basis points in 10/24**, SOFR−IORB **>0 basis points in 5/24**; both **only Dec 2025 and Oct 2026**. This >100 comparison is **NOT** an audited or preregistered model threshold.
- Most recent cutoff Oct 2026: **DGS30 5.32%, SOFR 3.94%, IORB 3.90%, DGS30−SOFR +138bp, SOFR−IORB +4bp**, DGS30 20-change yield-vol SD **4.98bp**. Sep→Oct: DGS30−SOFR **−33bp**, SOFR−IORB **+6bp**, volatility **+0.57bp**. The two spreads moved **opposite directions**, so do not claim simultaneous spread widening.
- Real-source audit code `scripts/aics_joint_ust_repo_observed_research.py` and negative tests `tests/test_aics_joint_ust_repo_observed_research.py`; [source-matched Actions replay SUCCESS](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44574558415), artifact 14555817063. Independently downloaded ZIP rehash SHA256 **`e9c051c6ab87a5410a2eb44cb2f4ee28e1771d8a6d67b7f574de47cd19c1eafc`**; report SHA256 **`a36f9620325bf41324552912be07331f0c4ccd7ed5d3c7bfe28b23e028750595`**. Durable input-digest and outcome receipt `aics_data/research/ust_repo_joint_original_replay_external_rehash_2026-11-19.json`.
- Critical limitations: Retrospective ALFRED vintages and NY Fed calendar publication proxies **do not independently prove historic provider release times**. All 24 observations have now been examined retrospectively; they **cannot count as untouched 24m OOS**. DGS30−SOFR is not a true Treasury term premium; positive SOFR−IORB alone is not proof of repo distress. NO trading trigger, independent PIT promotion, predictive skill, or model AICS. **22/66, independent PIT 0/11, certified 0/11, `index_aics=null`** remain. Next: separate historical provider release attestation and genuinely untouched OOS, not more duplication of test procedures.

## 19 November 2026 — MetLife real Q2 mortgage loan/ACL original and mixed insurer as-of

- On **2026-11-19**, the insurer information set is intentionally **asymmetric**: PRU 2026-09-30 original 10-Q filed 2026-11-04 is available under SEC+14 since **2026-11-18**; MET 2026-09-30 original 10-Q filed 2026-11-06 is embargoed until **2026-11-20**. The latest currently eligible MET primary 10-Q is the **2026-06-30** filing (accession `0001099219-26-000050`, filed 2026-08-06, available 2026-08-20). Never use MET Q3 at the frozen cutoff or mislabel an async insurer pair as synchronized Sep 2026.
- Added real `scripts/aics_insurers_met_june_original.py`, primary-source `tests/test_aics_insurers_met_june_original.py` and `.github/workflows/aics-insurers-met-q2-original.yml`; [successful original replay run 44579156955](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44579156955). Actual SEC original **42,939,093 bytes** SHA `a2b5359da635b89ffb3ab39908538328d52d4dac6099073ffcc4b4636fc3209b`, embedded primary 10-Q SHA `363dd1ce87ef01168f4bda0c02c7ad1779f5f3b81d698a3c8e0bb4db6d7638d6`. Source hash is pinned in production; parser handles SEC parenthesized negative loan reserve entries.
- Authenticated original figures (**USD millions**): MET net mortgage loans **84,593 Dec 2025 → 82,856 June 2026** (−1,737 / −2.05%); mortgage ACL **1,193 → 1,358** (+165 / +13.83%). ACL 2026 half-year rollforward **1,193 +316 six-month net provision −151 net charge-offs =1,358**; ending segment ACL commercial **1,016**, agricultural **107**, residential **235**. Commercial ACL **74.82%** of mortgage reserve, **not AI-specific**.
- Downloaded actual Actions original artifact **14557198374** into separate container, independently rehashed and checked ZIP CRC: archive SHA `9dbd375f2d492bf8590cae480cbf6038c97f6f6e68076b6bab0f543a0062a856`, original research JSON SHA `aabdaa0a249081eca466b402e413065371a803902ceea8d3de69393b1b97ac36`. Permanent receipt `aics_data/research/met_2026q2_original_sec_acl_independent_rehash_2026-11-19.json`.
- MET ACL/(net mortgage loans+ACL) 1.39% → 1.61% is only an accounting proxy. Source captured retrospectively Nov 19; **NOT** independently historical release-time PIT. Dec 2025 figure is a comparative in the Aug 2026 filing, **NOT** a Dec 2025 PIT vintage. MET and PRU portfolios differ, so no apples-to-apples insurer credit stress comparison, NAIC or AICS node signal is established. **22/66 technical milestones, 0/11 independently attested PIT, 0/11 certified, `index_aics=null`**.
- Next: independently verify MetLife Q3 after 2026-11-20 under SEC+14 as a **new dated** information slice (not retroactively on Nov 19); obtain actuarial statutory capital/NAIC ratings/reinsurance risk and separately archived live-time source vintages. Do not claim 23/66 without genuine gate-3 attestation.

## 19 November 2026 — Insurers: first two-primary-original simultaneous replay at *asymmetric* cutoff

- Strict information set frozen **2026-11-19**: Prudential 2026-Q3 SEC 10-Q accession `0001137774-26-000221`, filed **2026-11-04**, eligible **2026-11-18**. MetLife 2026-Q2 SEC 10-Q accession `0001099219-26-000050`, filed **2026-08-06**, eligible **2026-08-20**. MetLife 2026-Q3 filed 2026-11-06 **cannot** enter until **2026-11-20**. No backdating either source to statement period end.
- New combined **real full SEC original replay** `scripts/aics_insurers_mixed_credit_originals.py`, tests `tests/test_aics_insurers_mixed_credit_originals.py`, workflow `.github/workflows/aics-insurers-two-original-credit-replay.yml`. [Original real-source replay run 44588952381](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44588952381) **successful** with two original submissions and a joined research report. Downloaded archive **14563770502**, independent external SHA256 ZIP `627ae6220ac0d5ea354c56aca0be7884d49720bdf9216d91483a28cb77a23778` (ZIP CRC clean). Exact PRU original **56,649,032 bytes** SHA `49947c62bc026ff11df94e2c157ac67c18a073c7ec2f4e87f95f7c1645d59b41`; MET original **42,939,093 bytes** SHA `a2b5359da635b89ffb3ab39908538328d52d4dac6099073ffcc4b4636fc3209b`. Full merged JSON SHA `5e16f271abafae3ee2ebc826bdd534e9f83ef42561625862f7b7c5ee1448fb7a`, permanently pinned at `aics_data/research/insurers_pru_met_mixed_original_sec_external_rehash_2026-11-19.json`.
- PRU **commercial mortgage and other loans net** $64,715m (Dec 2025 comparative) → **$67,004m** (Sep 2026): **+$2,289m / +3.54%**. Related reported ACL **$469m → $449m**: **−$20m / −4.26%**. A separately identified subset **non-accrual loans *without related allowance*** **$442m → $610m**, **+$168m / +38.01%**. This is **NOT** all non-performing loans, defaults, or expected losses.
- MET **mortgage loans net** $84,593m (Dec 2025 comparative) → **$82,856m** (Jun 2026): **−$1,737m / −2.05%**. Mortgage ACL **$1,193m → $1,358m**: **+$165m / +13.83%**. Direct original note reconciliation **1,193 + 316 six-month net provision − 151 chargeoffs = 1,358 ($m)**. Commercial ending ACL **$1,016m**.
- **NO synchronization or risk ranking**: end dates differ (June vs September); MET broader mortgage portfolio, PRU commercial mortgage *and other loans*; December 2025 comparatives supplied by subsequent filings do not provide December 2025 original-time PIT. Original full submissions rehashed retrospectively in November. Missing insurer NAIC/RBC, private-credit AI attribution, reinsurance, true live provider as-of delivery, untouched 24m OOS. `Insurers` remains **2/6**, **22/66** project, **0/11** independent historic PIT and 0/11 certified, **AICS=null**.
- Next meaningful work should obtain **MetLife Q3 only once the November 20 SEC+14 embargo expires**, as a new as-of research slice, then evaluate statutory capital and covered credit-loss scope rather than reporting cross-issuer apples-to-oranges comparisons.

## 5. Next tasks, in strict order

1. **Sanity-check repo and tests** on the selected feature branch. Reproduce the progress percentage; identify any mismatch between workboard, branch and latest GitHub Actions. Make reliable CI rather than accumulating green but skipped collection jobs.
2. **AI Equities PIT gate beyond the completed raw archive stage (2/6)**: source dated point-in-time price vintages, constituent membership and corporate actions with permissions and no split-adjusted future leakage; do not infer PIT from 441 retrospectively served price rows.
3. **Extend independently checked company reconciliation**: the 37-name OMI/Telegram mapping, three unverified project graphs and no-promotion safeguards now pass CI. Obtain dated original contracts for Crusoe, Lambda, Firmus, SharonAI, GMI, Nscale, etc. and exact SPV borrower/guarantor identities. Keep PDF-only / Telegram-only leads quarantined.
4. **PIT audit and metrics**: Insurers NAIC + Level 3/private loans and reinsurance; SPV parent guarantees/drawn debt/credit recourse; Neoclouds cash conversion and debt maturity; NVIDIA 10-Q guarantee ceiling vs drawn exposure; macro Repo/UST ALFRED vintages.
5. **Derive genuinely documented node score methodology** with held-out OOS; certification only after independent data integrity review, do not add synthetic observations to fill missing nodes.
6. **Committee deliverable Nov 30**: clear caveats, observed candidate metrics vs unavailable full AICS, verified history, risk graph, source evidence, and next validation gates.

Update progress ONLY after eligible source receipts and unit tests, not because code was created or a research report was summarized.

## 6. Files which may require reattachment to Work

Project Aucs may retain chat attachments and project files, but new Work tasks cannot be assumed to see every file merely because it existed in an earlier message. Check before declaring success. User-held key attachments:

- `AICS_OMI_Brace_for_Impact_original_2026.pdf` (88-page original; original publisher URL in JSON).
- `AICS_telegram_11_screens_source_2026-11-18.zip` (11 screenshots, original image files).
- `aics_data_pit_package.zip`, `aics-raw-evidence.zip`, `AICS_research_monitor_2026-11-18.zip`, `AICS_ARCC_Private_Credit_research_2026-11-18.zip` where accessible.

Most durable context is in GitHub and the JSON registries; never infer that downloaded GitHub Actions 30-day artifacts will remain available forever.

## 7. AICS Work startup instruction (copy to new task)

> Продолжай проект AICS (Aucs) из GitHub `nikitamalinovskiybcs-beep/Fly`, ветка `devin/1779618014-quant-risk-framework`. **Сначала прочитай `docs/AICS_WORK_HANDOFF_2026-11-18.md`, `docs/aics_progress.md` и `aics_data/progress/status.json`, затем перепроверь последние Actions и CI.** Не начинай заново. Работа по 11 неизменным узлам и весам 1050; SEC +14 дней, ALFRED винтажи, без фабрикации, backfill и look-ahead. Реестр 37 компаний и Telegram/OMI-материалы уже в `aics_data/research`. Пройди по узлам без промежуточных согласований на обычные безопасные шаги, начни с AI Equities и проверки контрактов Neoclouds/SPV, сохраняй все изменения в репозитории с тестами и показывай реальный прогресс 0–100% из `status.json`. Не выдавай AICS и прогнозную точность за сертифицированные до независимого PIT и OOS. Сначала дай короткий план и выполняй его, затем предоставь конкретные commits, результаты тестов и обновлённую шкалу.
