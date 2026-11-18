# AICS — fourth ten-stage engineering increment (2026-11-18)

Status: implemented in PR branch, pending latest CI verification. All checks are research-only.

1. Diagnose and fix the missing observation-duplicate counter.
2. Verify each macro CSV row count against the source manifest.
3. Reject nonfinite numeric observations.
4. Reject empty macro source files.
5. Verify FRED current-snapshot vintage dates match the manifest as-of.
6. Verify SEC ticker-to-CIK mapping for all six companies.
7. Reject SEC report periods ending after their filing dates.
8. Check SEC accession identifier structure.
9. Bind each SEC XBRL companyfacts row to its exact CIK.
10. Extend XBRL accession checks to match filing identifiers.

All validations fail closed. No production index or predictive score is generated.

## Outstanding evidence

- PR CI does not download external data; syntax and offline checks are necessary but insufficient.
- Live run on default branch is required to test new quality gates against complete artifacts.
- Historical ALFRED vintages for the FRED-current-only series are not established.
- 11-node PIT coverage, fixed 24-month chronological OOS, and investment committee approval remain outstanding.
- Fixed 11-node weights sum to 1050. No trades, verdict changes, or model promotion.
