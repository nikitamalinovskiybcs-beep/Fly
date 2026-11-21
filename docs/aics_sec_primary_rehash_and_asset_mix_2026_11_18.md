# AICS — real SEC source byte audit: Insurers and Neoclouds/SPV

**Evidence as of 2026-11-18.** This is a reproducible **research-only** source/metric receipt, not an audited node score or historical companyfacts PIT vintage.

## Resolution of blocked SEC collection

Previous SEC Neoclouds/SPV Action failed because `AICS_SEC_USER_AGENT` was empty. The runner now uses `AICS_SEC_USER_AGENT` or, if absent, the project's existing `EDGAR_IDENTITY` secret. The code still refuses non-accountable contacts; missing credentials cannot produce green source evidence.

- SEC Neoclouds/SPV [run 44389973635](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44389973635): **4/4** date-eligible original SEC filing HTML documents downloaded and separately rehashed against the original GitHub Actions artifact. CoreWeave Q3 10-Q (filed 2026-11-12) remains embargoed through 2026-11-25, first eligible **2026-11-26**.
- Insurers MET/PRU [run 44390127352](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44390127352): both issuers downloaded, **6** SEC JSON originals rehashed, including **2** SEC `filings.files` appendices. **521** current companyfacts observations passed local filing-accession and SEC +14-day chronological filters (MET **257**, PRU **264**). Workflow verifier originally failed due direct script import context; using `python -m scripts.aics_verify_insurers_sec_evidence` fixed it.

The ZIP checks and original source SHA-256s, filing dates, archive IDs and expiration dates are pinned in `aics_data/research/sec_primary_archive_independent_rehash_2026_11_18.json`. Original ZIP contents are in 30-day Actions artifacts (expire 2026-12-18). The source manifest alone cannot recreate bytes after archive expiration.

## Two descriptive, non-scoring SEC candidate calculations

These are **AFS debt securities / total GAAP assets** from the latest complete common-accession pair of filtered SEC companyfacts rows available in the retrieved archive for each issuer, with an exact SEC +14 calendar day availability restriction. Values in USD billions are displayed only for readability; the machine receipt retains integer dollars.

| Company | Reporting period | Filed / AICS available at | GAAP assets (USD bn) | AFS debt securities (USD bn) | AFS / assets |
|---|---|---|---:|---:|---:|
| MetLife (MET) | 2026-06-30 | 2026-08-06 / 2026-08-20 | 759.372 | 322.183 | **42.4276%** |
| Prudential Financial (PRU) | 2026-09-30 | 2026-11-04 / 2026-11-18 | 771.378 | 322.460 | **41.8031%** |

Formula: `100 * AvailableForSaleSecuritiesDebtSecurities / Assets`. Both values in each row share issuer, period, filing accession, and filed date. At 2026-11-18 the MET 2026Q3 source was not an eligible matched data pair in this archive, so do **not** compare these two percentages as an aligned quarterly trend, or infer cross-issuer relative stress.

These GAAP AFS-debt-security amounts are **not** company-specific AI exposures, not private credit or Level 3 shares, not NAIC statutory allocations, and not evidence of a contractual SPV guarantee. A current companyfacts response can include revised or amended facts retroactively. The byte-checked archive establishes provenance of current-capture sources and local consistency, **not** original date-stamped historical provider vintages.

## Reproduce the fail-closed receipt check

```sh
python -m unittest discover -s tests -p test_aics_validate_sec_rehash_receipt.py -v
python -m scripts.aics_validate_sec_rehash_receipt
```

The script checks receipt metadata, pinned source SHA-256 syntax and pairings, full SEC +14-day chronology, 2/2 candidate arithmetic, all 11 weights and blocked score fields. **It does not redownload/re-hash the ZIPs itself**; a green receipt unit test alone is never independent byte-level attestation. The latter was separately performed on the two downloaded GitHub Actions ZIP archives and is recorded in the immutable-source SHA values within the receipt.

## Next evidence gate

Obtain full dated originals and source-level amendments/vintages, review NAIC statutory filings and private-credit/Level 3 assets, identify actual SPV borrowers and legal recourse, and keep a genuinely untouched 24-month OOS. The AICS index and any proposed investment response remain N/A. No additional 6-stage project milestone was credited from these research calculations.
