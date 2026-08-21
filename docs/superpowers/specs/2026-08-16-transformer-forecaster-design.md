# Global Transformer Forecaster — Design Spec

Lane A of the post-hackathon deepening work: replace "forecasting is a comparison
harness over off-the-shelf methods" with a real, from-scratch, trainable model
that has to earn a place in that same harness on honest terms.

## Goal

Train one global sequence model — a small Transformer, not per-city, not per-parameter —
across all 216 (city, parameter) series in `data/processed/daily_city.parquet`, and
add it as a fifth competitor in the existing forecast bench (`ml/bench.py`), scored
on the same rolling-origin folds as `naive`, `damped_trend`, `gbt`, and `arima_plus`,
winning or losing on the same terms as everything else already there.

## Non-goals (explicitly out of scope for this spec)

- Automated retraining / drift monitoring / model versioning — that's Lane B (MLOps),
  a separate spec, built on top of this once it exists.
- Changing what the bench *serves* to users beyond adding the new method as an
  option `get_forecast()` can pick — the winner-selection logic in `ml/bench.py`
  already picks whichever method has the lowest backtest MAE per series, unchanged.
- Any change to `agents/tools.py` or the frontend beyond what's needed for the new
  method's label to render (it already handles an arbitrary method key via
  `METHOD_LABELS`).

## The core design problem, and why it's the whole point of this spec

Every existing forecaster in `ml/forecasters.py` shares one calling convention:
`forecast(train: pd.DataFrame, horizon: int) -> np.ndarray`, called once per
(city, parameter, fold) inside `backtest_series()` — a **fresh model refit
every single call**, using only that fold's `train` slice. That's correct and
cheap for a `HistGradientBoostingRegressor` (fits in milliseconds), but it is the
wrong shape for a global neural model: refitting a Transformer from scratch for
each of 216 series × 8 folds would be both computationally absurd and would
throw away the entire point of a *global* model (there'd be no cross-city weight
sharing left if every fold trains its own copy).

**Resolution: train once, offline, ahead of time — then only ever run inference
inside the bench.** A one-time training script produces a weights file; the
bench-facing forecaster function loads it lazily (cached singleton) and does a
forward pass conditioned on whatever `train` slice it's given. This matches how
a real production forecasting system actually works (train offline on a
schedule, serve inference on the hot path) and is the honest reason Lane B
(retraining triggers) is a *separate*, later piece of work — this spec produces
the thing Lane B would eventually automate.

## The leakage trap this design has to avoid

Because the model is trained once on (most of) the archive rather than refit
per fold, there is a real risk that its one-time training pass already "saw"
data that falls inside what a backtest fold pretends is the unseen future —
classic look-ahead leakage, and exactly the failure mode named as a risk when
this lane was chosen.

The fix is a **hard, global training cutoff date**, `T`, chosen once:

```
T = (latest date in daily_city.parquet) − TEST_MARGIN_DAYS
```

`TEST_MARGIN_DAYS` must be strictly greater than the span the existing bench
folds cover: `N_FOLDS * HORIZON` = `8 * 3` = 24 days (`ml/backtest.py`). Set
`TEST_MARGIN_DAYS = 45` (a deliberate margin above the 24-day minimum, not the
bare minimum, so a few days of archive-refresh drift never silently reopens the
leakage window).

Training data for the Transformer is **every city/parameter series, truncated
to dates ≤ T, with no exceptions.** The model never sees a single row dated
after `T` during training, validation-for-early-stopping, or hyperparameter
selection. Since every rolling-origin fold in the current bench config falls
within the last 24 days of each series — inside the `TEST_MARGIN_DAYS = 45`
withheld window — the model is guaranteed to be evaluating on genuinely unseen
data every time `backtest_series()` calls it, the same guarantee every other
method gets by construction.

This means: if the archive's latest date moves forward (as it does on every
data refresh) without T being recomputed and the model being retrained, the
margin shrinks. `ml/train_transformer.py` must print and assert that
`TEST_MARGIN_DAYS` still exceeds the fold span at the top of every training run,
so this can never silently regress — it's a loud failure, not a quiet one.

## Model architecture

