# Cai Jiao BMP records 583–594: ingestion gate

## Source identity

Liu et al. (2024) Supplementary Table S1 maps BMP database query numbers 583–594 to:

- title: *Promoting Anaerobic Digestion by Biochar: Preliminary Study on Technology Optimization and Mechanism Analysis*
- author: Cai Jiao
- affiliation: Tongji University
- document type: master's thesis
- thesis DOI: not reported

The peer-reviewed article *Effects and optimization of the use of biochar in anaerobic digestion of food wastes* (DOI `10.1177/0734242X16634196`) is related context. Row-level equivalence between the thesis records and the article has not been verified.

## Files in this repository

- `data/candidate_manifests/cai_jiao_bmp_records_583_594.csv` preserves the 12 query identifiers and explicitly blank unrecovered fields.
- `data/candidate_manifests/cai_2016_aggregate_evidence.csv` preserves only values reported at ISR-group level in the article abstract.

Neither file is model input.

## Current blocker

On 2026-09-10, `https://bmp.wmdatabase.cn/` returned an expired-certificate error before the registration/login interface. Secure export was therefore unavailable. The certificate must not be bypassed and credentials must not be sent over an insecure connection.

## Aggregate evidence boundary

The article abstract reports, for ISR 2.0, 1.0, and 0.8:

- reported lag-phase shortening ranges of -20.0% to 10.9%, 43.3% to 54.4%, and 36.3% to 54.0%;
- reported maximum methane-production-rate increases of 100% to 275%, 100% to 133.3%, and 33.3% to 100%;
- best reported biochar doses of 2.5, 0.625, and 0.5 g/g-waste.

Positive lag-shortening values mean a reduction in lag duration. For ISR 2.0, the abstract's unusual negative endpoint is preserved verbatim as numeric evidence but its direction is explicitly unverified; it must not be interpreted until full-text treatment mapping is recovered.

These values summarize several treatments. They must not be assigned to individual query numbers or expanded into pseudo-observations.

## Admission checks

Records 583–594 remain excluded from training and validation until all checks pass:

1. Obtain the official database export or a primary thesis table/figure.
2. Record the downloaded file checksum and access date.
3. Verify which query number maps to each ISR and biochar dose.
4. Preserve the database's original outcome definitions and units for Pmax, Rmax, and lag time.
5. Determine whether values were measured directly, fitted, or digitized.
6. Verify blank correction and normalization basis.
7. Preserve replicate identity only when explicitly supplied.
8. Compare source rows against the repository data contract.
9. Emit a source-specific machine-readable QC report.
10. Declare the final role before analysis to prevent leakage.

Until then, the source status is `BLOCKED_OFFICIAL_EXPORT` and `import_eligible = No`.
