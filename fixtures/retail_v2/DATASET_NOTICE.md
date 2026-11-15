# Dataset attribution and preparation notice

**Source:** Chen, D. (2015). *Online Retail* [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5BW33

- Official dataset page: https://archive.ics.uci.edu/dataset/352/online%2Bretail
- Official download: https://archive.ics.uci.edu/static/public/352/online%2Bretail.zip
- Dataset license: **Creative Commons Attribution 4.0 International**, https://creativecommons.org/licenses/by/4.0/
- License legal text and disclaimers: https://creativecommons.org/licenses/by/4.0/legalcode
- Original creator named by UCI: Daqing Chen. This project is not endorsed by the creator or UCI.

These files are a modified, bounded positive-sales sample derived from the source workbook. They are not the complete dataset, a complete invoice ledger, or a statement of actual merchant net revenue. CustomerID and product descriptions are omitted. Countries, invoice/line provenance, dates, quantities and prices derive from the original records. The original raw workbook remains outside version control.

**Modifications:** selected five dated partitions; excluded cancellation invoices, nonpositive/invalid inputs and lines not representable as exact pence under the documented decoding policy; selected complete eligible invoice groups by fixed SHA-256 order, up to 160 lines per partition; converted quantity times sterling price into integer pence; mapped Country to region; constructed unique IDs from invoice number and original worksheet row. The provenance JSON files retain original numeric XML strings and normalized numeric values. CSV rows are sorted by their stable IDs. Selection details and eligibility counts appear in `fixture.json`.

XLSX numeric strings are interpreted as finite IEEE binary64 and shortest round-trip decimal strings before exact Decimal arithmetic. This handles representation tails such as `2.5499999999999998` without claiming to verify a historical price. Final line amounts must be exactly integral pence; no monetary rounding is performed. Sterling prices are GBP for every country; country does not determine currency.

Initial refunds and support observations are absent, represented by empty sources. The illustrative exchange rates, quantity/price corrections, offsetting changes, synthetic refunds and source failures in the evaluation cases are **staged interventions**, not historical facts. Reports use existing registered tools and declared recipes. Preserve this notice, attribution, license link and modification disclosure when redistributing these derived files.

The application code's MIT license does not replace the dataset's CC BY 4.0 terms. The linked dataset license includes its warranty and liability disclaimers.
