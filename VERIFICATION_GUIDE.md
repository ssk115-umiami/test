# Real-Data Verification Guide

Both real adapters (`BybitPublicDataAdapter`, `NyisoPowerDataAdapter`)
were built from documentation cross-checked as carefully as this
session's sandbox allowed (it blocks all exchange/vendor/government
domains — see `IMPLEMENTATION_STATUS.md`). Real-data runs against Bybit
have found and fixed three issues so far — an order-book 404 (Round 1), a
trades schema mismatch (Round 2), and a catastrophic order-book
under-sampling bug (Round 3, only 2 rows for a full day) — all in §1
below. NYISO has not been run against live data yet.

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
`load()` returns a DataFrame matching the schema in section 3 below with
roughly one row per `sampling_interval_ms` across the requested span
(**~86,400 rows for one day at the 1000ms default** — not a handful), and
`report.verified is True`. As of Round 3, `verified` is **not** set just
because `load()` parsed without exceptions — `validate()` runs
`_orderbook_output_sanity()` (row count vs. expected, sampling cadence,
crossed-book count, nonpositive-size count) and only calls
`mark_verified()` if all four pass; see the Round 3 finding below for
exactly what a failing run looks like. Confirm it persisted:

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

### Round 2 finding (fixed): trades `DataSourceSchemaError`

Verification progressed past Round 1 and reached real trades data, which
failed with `could not find side/size columns in trades data` against
the actual observed columns `['id', 'timestamp', 'price', 'volume',
'side', 'rpi']`. Root-caused by cloning
**`github.com/bybit-exchange/docs`** — Bybit's own official API docs
source repo, not a third party — and reading
`docs/v5/market/recent-trade.mdx` directly:

- **`volume` is the size column** (the archived CSV's name for what the
  live API calls `size`) — now accepted alongside `size`/`qty`/`quantity`.
  Confirmed **denominated in the base asset** (BTC for BTCUSDT) by that
  doc's own worked example (price=16618.49, size=0.00012 → ~$2 notional,
  only sensible in base units).
- **`side` values are exactly `Buy`/`Sell`**, documented as *"Side of
  taker"* (the aggressor) — this confirms the existing sign convention
  (`Buy` = **+size**, `Sell` = **-size**, i.e. positive signed volume =
  net aggressive buying pressure) was already correct. Unrecognized
  values now raise `DataSourceSchemaError` naming them, instead of
  silently contributing zero.
- **`rpi`** is the archived name for the live API's `isRPITrade` — a
  flag for Bybit's Retail Price Improvement liquidity program (Feb
  2025), unrelated to direction or size. **Safely ignored** — confirmed
  by the docs, not assumed.
- **`id`** is the archived name for `execId`, an identifier, unused here.
- **Timestamp units** were not directly confirmed for the archived
  CSV's `timestamp` column specifically (the live API's own field is
  named `time`, in milliseconds — a different name, so not guaranteed
  to share the convention). `_parse_trade_timestamps` now infers
  seconds/milliseconds/microseconds from magnitude rather than assuming,
  and raises `DataSourceSchemaError` on an implausible magnitude instead
  of silently mis-parsing. All Bybit timestamps are UTC (exchange-wide
  convention).

