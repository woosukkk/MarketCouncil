from pathlib import Path

from tools.regime_context import regime_context_payload
from tools.regime_store import RegimeStore


def test_store_round_trip_and_context_excludes_raw_prices(tmp_path: Path) -> None:
    analysis = {
        "schema_version": 1,
        "regimes": {"past_bull": {"start_date": "2025-01-01"}},
        "comparison": [],
        "reasons": {},
        "price_series": [{"date": "2025-01-01", "close": 100}],
        "limitations": [],
    }
    store = RegimeStore(tmp_path)

    store.save("테스트 기업", analysis)
    loaded = store.load_latest("테스트 기업")
    context = regime_context_payload(analysis)

    assert loaded == analysis
    assert "price_series" not in context
