# Shared market regime analysis

`RegimeWorkflow` creates a versioned JSON artifact that is independent of a
debate or Judge implementation. It collects three years of daily OHLCV data
and contains the full price series, two
non-overlapping regimes, comparable metrics, up to two evidence-backed reasons
per regime, event price reactions, and explicit limitations.

The result keeps calculation data and display data separate:

- `price_series`: the complete daily OHLCV series used for calculations.
- `display_series.recent_daily`: the latest 60 trading days, shown daily.
- `display_series.medium_monthly`: trading days 61 through 252, grouped monthly.
- `display_series.historical_quarterly`: data older than 252 trading days,
  grouped quarterly.
- `timeline_evidence`: verified, dated disclosures and web sources grouped into
  the same daily, monthly, and quarterly rows. Each row keeps only a small
  number of sources and links to its quote, context, and original page.

Historical evidence collection is separate from the latest-debate collector.
It uses three years of OpenDART filings as the official baseline for Korean
stocks and supplements them only with web documents whose publication dates
can be verified. Missing periods remain explicitly unsupported rather than
receiving an inferred cause.

The UI and Markdown output show this three-year series as its own section and
show the selected bull/bear regime comparison below it. Display aggregation
does not change regime detection or metric calculations.

## Reuse in another build

Copy or cherry-pick the regime feature files, then build the artifact after the
shared evidence catalog is ready:

```python
from app.regime_workflow import RegimeWorkflow
from tools.regime_context import build_regime_context
from tools.regime_store import RegimeStore

regime_analysis = RegimeWorkflow().run(
    company_name,
    financial_data["ticker"],
    evidence_catalog,
)
RegimeStore().save(company_name, regime_analysis)
regime_context = build_regime_context(regime_analysis)
```

Append `regime_context` to the common Bull/Bear input. In a Judge build, append
the same value to the Judge prompt and require it to:

- reject claims that mix values from different periods;
- distinguish verified events from market interpretations and hypotheses;
- compare absolute return, drawdown, volatility, and volume on the same basis;
- treat missing or unverified source text as a limitation;
- avoid turning temporal coincidence into proven causation.

`build_regime_context()` intentionally excludes `price_series` and
`display_series` to keep LLM input compact. Both remain in the saved JSON for
tables, charts, audits, and later evaluation.

The workflow also fetches `^KS11` for KOSPI stocks, `^KQ11` for KOSDAQ
stocks, and `^GSPC` otherwise. It records regime excess return and each event's
five-day market-adjusted reaction. Benchmark failure is non-fatal and is
recorded as a limitation.

## Detection rule

- Window: 60 trading days.
- Recent comparison: the lowest-return window ending inside the latest 120
  trading days.
- Historical comparison: the highest-return 60-day window that ends before the
  recent window begins.
- If the recent window is not negative or the historical window is not
  positive, the artifact records that limitation instead of relabeling the
  data.

This deterministic rule selects periods. The LLM only explains candidate
reasons from sources published inside each selected period.