**Updated one-day local verification command** (same as before, dates
already reflect Round 1's fix — re-run this to confirm Round 2):

```bash
source .venv/bin/activate

python -c "
from project_factory.data.adapters.bybit_l2 import BybitPublicDataAdapter

adapter = BybitPublicDataAdapter(
    symbol='BTCUSDT',
    market='spot',
    start='2025-06-01',
    end='2025-06-01',
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

### Round 3 finding (fixed): only 2 rows for a full day

A real run succeeded syntactically — no exception, `verified` got set —
but returned `df.shape == (2, 23)`, with timestamps
`2025-06-01 00:00:00.948` and `2025-06-02 00:00:00.947`. Not remotely
usable for a market-making dataset. Root cause: the adapter only ever
kept `type == "snapshot"` records and silently discarded every `delta`
record. Bybit's archive apparently contains very few raw snapshots per
day — the book is otherwise conveyed almost entirely through `delta`
messages — so nearly the whole day was being thrown away. This had been
flagged in the Round 1 docstring as a scope-cut ("delta reconstruction
remains a documented, not-yet-built extension"); it turned out to be the
actual bug, not an optional refinement.

**Fix — real order-book reconstruction**, implemented per Bybit's
documented protocol (cloned `bybit-exchange/docs`,
`v5/websocket/public/orderbook.mdx`) and cross-checked against Bybit's
own officially-linked reference implementation (pybit's
`_process_delta_orderbook`, fetched at the exact commit that repo's FAQ
links to):

- Every `snapshot` fully **replaces** the book (not just the first one).
- Every `delta`, applied in sequence: `size == 0` **deletes** that price
  level; otherwise it **inserts or updates** it. Levels are kept
  unordered internally and sorted only when top-of-book is read — the
  reference implementation confirms delta entries are not necessarily
  kept sorted.
- `seq`/`u` are tracked as **diagnostics only** (a non-increasing `seq`
  between consecutive deltas is counted as a "sequence anomaly"; a
  non-initial snapshot is counted as a "reset") — Bybit's docs do not
  commit to a strict +1-per-message increment, so nothing assumes one.

The reconstructed book's top-5 state is then **sampled on a fixed grid**
(`sampling_interval_ms`, constructor argument, default
`DEFAULT_SAMPLING_INTERVAL_MS = 1000`) rather than emitted on every raw
update — Level 200 pushes are documented at ~100ms native frequency, so
emitting every update would be ~864,000 rows/symbol/day, far more
resolution than this archetype's seconds-scale prediction horizon needs.
1000ms also matches `_aggregate_trades_to_seconds`'s own 1-second
buckets. **Lookahead safety**: for grid point `g`, every record with
timestamp `<= g` is applied *before* the sample for `g` is taken — a
message that arrives strictly after `g` cannot leak into a sample labeled
`g`.

**On the `2025-06-02 00:00:00.947` boundary timestamp**: confirmed (by
reading `_dates()`) that `start == end == "2025-06-01"` fetches exactly
one file — `pd.date_range` with equal start/end yields a single date —
so this was never a date-range bug fetching a second day. The record must
be embedded inside that one file, ~1ms past the first record 24h prior;
the most plausible explanation is a boundary/closing record included for
continuity into the next day's stream, a common daily-archive convention
— this could not be independently confirmed by inspecting raw bytes from
this sandbox (no Bybit network access here). The reconstruction does not
assume midnight-to-midnight bounds, so this record is naturally included
as the tail of one extra sample rather than needing special-case
handling.

**`validate()` no longer trusts a clean parse.** It now calls
`_orderbook_output_sanity(df, sampling_interval_ms, expected_span_ms)`,
which checks:

| check | fails when |
|---|---|
| `row_count_ok` | rows < 50% of `expected_span_ms / sampling_interval_ms` |
| `cadence_ok` | median inter-row gap deviates from `sampling_interval_ms` by more than 50% |
| `crossed_book_ok` | more than 1% of rows have `bid_price_1 >= ask_price_1` |
| `nonpositive_size_ok` | any row has `bid_size_1 <= 0` or `ask_size_1 <= 0` |

`mark_verified()` is only called if all four pass (`sanity["sane"]`).
This is exactly the check that would have caught the 2-row result
directly — `2 / 86400 = 0.00002 « 0.5`, so `row_count_ok` would have been
`False` and the dataset would never have been marked verified. The
sanity result and the reconstruction event counts (`n_snapshots`,
`n_deltas`, `n_resets`, `n_deltas_before_snapshot`,
`n_sequence_anomalies`, `n_malformed`) are both appended to the returned
`DataQualityReport.notes`, so a failing run tells you *why* it failed
without re-running with extra logging.

**Updated one-day local verification command** (unchanged shape from
Round 2 — same command, now expect ~86,400 rows instead of 2):

```bash
source .venv/bin/activate

python -c "
from project_factory.data.adapters.bybit_l2 import BybitPublicDataAdapter

adapter = BybitPublicDataAdapter(
    symbol='BTCUSDT',
    market='spot',
    start='2025-06-01',
    end='2025-06-01',
)
adapter.check_connectivity()
print('connectivity OK')

df = adapter.load()
print('shape:', df.shape)
print('timestamp min/max:', df['timestamp'].min(), df['timestamp'].max())
print('median sampling interval (ms):', df['timestamp'].diff().median() / __import__('pandas').Timedelta(milliseconds=1))
print('bid>=ask violations:', int((df['bid_price_1'] >= df['ask_price_1']).sum()))
print('nonpositive bid size:', int((df['bid_size_1'] <= 0).sum()))
print('nonpositive ask size:', int((df['ask_size_1'] <= 0).sum()))
print('reconstruction diagnostics:', adapter._last_orderbook_diagnostics)
print(df.head())
print(df.tail())

report = adapter.validate(df)
print('verified:', report.verified)
print(report.model_dump())
"
```

Please report back: **row count, timestamp min/max, median sampling
interval, bid<ask violation count, nonpositive-size count,
`adapter._last_orderbook_diagnostics` (sequence-gap/reset counts), and
the first/last 5 rows** — this is what confirms Round 3's fix against
real data (this sandbox cannot reach Bybit to confirm it directly).

### Preserving a real fixture once this succeeds

Every real network fetch writes its raw bytes to
`adapter.raw_trades_dir` (`data_cache/bybit_l2/raw/trades/`) and
`adapter.raw_orderbook_dir` (`data_cache/bybit_l2/raw/orderbook/`)
**before** any parsing, using Bybit's own filenames, and nothing in the
adapter ever deletes them. Once §1's command succeeds:

```bash
mkdir -p tests/fixtures/bybit
cp data_cache/bybit_l2/raw/trades/BTCUSDT_2025-06-01.csv.gz tests/fixtures/bybit/
cp data_cache/bybit_l2/raw/orderbook/2025-06-01_BTCUSDT_ob200.data.zip tests/fixtures/bybit/
```

Those two files are real, byte-for-byte Bybit data — a stronger fixture
than the schema-accurate-but-constructed ones currently in
`tests/test_bybit_adapter_parsing.py`. Point a new test at them directly
(read + gunzip / read + unzip, then call `_parse_trades_csv_gz` /
`_parse_orderbook_zip` on the path) once you've copied them in.

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
cross-referencing two independent scripts in that repo, and Bybit's own
`v5/websocket/public/orderbook.mdx`): raw snapshots carry **200 price
levels per side**; the full stream (snapshot + delta) refreshes at up to
**100ms**, archived daily from **May 2025 onward**. This adapter
reconstructs the full book from every `snapshot` and `delta` record (see
the Round 3 finding above — an earlier version only read `snapshot`
records and this was the root cause of a 2-rows-per-day bug), then keeps
the **top 5 levels** (`bid/ask_price_1..5`) sampled at a fixed
`sampling_interval_ms` (default 1000ms) — a documented v1 scope choice
(depth and cadence), not a limitation of the source data, which is
genuine L2 order-book information throughout, not candles or trades.

One row per sampling-grid point (default: one per second), merged with
trade aggregates:

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

`tests/test_bybit_adapter_parsing.py::test_reconstruct_and_sample_orderbook_applies_deltas_before_snapshot_grid_point`
and `::test_reconstruct_and_sample_orderbook_does_not_look_ahead` are the
Round 3 regression tests — they build a small synthetic snapshot+delta
stream (schema-accurate, not a live capture — no network access to Bybit
from this sandbox) and confirm the reconstruction applies deltas before
sampling and never leaks a future delta into an earlier grid point.
`::test_orderbook_output_sanity_flags_the_round_3_two_row_failure`
reproduces the exact real-world failure shape (2 rows for a full day) and
asserts the new sanity gate rejects it. Once you've run §1 successfully,
consider saving one real `.data.zip` under `tests/fixtures/` and pointing
a test at it directly for a stronger guarantee than a constructed
fixture.
`tests/test_bybit_adapter_parsing.py::test_orderbook_url_includes_market_segment`
and `::test_start_date_before_orderbook_availability_window_raises` are
regression tests for the two Round 1 bugs specifically; the trades-schema
tests (`test_aggregate_trades_to_seconds_matches_real_observed_bybit_schema`,
`::test_aggregate_trades_to_seconds_raises_on_unrecognized_side_value`)
cover Round 2.

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
