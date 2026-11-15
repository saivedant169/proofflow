# Prospective multi-country correction workflow

This is a reviewable summary of the private protocol frozen before the first and
only paired attempt. The original protocol SHA-256 is
`a3d1ac8b8820e632e341373efaa983717275d34a324c63dbe0f50b3204987c84`;
the complete study freeze SHA-256 is
`855e22cec6cc68afd80cb0b2f4c98749e06cdaaf76b1551cb50c6241204d2cdd`.
The measured application and existing comparison runner were unchanged revision
`c2c19c1397026e136bf7648ddb0604a4d2ea6d7f`. This later documentation/evidence
package is a sanitized projection, not a new measured application revision.

## Selection fixed before arithmetic or execution

Use the hash-pinned [UCI source](../fixtures/fresh_multicountry_v1/DATASET_NOTICE.md).
Conservatively exclude whole months December 2010 and January, February, March,
May, June, August, September and November 2011. These cover every month with
retained previous eligibility profiles and all prepared/exercised real-data
fixtures, including January 16's hosted browser and connector trials.

Scan remaining days chronologically. Choose the first whole date with 1–1,000
eligible lines and at least two countries; retain every eligible line in original
worksheet order. Choose the report country with most lines, using lexical order
to break ties. No row sampling, monetary-outcome selection or post-failure date
substitution is allowed. Stop on source integrity, invoice overlap or size failure.

Eligibility follows the existing real-partition policy: Excel 1900 calendar day;
supported trimmed invoice/country; no cancellation invoices; positive integral
quantity at most one billion; positive finite price; binary64 shortest-decimal
numeric decoding; exact line pence bounded 1–10^12, with no qualifying rounding.
The complete CSV must fit 1 MiB. Selected invoices must not occur in excluded
months. Keep sanitized original numeric cells for independent reconstruction.

The recorded first qualifying day is April 10, 2011, with 933 lines and two
countries. April 3 fit the row cap but had only UK lines; other preceding April
days exceeded the cap. [The retained candidate profiles](../fixtures/fresh_multicountry_v1/selection.json)
show the full selection sequence. The pre-scan rule/source manifest SHA-256 is
`e48684119133192701991364c661b9d757386c57169ef49925a971210d3a2894`.

This is a previously unprepared daily partition outside months with retained
period profiles. It is not a sealed/unseen holdout: earlier scans inspected
workbook-wide eligibility and invoice relationships, and unexecuted proposals
named April. It remains one case from the same known public dataset.

## Identical input, output and handoff scope

Both methods receive the exact same CSV, selected country, initial GBP/USD 1.25
and corrected GBP/USD 1.30. Only FX changes; no CSV line changes. All countries'
prices are GBP. Refund/support observations are absent and default to empty
sources. Missing observations must not be described as observed zero activity.

The independent standard-library oracle reconstructs every uploaded line from
original numeric cells, groups GBP pence by country, converts each country's
subtotal once with Decimal ties-to-even, then sums integer USD cents for the
company. It neither imports application arithmetic nor uses uploaded gross
cents as its arithmetic source. All eight semantic outputs for both stages were
frozen before either arm ran. Zero uses canonical integer 0; synthetic checks
cover missing fields and textual negative-zero rejection separately.

**Ordinary recalculation** uses the existing standard-library CSV/Decimal control:
one validated scan, eight logical outputs computed together, four reconciliation
controls, immutable timestamped report files and a shared latest-input digest.
A handoff guard checks both the current input revision and exact published bytes.

**ProofFlow** uses unchanged local FastAPI endpoints and native HydraDB OSS 0.4.0
in fresh owned namespaces with independent temporary state. Two same-session
clients run preview/create, then preview/update/refresh and checked exports.
Demo bootstrap, all preflight calls, recorded executions and fresh-recipe
verification calls are counted. Observers wrap the original functions without
replacing results. The independent raw-cell oracle remains separate from the
product's verification, which uses product arithmetic.

## One ordered paired attempt

Ordinary runs first, then ProofFlow; each receives a cold initial close and one
warm FX correction. No timing comparison is made. No retries, resume, replacement
day or changed threshold. Preserve failures and unobserved later steps. A failed
arm does not suppress the other arm after shared prerequisites have passed.

1. Publish initial reports, compare all eight outputs and currency/units with the
   frozen oracle, and accept the current company/UK snapshot. Keep the old view.
2. Accept corrected sources before publishing corrected reports. Refuse the old
   view as current without content. ProofFlow must return HTTP 409/no-store,
   withhold both current values as null, retain historical heads and record no
   new executions at publication.
3. Check exactly four affected outputs and native source/execution/artifact paths
   from the superseded FX version to both prior reports. Gross, refunds, net and
   support heads remain current.
4. Recalculate/publish ordinary reports and refresh ProofFlow. Compare eight
   outputs again, refuse the old view again, then accept current reports. Check
   exact unaffected artifact/receipt identities and four replacement receipts.
5. Reload current state and check report identities. Confirm initial exported
   bytes remain unchanged; static historical files are expected in both methods.

Each arm schedules 16 semantic comparisons, two stale refusals and two current
acceptances. Outputs/countries/requests are not independent trials. Record
ordinary row scans/logical outputs separately from ProofFlow function invocations;
their units differ. A retained receipt is not evidence of compute savings.

## Decision rule and evidence boundaries

Both guards passing means equal observed stale-handoff prevention. Correct,
retained artifact identities and native paths may differentiate provenance on
this case. An arithmetic failure disqualifies successful-output comparisons for
that arm. No meaningful advantage is an acceptable conclusion. No claim of
latency, cost, compute savings, adoption, human usability, learning or broad
generalization follows from this design.

Original raw attempt evidence remains private. The tracked receipt uses semantic
aliases and preserves original evidence hashes, but these hashes alone do not
let readers inspect unavailable raw bytes or independently attest native service
execution. The tracked verifier independently recomputes source arithmetic and
checks the normalized receipt's internal consistency. With the original workbook,
it also verifies complete row selection and provenance. See the
[results and verification instructions](FRESH_MULTICOUNTRY_RESULTS.md).
