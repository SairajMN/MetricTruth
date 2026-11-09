# Certified Metric Registry Specification

All business metrics are defined in `registry/metrics/*.yaml` and loaded into the `certified_metrics` and `metric_versions` tables on startup.

## Registered Metrics

| Metric ID | Name | Formula (`numerator / denominator`) | Aggregation | Unit | Status | SLA |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `paid_customer_acquisition_cost` | Paid Customer Acquisition Cost | `total_paid_media_spend / paid_attributed_new_customers` | `ratio` | `USD` | `approved` | 24h |
| `blended_customer_acquisition_cost` | Blended Customer Acquisition Cost | `total_paid_media_spend / total_valid_new_customers` | `ratio` | `USD` | `approved` | 24h |
| `fully_loaded_customer_acquisition_cost` | Fully Loaded Customer Acquisition Cost | `total_loaded_acquisition_spend / total_valid_new_customers` | `ratio` | `USD` | `draft` | 24h |
| `cost_per_click` | Cost Per Click | `total_paid_media_spend / total_ad_clicks` | `ratio` | `USD` | `approved` | 24h |
| `click_through_rate` | Click-Through Rate | `total_ad_clicks / total_ad_impressions` | `percentage` | `PERCENT` | `approved` | 24h |
| `customer_conversion_rate` | Customer Conversion Rate | `paid_attributed_new_customers / total_ad_clicks` | `percentage` | `PERCENT` | `approved` | 24h |
| `return_on_ad_spend` | Return on Ad Spend | `paid_attributed_revenue / total_paid_media_spend` | `ratio` | `RATIO` | `approved` | 24h |

## Mandatory Exclusions & Attribution Rules

- `internal_test_campaigns`: Excludes campaigns where `campaign_status != 'ACTIVE'` (e.g. `CMP_TEST_999`).
- `invalid_customer_records`: Filters `customer_acquisitions.is_valid = TRUE`.
- `last_non_direct_paid_click`: Filters `customer_acquisitions.attribution_model = 'last_non_direct_paid_click'` for Paid CAC, CVR, and ROAS.

