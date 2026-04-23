# CSV Product Import

Upload a CSV from **Admin → Products → Import CSV** to bulk-create products. One row = one product with one default variant.

## Columns (header row required)

| column  | required | notes                                         |
|---------|----------|-----------------------------------------------|
| title   | yes      | product title                                 |
| handle  | yes      | URL slug; must be unique                      |
| barcode | yes      | EAN/UPC for POS scanning (may be empty)       |
| sku     | yes      | internal SKU (may be empty)                   |
| price   | yes      | decimal, e.g. `4.99`                          |
| status  | no       | `active` (default) or `draft`                 |

Rows with duplicate handles are skipped. Rows with bad prices or missing title/handle are reported in the result summary (toast + browser console).

See `example-products.csv` for a starter file.
