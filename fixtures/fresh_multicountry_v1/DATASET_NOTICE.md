# Dataset attribution and transformations

Daqing Chen (2015), **Online Retail**, UCI Machine Learning Repository.
[Dataset](https://archive.ics.uci.edu/dataset/352/online+retail) ·
[DOI 10.24432/C5BW33](https://doi.org/10.24432/C5BW33) ·
[Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/).

Original `Online Retail.xlsx` SHA-256:
`43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`.
The source workbook contains 541,909 transaction rows. Every country's UnitPrice
is denominated in GBP; country does not imply a different source currency.

This extract contains all 933 eligible positive transaction lines from April 10,
2011, across 32 invoices: United Kingdom 907 lines, Belgium 26 lines. It excludes
seven cancellation rows from that date. The prospectively fixed selection chose
the first complete day outside previously profiled months that had at most 1,000
eligible lines and at least two countries. See [selection.json](selection.json)
and the [protocol](../../docs/FRESH_MULTICOUNTRY_PROTOCOL.md).

Changes from the original:

- Filter cancellation invoices and unsupported/nonpositive quantity or price.
  Decode numeric cells through binary64 shortest decimal spelling; retain only
  integral positive quantities and exact whole-pence line amounts within bounds.
- Preserve the selected original worksheet row, invoice number, raw invoice date,
  quantity and unit-price XML cells, and country in `source_cells.csv`.
- Create `orders.csv` with `order_id,region,currency,gross_cents`. The order ID is
  `uci:<InvoiceNo>:row:<original worksheet row>`, region is country, currency is
  GBP, and gross cents are exact line pence. No source amount is rounded to qualify.
- Omit customer IDs, product descriptions and stock codes from both files.
- Apply the explicitly authored GBP/USD **1.25 → 1.30** scenario. These are not
  historical exchange rates or corrections to original transactions.

Refund and support observations are absent. The workflow models omitted fields
as empty sources with zero contribution; this is not evidence of zero real-world
refunds or support activity. These figures describe an eligible positive-sales
extract, not complete merchant revenue. UCI and the dataset author do not endorse
ProofFlow or this experiment.