- **Input representation, per series, per day:** the same seasonal encoding
  already used for the gradient-boosted model (`ml/features.py`'s `dow_sin`,
  `dow_cos`, `doy_sin`, `doy_cos`), plus the raw (normalized) pollutant value.
  Reusing this encoding instead of inventing a second one keeps the two feature
  pipelines legible side by side, and gives an honest, easy answer if asked "why
  these features" — it's the same seasonal representation already justified
  elsewhere in the codebase.
- **Context window:** the trailing 60 days per series, as a fixed-length input
  sequence. 60 was chosen over something longer because the shortest series in
  the archive has 153 days total (`daily_city.parquet` groupby check: min 153,
  median ~507) — 60 leaves every series enough history for multiple non-overlapping
  training windows even at the short end, without over-representing the
  long-history cities.
- **City conditioning:** a learned embedding per city (36 cities → an
  `nn.Embedding(36, d_model)`), concatenated (or added, via a projection) to
  every timestep's input before the encoder — this is the mechanism that makes
  it one *global* model instead of 36 independent ones, and it's the answer to
  "how does it share strength across cities."
- **Parameter conditioning:** same idea, a small learned embedding per pollutant
  (6 parameters), so one model handles PM2.5, PM10, NO₂, O₃, SO₂, and CO instead
  of needing six separate models.
- **Core:** a small Transformer encoder — 2–3 layers, 4 attention heads,
  `d_model` around 64, sinusoidal or learned positional encoding over the
  60-day window. Deliberately small: the goal is a real, correct, inspectable
  architecture, not parameter count.
