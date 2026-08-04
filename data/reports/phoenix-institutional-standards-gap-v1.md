# Phoenix institutional standards gap review

## Important scope

These sources are standards, supervisory guidance, or industry frameworks. They
do not automatically make Phoenix compliant. Applicability depends on the
entity, jurisdiction, client type, product manufacturer/distributor role, and
whether Phoenix is research-only or used for advice/sales.

## Sources reviewed

1. Federal Reserve/OCC, **SR 11-7 Model Risk Management**:
   https://www.federalreserve.gov/boarddocs/srletters/2011/sr1107.pdf
2. ISDA, **SIMM principles and model specification**:
   https://www.isda.org/a/vAiDE/simm-from-principles-to-model-specification-4-mar-2016-v4-public.pdf
3. ISDA, **SIMM methodology v2.5A**:
   https://www.isda.org/a/FBLgE/ISDA-SIMM_v2.5A.pdf
4. EUSIPA governance and product categorisation:
   https://eusipa.org/governance/
5. EU PRIIPs Regulation, consolidated text:
   https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX%3A02014R1286-20240109
6. ESMA MiFID II product-governance guidelines:
   https://www.esma.europa.eu/sites/default/files/2023-08/ESMA35-43-3448_Guidelines_on_product_governance.pdf
7. ESMA MiFID II suitability guidelines:
   https://www.esma.europa.eu/sites/default/files/2023-04/ESMA35-43-3172_Guidelines_on_certain_aspects_of_the_MiFID_II_suitability_requirements.pdf

## What Phoenix should adopt

| Standard theme | Phoenix requirement | Current status |
|---|---|---|
| Effective challenge | Independent challenger, validation, documented limitations | Partial |
| Model lifecycle | Registry, version, owner, change log, approval and retirement | Partial |
| Reproducibility | Same inputs, trade terms and seed produce the same result | Partial |
| Transparency | Component attribution, assumptions, sensitivities and dispute trail | Partial |
| Data governance | Source, timestamp, version, freshness, quote-fit and evidence class | Partial |
| Validation | OOS/holdout metrics, baseline comparison, backtesting and monitoring | Blocked |
| Stress testing | Barrier, correlation, volatility, gap and liquidity scenarios | Research-only |
| Product disclosure | Payoff, maximum loss, costs, liquidity, issuer/credit and scenario warnings | Partial |
| Target market | Client type, knowledge/experience, objectives, risk tolerance and capacity | Pending human review |
| Suitability | Documented client assessment and best-interest process | Pending human review |
| Product taxonomy | Clear classification of payoff and riskiness | Partial |

## Important distinctions

- **SR 11-7** is supervisory guidance for banking organizations, not a
  universal Phoenix certification. It is still the best public template for
  model development, validation, governance and effective challenge.
- **ISDA SIMM** is an initial-margin model for non-cleared OTC derivatives,
  not a Phoenix note-pricing approval. Phoenix should borrow its principles:
  transparent inputs, replicability, component attribution, sensitivity,
  timely recalculation and dispute-ready outputs.
- **EUSIPA** provides industry self-regulatory and categorisation practices.
  It is useful for product taxonomy and transparency, not a substitute for
  local legal/regulatory advice.
- **PRIIPs** is aimed at retail-investor KID disclosure. A professional client
  profile may change applicability, but does not remove the need for accurate
  risk, cost, liquidity and loss disclosures.
- **MiFID II product governance/suitability** remains central where a firm
  manufactures, distributes, advises on, or manages the product.

## Required institutional redesign order

1. Freeze a canonical payoff and risk calculation contract.
2. Add a model registry with owner, version, assumptions, dependencies,
   validation status and approval state.
3. Separate market evidence, model estimates, assumptions and AI research.
4. Replace silent unknown-ticker defaults with explicit unavailable/uncertain
   states and production blocking.
5. Add independent challenger calculations and aligned-engine reconciliation.
6. Add OOS anchors, empirical baseline, stress tests and monitoring thresholds.
7. Generate a product-risk/disclosure packet with maximum loss, costs,
   liquidity, issuer risk, scenarios and limitations.
8. Keep final target-market, suitability, compliance and model-risk decisions
   human-owned.

## Phoenix decision

Current status remains **research-only / NO-GO for client production**. The
standards support the redesign, but they do not supply the missing market
evidence, independent validation, or human approvals.
