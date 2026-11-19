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