- **Output / multi-step decoding:** direct multi-horizon output head (predict
  all `horizon` days at once from the encoder's final hidden state) rather than
  autoregressive one-step-at-a-time decoding — simpler, avoids compounding
  single-step errors across the horizon, and is easy to defend ("direct
  multi-horizon forecasting" is a real, named, legitimate strategy, not a
  simplification to hide).
- **Normalization:** per-series z-score (mean/std computed from that series'
  *training-cutoff* history only, never from validation/test rows — the same
  leakage discipline as the cutoff itself, just applied at the feature level
  too), so one shared model isn't confused by Delhi's PM2.5 living on a
  different scale than a cleaner city's.

## Training procedure

- **Framework:** PyTorch (new dependency — not currently on the resume or in
  `requirements.txt`; this is the point where that becomes true).
- **Split, all within `date ≤ T`:** a further internal rolling-origin
  validation split (reusing `ml/backtest.py`'s `make_folds` logic conceptually,
  applied *inside* the pre-T region) for early stopping and hyperparameter
  selection — never touching the post-T bench evaluation window.
- **Loss:** MAE (mean absolute error) — matching the metric the bench itself
  scores everyone on (`ml/backtest.py`'s `mae()`), so "the model was trained to
  minimize the same thing it's judged on" is literally true, not just close.
- **Early stopping:** on the internal validation split, patience-based, to
  avoid the overfitting failure mode named as the main risk of this whole lane.
- **Artifact:** trained weights saved to `ml/model_weights/transformer_forecaster.pt`,
  plus a small JSON sidecar (`ml/model_weights/transformer_forecaster.meta.json`)
  recording the training cutoff `T`, the city/parameter vocabularies (so
  inference can map names to embedding indices consistently), normalization
  stats per series, and the architecture hyperparameters — so the bench-facing
  loader never has to guess what shape of model it's loading.

## Integration into the bench

- New file `ml/transformer_forecaster.py`, exposing
  `transformer_forecast(train: pd.DataFrame, horizon: int) -> np.ndarray` —
  the exact same signature as every function in `LOCAL_FORECASTERS`
  (`ml/forecasters.py`). Internally: lazily load the cached model + meta JSON
  once per process (`functools.lru_cache`, matching the pattern already used
  for e.g. `agents/tools.py`'s cached readers), look up the series' city/parameter
  embedding indices from the meta sidecar, take the trailing 60 days of `train`,
  normalize with the *stored* per-series stats (not stats recomputed from
  `train` itself — the fold's `train` slice can be shorter than the full
  history the stored stats were computed from, and recomputing per-fold would
  reintroduce a subtle leakage-adjacent inconsistency between how the model was
  trained and how it's evaluated).
- `ml/forecasters.py` gains a fourth entry — but **not** by adding it to
  `LOCAL_FORECASTERS` directly. `LOCAL_FORECASTERS` is also used by
  `_final_forecast_rows()` and by `gbt_forecast`'s recursive per-step logic;
  the transformer forecaster doesn't need per-fold refitting the way that dict
  implies for the others. Add it as an explicit fifth call in `ml/bench.py`'s
  `run_bench()`, guarded by a `try/except` per series (a series shorter than
  60 days, or a city/parameter combo outside the training vocabulary — e.g. if
  the archive later adds a 37th city before the model is retrained — must fall
  back to being absent from that series' `scores` dict, not crash the whole
  bench run, matching how `arima_plus` is already optional per series today).
- `METHOD_LABELS` gains `"transformer": "Transformer (global, multi-city)"`.
- No change needed to `agents/tools.py`'s `get_forecast()` — it already serves
  whichever method won a series' backtest by name by reading `forecast_bench.json`,
  and already has the damped-trend fallback path for a method with no current
  forecast row (see `ml/bench.py`'s comment on `arima_plus` staleness) — the
  same fallback covers a series where the transformer was skipped.

## Files touched

**New:**
- `ml/train_transformer.py` — one-time offline training script (the thing you
  run by hand / eventually schedule, not called from the request path).
- `ml/transformer_model.py` — the `nn.Module` architecture definition, kept
  separate from the training script so the bench-facing loader can import just
  the class definition without pulling in training-only code (optimizer setup,
  argparse, etc.).
- `ml/transformer_forecaster.py` — the bench-facing `transformer_forecast()`
  inference function described above.
- `ml/model_weights/transformer_forecaster.pt` + `.meta.json` — the trained
  artifact (committed to the repo, like `benchmark/benchmark_results.json`
  already is, so the bench is reproducible without requiring a GPU to run).

**Modified:**
- `ml/bench.py` — add the transformer as a fifth scored method inside
  `run_bench()`, per-series try/except as described above.
- `requirements.txt` — add `torch`.

## Testing plan

- **Leakage guard test:** assert that `ml/train_transformer.py` raises/refuses
  to run if `TEST_MARGIN_DAYS <= N_FOLDS * HORIZON` (imported from
  `ml/backtest.py`, not hardcoded twice) — this is the single most important
  test in the whole feature, because it's the one that would otherwise fail
  silently.
- **Shape/sanity test:** `transformer_forecast()` on a real series from the
  archive returns exactly `horizon` finite, non-negative values.
- **Vocabulary-miss test:** calling `transformer_forecast()` with a city or
  parameter not in the trained vocabulary raises a specific, catchable
  exception (not a raw `KeyError` from deep inside embedding lookup) — this is
  what the per-series `try/except` in `ml/bench.py` needs to catch cleanly.
- **Integration test:** `run_bench()` on the real `daily_city.parquet` includes
  `"transformer"` in at least one series' `mae` dict, and the full bench run
  still completes for all 216 series without an unhandled exception even if the
  transformer is skipped for some of them.
- **No leakage, empirically:** as a sanity check beyond the date-math assertion,
  confirm the stored training cutoff `T` in the meta JSON is in fact ≤ every
  fold's earliest test-window start date across all series, computed once
  from the real `make_folds()` output — belt-and-suspenders on top of the
  assertion above.

## What "done" looks like for the interview story

- A trained model whose training loop, loss, validation split, and leakage
  safeguard can all be explained and defended from memory, not read off a
  slide.
- Honest bench results showing where the transformer wins and where it
  loses against naive/damped-trend/gbt/ARIMA_PLUS — a loss is not a bug to
  hide, it's the same honesty the bench already practices for every other
  method, and "here's where a from-scratch neural model didn't beat a
  three-line heuristic, and here's my hypothesis why" is a stronger answer
  than an unbroken winning streak would be.
- Attention weights from at least one real prediction, inspectable and
  plottable — the concrete artifact that turns "I built a Transformer" from
  a claim into something demonstrable in the room.
