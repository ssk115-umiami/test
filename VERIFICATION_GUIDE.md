# Real-Data Verification Guide

Both real adapters (`BybitPublicDataAdapter`, `NyisoPowerDataAdapter`)
were built from documentation cross-checked as carefully as this
session's sandbox allowed (it blocks all exchange/vendor/government
domains — see `IMPLEMENTATION_STATUS.md`). A first real-data run against
Bybit found a live 404 — see "Round 1 finding" at the end of §1 for the
root cause and fix. NYISO has not been run against live data yet.

Nothing here should be read as a claim that either adapter works — that
is precisely what these steps determine.

---

## 1. Verify Bybit with real data

```bash
source .venv/bin/activate

python -c "
from project_factory.data.adapters.bybit_l2 import BybitPublicDataAdapter

adapter = BybitPublicDataAdapter(
    symbol='BTCUSDT',
    market='spot',
    start='2025-06-01',   # order-book archive only exists from May 2025 onward — see Round 1 finding below
    end='2025-06-02',
)
adapter.check_connectivity()   # now checks BOTH the trades and order-book endpoints
print('connectivity OK')

df = adapter.load()
print(df.shape)
print(df.columns.tolist())
print(df.head())

report = adapter.validate(df)
print(report.model_dump())
"
```

Or via the CLI, once you have a `project_spec.yaml` for a
`predictive_market_making` project (`qpf analyze-role` against
`examples/headlands_jd.txt`, then `qpf init-project` — the generated
spec uses `BybitPublicDataAdapter`'s defaults, which are now inside the
confirmed date window):

```bash
qpf run --spec projects/<id>/project_spec.yaml --stage data
```

**What "success" looks like:** `check_connectivity()` returns silently,
`load()` returns a non-empty DataFrame matching the schema in section 3
below, and `report.verified is True` (this is set automatically by
`load()` — see `project_factory/data/verification.py`). Confirm it
persisted:

```bash
python -c "
from pathlib import Path
from project_factory.data.verification import verification_status
print(verification_status(Path('data_cache/bybit_l2'), 'bybit_public_data'))
"
```

### Round 1 finding (fixed): HTTP 404 on the order-book URL

A real run reported connectivity OK but a 404 on
`https://quote-saver.bycsi.com/orderbook/BTCUSDT/2024-06-01_BTCUSDT_ob200.data.zip`.
Root-caused by cloning and reading
`github.com/nssanta/Bybit-Download-OrderBook-Trades-Klines`'s actual
downloader source and README directly (not re-guessing from search
snippets) — **two** bugs, both now fixed:

1. **Wrong URL** — missing a market-type path segment. The confirmed
   real path is `.../orderbook/spot/{SYMBOL}/{file}` (or `.../linear/...`
   for futures), not `.../orderbook/{SYMBOL}/{file}`.
2. **Wrong default date range** — that repo's own README states
   Bybit's order-book archive is *"Available From: May 2025"* (trades
   goes back to 2020, which is why that half of the original request
   worked). The adapter's old defaults (2024-06-01..03) predated the
   archive entirely and would have 404'd on the date alone even with
   the URL fixed. `BybitPublicDataAdapter.__init__` now rejects a
   `start` before 2025-05-01 with a clear `ValueError` instead of
   letting it become a confusing 404 later.

Also fixed: `check_connectivity()` previously only pinged the trades
endpoint (different host from order-book), which is exactly how a
broken order-book URL passed connectivity and only failed at `load()` —
it now checks both endpoints independently and names which one failed.

The JSONL record schema itself (see §3) needed **no change** — it was
already correct; confirmed against that same repo's `convert_to_parquet.py`
parser. Full detail in `bybit_l2.py`'s module docstring.

---

## 2. Verify NYISO with real data

```bash
source .venv/bin/activate

python -c "
from project_factory.data.adapters.nyiso import NyisoPowerDataAdapter

adapter = NyisoPowerDataAdapter(
    zone='N.Y.C.',
    start='2024-06-01',
    end='2024-06-02',
)
adapter.check_connectivity()
print('connectivity OK')

df = adapter.load()
print(df.shape)
print(df.columns.tolist())
print(df.head())

report = adapter.validate(df)
print(report.model_dump())
"
```

