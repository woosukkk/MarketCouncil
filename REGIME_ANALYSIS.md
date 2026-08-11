# Shared market regime analysis

`RegimeWorkflow` creates a versioned JSON artifact that is independent of a
debate or Judge implementation. It contains the full price series, two
non-overlapping regimes, comparable metrics, up to two evidence-backed reasons
per regime, event price reactions, and explicit limitations.

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

`build_regime_context()` intentionally excludes `price_series` to keep LLM
input compact. The complete series remains in the saved JSON for tables,
charts, audits, and later evaluation.

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
