# AICS V27 · SPV borrowings, recourse and 2008-style funding-transmission research

**22 November 2026.** Quantitative research (not a market forecast or live credit balance). The last original SEC values were retrospectively read and source bytes SHA-verified, but the historical first-delivery PIT receipts remain **unattested**. This work does not change AICS's original 11 weights (1,050), historical 450/500 thresholds, independent certification status or trading.

## The economically real and non-additive facts

| Original disclosure | Legal borrower or group | Economic as-of | Available (SEC filed +14) | Meaning | Value |
|---|---|---|---|---|---:|
| CoreWeave June 2026 10-Q DDTL 4.0 | CoreWeave Compute Acquisition Co. VIII, LLC | 2026-06-30 | **2026-08-26** | Reported facility debt / contractual ceiling | **$2.837bn / $8.500bn** |
| CoreWeave June 2026 10-Q DDTL 5.0 | CoreWeave Financing DDTL V, LLC | 2026-06-30 | **2026-08-26** | Reported facility debt / contractual ceiling | **$1.101bn / $3.100bn** |
| Nscale Sept 2026 S-1 | Ward County and NC SPVs | filed 2026-09-18 | **2026-10-02** | Separate GPU borrowing contractual ceilings (NOT actual drawn debt) | **$1.850bn / $1.200bn** |
| Same S-1: Dell Financial Services | Same two Nscale SPVs | 2026-09-04 disclosure | **2026-10-02** | 40 initial-term rental schedules **including** ~$34.8m finance charges; NOT GPU loan principal | **~$2.540bn** |
| Nscale S-1 UK services facility | Nscale Services UK Ltd | 2026-03-31 | **2026-10-02** | Historical drawn-and-outstanding term loans in separate legal group | **~$58.9m** |
| Nscale S-1 Macquarie facility | Nscale Global Holdings Limited | dated 2025-08-01 / 2026-01-30 | **2026-10-02** | Two historical **utilization events**, NOT current balance | **$70.1m / $34.9m** |
| Nscale S-1 consolidated balance sheet | Consolidated Nscale | 2026-06-30 | **2026-10-02** | Debt carrying value, not incrementally additive to the historical utilizations | **$137.4m** |

[Original CoreWeave SEC 10-Q](https://www.sec.gov/Archives/edgar/data/1769628/000176962826000366/crwv-20260630.htm). The two dated facility debts total **$3.938bn** of reported debt against **$11.600bn** of ceilings, or **33.95%**. This only describes those two credit facilities, not consolidated indebtedness, parent enforceable guarantees, credit losses, lendable availability, or the 2026-November current balance. DDTL 4.0: **non-recourse except limited customary guarantees**. DDTL 5.0: **unconditional parent guarantee** (enforceable amount independently unquantified). The two borrower-debt balances are the only two same-date validated SPV facility balance edges, with **zero** named current lender-to-borrower dollar exposure edges proven.

[Original Nscale S-1 first-filed source](https://www.sec.gov/Archives/edgar/data/2110365/000119312526395475/ck0002110365-20260918.htm). Nscale Ward/NC **actual draws remain unknown**, as do the outstanding DFS lease liability, financial support enforceability and parent exposure amount. The Macquarie historical $105m total uses are not a current exposure. **Never add** Nscale GPU facility ceilings, DFS rent, $137.4m consolidated debt, $58.9m separate UK debt, and $105m historical Macquarie utilization events.

## Early buildout stress versus credit contagion

- The original four hyperscalers (Microsoft, Amazon, Alphabet, Meta) saw aggregate **OCF−gross cash PPE** fall from **+$60.201bn (2025 Q4)** to **+$20.977bn (2026 Q1)** to **+$6.709bn (2026 Q2)** to **−$26.425bn (2026 Q3)**.
- Separately, CoreWeave's **2026 Q2 OCF−cash PPE = −$5.743bn**. This is the *same issuer and quarter* as the two published SPV facility debts. Both source types first become eligible under AICS SEC+14 **2026-08-26**. A cash gap is **not** new financing or an SPV draw.
- The four hyperscalers **are not** CoreWeave and Nscale; no valid aggregate cross-company funding sum, lender loss, debt maturities run, bank contagion simulation, or dated exposure flow can yet be inferred.
- The physical overbuild/cash-flow squeeze resembles an **economic risk channel** discussed for 2000, while the SPV borrower/guarantee/wholesale funding structure is a **distinct hypothesis** inspired by 2008. Comparable historical PIT source vintages have not been reconstructed; **numeric similarity percentages and crash probabilities remain null**.

## AICS code and source checks

- [Source-aware instrument bridge](../scripts/aics_spv_funding_transmission_bridge.py) reads independently rehashed CoreWeave/Nscale original metadata and same-issuer CoreWeave financials; before 2026-08-26 CoreWeave balance is **null** and before 2026-10-02 Nscale ledger is **null**.
- [Non-additive tests](../tests/test_aics_spv_funding_transmission_bridge.py) reject fake guarantees, nominal ceiling as reported debt, lease rent as debt, source-date backdating and forged cross-issuer causality.
- [Existing 30-role model-improvement agent](../scripts/aics_ten_model_improvement_agents.py) now includes the V27 research bridge in `CreditContagionAnalyst` and `ModelChallenger`. These are instrument-level source-confirmed exposures **without current named lender identity**.
- [30-agent coordinator](../scripts/aics_thirty_agent_cycle.py) exposes **2 named borrower/facility balance records** but leaves the `SPV_CREDIT_RECOURSE_NETWORK` experiment open because **0 currently verified named lender→borrower dollar exposure edges**.
- [GitHub Actions](../.github/workflows/aics-ten-real-source-waves.yml) runs source-capture, model challenger, bridge tests, and the integrated research cycle. No additional live source HTTP collection is requested by the bridge.

## Next evidence required for a genuine 2008-credit-transmission predictor

Obtain lender-level current original exposure/covenant/recourse, maturity walls, actual Nscale Ward & NC draws with dates, parent guarantee recourse limits, collateral/depreciation vintages, repo haircuts and funded vehicle-to-insurer/BDC identities. Only then independently revalidate a historical as-of source series against documented 2000/2008 episodes and a genuine untouched 24-month OOS dataset. The bounded V27 research should not change risk decisions until these tests pass.
