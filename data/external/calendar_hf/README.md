
---
license: mit
language:
  - en
task_categories:
  - time-series-forecasting
  - tabular-classification
  - tabular-regression
tags:
  - forex
  - forex-factory
  - forexfactory
  - economic-calendar
  - historical-data
  - financial-data
  - macroeconomics
  - time-series
pretty_name: "Forex Factory Historical Economic Calendar Dataset (2007–2025)"
size_categories:
  - 10K<n<100K
---

# Forex Factory Historical Economic Calendar Dataset (2007–2025)

A historical **Forex Factory economic calendar dataset** containing scheduled macroeconomic events, currencies, impact classifications, published actual/forecast/previous values, and event descriptions in a downloadable CSV.

**Snapshot coverage:** **2007-01-01 through 2025-04-07**. This is a historical snapshot, **not a live or continuously updated economic calendar API**.

[Browse the CSV](https://huggingface.co/datasets/Ehsanrs2/Forex_Factory_Calendar/tree/main) · [Python scraper on GitHub](https://github.com/ehsanrs2/forexfactory-scraper) · [Forex Factory calendar](https://www.forexfactory.com/calendar)

## Dataset at a glance

| Attribute | Value |
| --- | --- |
| Data | Forex Factory economic calendar events |
| Published file | [`forex_factory_cache.csv`](https://huggingface.co/datasets/Ehsanrs2/Forex_Factory_Calendar/blob/main/forex_factory_cache.csv) |
| Coverage | 2007-01-01 to 2025-04-07 |
| File format | UTF-8 CSV |
| Timestamp format | ISO 8601, with UTC offset |
| Display timezone used in the original collection | `Asia/Tehran` |
| Records | Approximately 83.4k rows, according to the Hugging Face viewer when checked in October 2026 |
| Data split | `train` (this is a dataset-viewer split name, **not** a benchmark training/validation split) |

Dates are part of the recorded data, not a promise that every calendar event in the period is present.

## Columns

| Column | Description |
| --- | --- |
| `DateTime` | Reported date and time of the economic event, with an offset |
| `Currency` | Affected currency (such as USD, EUR, GBP, JPY) |
| `Impact` | Source impact classification; may include **Non-Economic** as well as low/medium/high |
| `Event` | Calendar event title |
| `Actual` | Reported actual indicator value, when available |
| `Forecast` | Expected indicator value, when available |
| `Previous` | Previously reported indicator value, when available |
| `Detail` | Available event description and context from the source |

Numerical-looking values may contain percentages, suffixes, or other notation. Treat them as strings until you apply indicator-specific parsing.

## Quick start with pandas

```python
import pandas as pd

csv_url = (
    "https://huggingface.co/datasets/"
    "Ehsanrs2/Forex_Factory_Calendar/resolve/main/forex_factory_cache.csv"
)
df = pd.read_csv(csv_url, dtype=str)
df["DateTime"] = pd.to_datetime(df["DateTime"], utc=True, errors="coerce")
print(df[["DateTime", "Currency", "Impact", "Event"]].head())
```

You can also download the CSV from the [Files tab](https://huggingface.co/datasets/Ehsanrs2/Forex_Factory_Calendar/tree/main).

## Potential use cases

- Exploring historical macroeconomic event schedules
- Event-study research and economic calendar visualization
- Building features for financial time-series experiments
- Investigating event-driven backtesting workflows
- Teaching data cleaning and temporal data analysis

**Backtesting caution:** Do not assume this snapshot records exactly what traders knew at each historical time. Calendar fields, reported values, release timing, and text may have been updated after the event. Any point-in-time strategy needs independent checks for look-ahead bias.

## Collection and provenance

The historical dataset was originally published in April 2025. Its existing documentation describes a Selenium-based collection process with pandas processing and timezone-aware timestamps.

A separately maintained [Python scraper repository](https://github.com/ehsanrs2/forexfactory-scraper) now documents an HTML-first, incremental CSV cache workflow with saved-HTML and available export-file providers. **The present codebase and this published 2007–2025 snapshot are not guaranteed to use the same historical collection pipeline or schema.** Running the repository's scraper does not automatically update this Hugging Face dataset.

The original content source is [Forex Factory](https://www.forexfactory.com/calendar). This dataset is community-maintained and is **not affiliated with or endorsed by Forex Factory**.

## Limitations and responsible use

- This is a snapshot ending **2025-04-07**, not a live feed.
- Actual, forecast, previous, and detailed text fields can be missing.
- Event classifications and economic releases may differ across time and data revisions.
- Historical timestamps and timezones should be checked carefully, especially before temporal joins.
- No completeness or numerical-correctness guarantee is provided for financial or trading decisions.
- Verify source rights and [Forex Factory notices](https://www.forexfactory.com/notices) before reuse or redistribution, particularly for commercial purposes.

**License metadata:** The existing Hub dataset card labels this repository `mit`, which has been preserved in this proposed edit rather than changed without the publisher's authorization. That label does **not** establish rights over third-party source content; the underlying rights and redistribution terms require independent verification. The companion scraper's GPL-3.0 code license applies to the scraper code, not automatically to the source data.

## Citation

If you use this historical snapshot in research, a suggested citation is:

```bibtex
@misc{ehsanrs2_forex_factory_calendar_2025,
  author       = {Ehsanrs2},
  title        = {Forex Factory Historical Economic Calendar Dataset (2007--2025)},
  year         = {2025},
  publisher    = {Hugging Face},
  url          = {https://huggingface.co/datasets/Ehsanrs2/Forex_Factory_Calendar},
  note         = {Historical snapshot ending 2025-04-07}
}
```

For code-specific attribution, link to the [source repository](https://github.com/ehsanrs2/forexfactory-scraper) as well.