Or via the CLI (`qpf analyze-role` against `examples/cci_jd.txt`, then
`qpf init-project`, then):

```bash
qpf run --spec projects/<id>/project_spec.yaml --stage data
```

**What "success" looks like:** same shape as Bybit — non-empty frame,
`report.verified is True`, persisted in
`data_cache/nyiso/.verified.json`.

**Most likely failure and the fix:** the exact zone-name string in the
raw `Name` column (`N.Y.C.` is a best guess) — if this is wrong, the
error will name every zone the file actually contains (see §4), so you
can just re-run with the corrected string: `NyisoPowerDataAdapter(zone="<the correct string>", ...)`.

---

## 3. Expected schemas / sample output

### Bybit (`BybitPublicDataAdapter.load()`)

**Source archive's actual depth/frequency** (confirmed via
`github.com/nssanta/Bybit-Download-OrderBook-Trades-Klines`'s README,
cross-referencing two independent scripts in that repo): raw snapshots
carry **200 price levels per side**, refreshed roughly **every 200ms**,
archived daily from **May 2025 onward**. This adapter deliberately keeps
only the **top 5 levels** (`bid/ask_price_1..5`) — a documented v1 scope
cut, not a limitation of the source data — and reads only `snapshot`
records, not the `delta` records between them (also documented; see
`_parse_orderbook_records`'s docstring). Both are legitimate order-book
depth, not candles or trades.

One row per order-book snapshot, merged with trade aggregates:

| column | type | notes |
|---|---|---|
| `timestamp` | datetime64[ns] | snapshot time |
| `bid_price_1..5`, `ask_price_1..5` | float | top 5 of the source's 200 book levels |
| `bid_size_1..5`, `ask_size_1..5` | float | sizes at those levels |
| `trade_signed_volume` | float | net signed volume in the preceding second |
| `trade_count` | float | trade count in the preceding second |

```
   timestamp            bid_price_1  ask_price_1  bid_size_1  ...  trade_signed_volume  trade_count
0  2025-06-01 00:00:03  67420.10     67420.20     0.842       ...  -0.031                3.0
1  2025-06-01 00:00:07  67419.90     67420.00     1.204       ...   0.114                5.0
```

Raw files land in `data_cache/bybit_l2/raw/trades/` and
`data_cache/bybit_l2/raw/orderbook/`.

### NYISO (`NyisoPowerDataAdapter.load()`)

One row per hour:

| column | type | notes |
|---|---|---|
| `timestamp` | datetime64[ns] | the hour being priced |
| `da_lbmp` | float | day-ahead LBMP, $/MWh |
| `rt_lbmp` | float | real-time hourly LBMP, $/MWh |
| `da_rt_spread` | float | `da_lbmp - rt_lbmp` |
| `load_forecast` | float | ISO load forecast for the zone, MW |
| `load_forecast_published_at` | datetime64[ns] | when the forecast was published (NYISO's own "File Date") |

```
   timestamp            da_lbmp  rt_lbmp  da_rt_spread  load_forecast  load_forecast_published_at
0  2024-06-01 00:00:00  28.41    26.90    1.51          5432.0         2024-05-31 04:00:00
1  2024-06-01 01:00:00  27.85    31.20   -3.35          5210.0         2024-05-31 04:00:00
```

Raw files land in `data_cache/nyiso/raw/{damlbmp,rtlbmp,isolf}/`.

---

## 4. Reading failure messages

Both adapters raise one of four exception types
(`project_factory/data/errors.py`) instead of a raw httpx/pandas
exception — the type alone tells you which of the four things below is
wrong, no stack-trace archaeology required.

| Exception | Means | Example message | What to do |
|---|---|---|---|
| `DataSourceNetworkError` | Couldn't reach the host at all | `could not reach https://public.bybit.com/...: [connection error]` | Check your internet access / whether the host itself resolves (`curl -I <url>`) |
| `DataSourceHTTPError` | Reached it, got 4xx/5xx | `GET order-book endpoint https://quote-saver.bycsi.com/orderbook/spot/BTCUSDT/2025-06-01_BTCUSDT_ob200.data.zip returned HTTP 404` | For Bybit order-book: confirm the date is >= 2025-05-01 first (this adapter now raises `ValueError` at construction if not); a persistent 404 on an in-window date means the URL shape changed again — re-verify against a current downloader tool's source, the way this round's fix was done. For NYISO: 404 on the daily path usually means the date is outside the ~7-day retention window and the monthly-zip fallback should have engaged automatically — a persistent 404 means the dataset/filename convention changed |
| `DataSourceSchemaError` | Got a response, wrong shape | `zone 'N.Y.C.' not found in .../20240601damlbmp_zone.csv; available zones: ['CAPITL', 'CENTRL', ...]` | The error lists what WAS found — fix the adapter's assumption (zone string, column name) directly from that list |
| `DataSourceQualityError` | Parsed fine, failed a quality check | `no overlapping DA/RT rows for zone='N.Y.C.' in 2024-06-01..2024-06-02` | Usually a bad/too-narrow date range, not an adapter bug — widen it and retry |

This is deliberately the same taxonomy for both adapters (and any future
one) — you never need to remember which adapter raises what.

### Fixture-based tests for the fixed schema

`tests/test_bybit_adapter_parsing.py::test_parse_orderbook_records_handles_full_confirmed_record_shape`
uses a JSONL fixture built field-for-field from
`convert_to_parquet.py`'s `parse_record()` in the same real downloader
repo (`ts`, `cts`, `type`, nested `data.u`/`data.seq`/`data.b`/`data.a`)
— the closest available substitute for a live-captured file from inside
this sandbox (no network access to Bybit here). It is schema-accurate
against that source's own parser, not a byte-for-byte real download;
once you've run §1 successfully, consider saving one real `.data.zip`
under `tests/fixtures/` and pointing a test at it directly for a
stronger guarantee.
`tests/test_bybit_adapter_parsing.py::test_orderbook_url_includes_market_segment`
and `::test_start_date_before_orderbook_availability_window_raises` are
regression tests for the two Round 1 bugs specifically.

---

## 5. Architecture changes Milestone 4 forced

Milestone 4 was explicitly run as a generalization test — build a second
archetype (regression target, no order book, no quoting) through the
*same* orchestrator/reporter/validator, and see what breaks. Three real
bugs surfaced, all in code that looked archetype-agnostic but wasn't,
fixed before this was called done:

1. **`orchestrator._run_robustness_suite` hardcoded
   `MarketMakingStrategy(...)`** with a market-making-specific parameter
   list. Fixed by reconstructing `type(strategy)` from the actual
   instance's own parameters (`vars(strategy)`), and only sweeping
   `fee_bps`/`latency_ticks` when the strategy instance actually exposes
   that attribute — `latency_sensitivity` is correctly *absent* from the
   power archetype's robustness output rather than faked.
2. **`task_type` defaulted to `"classification"`** in
   `orchestrator.run_stage()`'s signature — silently wrong for the
   regression-target power archetype. Fixed with
   `registry.register_task_type`/`get_task_type`, resolved per-archetype
   the same way every other dependency already was.
3. **A hardcoded `"logistic_regression"` fallback** model name (used
   when a spec's model-ladder name doesn't resolve) would have crashed
   for a regression task. Replaced with a `task_type`-aware default.

One deliberate (non-bug) design split: `trading/pnl.py` now has two
result-assembly functions —`assemble_trading_result` (mark-to-market,
continuously-held inventory) for market making, and
`assemble_periodic_trading_result` (a fresh position each period against
that period's own realized outcome, no meaningful price to mark between
periods) for the power sizing strategy. They were kept separate rather
than forced into one function because mark-to-market inventory and
periodic signal-based positions are genuinely different market
structures; what's shared (and load-bearing for `reporting/memo.py`
staying archetype-agnostic) is the *output shape* both produce, via a
common `_standard_result()` helper.

Everything else — `WalkForwardValidator`, `audit_leakage`, the model
factory (`ridge`/`ols`/`gradient_boosted_tree` covered power's model
ladder with zero changes), `ExperimentRecord`/`run_walk_forward_experiment`,
the data-quality/verification machinery, the CLI commands, and the
reporter's figure/table generation — worked for `power_da_rt` completely
unchanged. `orchestrator.py` contains no archetype-name conditionals;
this is asserted directly by
`tests/test_orchestrator_power.py::test_same_orchestrator_code_serves_both_archetypes_without_branching`.
