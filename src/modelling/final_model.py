import numpy as np, pandas as pd
import lightgbm as lgb
from sklearn.metrics import mean_absolute_error, mean_squared_error
import sys
from pathlib import Path
import matplotlib.pyplot as plt
from scipy.signal import savgol_filter
sys.path.insert(0, str(Path.cwd() / "src/reading_cleaning"))
from read_parquet import read_parquet_range

CT_MAP = {"Residential": 1, "SGS <50kW": 2}
FEATURES = ["fsa", "day", "hour", "customer_type", "temperature"]
TARGET = "average_consumption"

def build(start, end, drop_fsas=frozenset()):
    parts = []
    for p in pd.period_range(start, end, freq="M"):
        raw = read_parquet_range(p.year, p.month, p.year, p.month)
        raw = raw[(raw["price_plan"] != "ULO") & (~raw["fsa"].isin(drop_fsas))]
        raw = raw.assign(temp_missing=raw["temp_c"].isna())

        g = (raw.groupby(["fsa", "date", "hour", "customer_type"], as_index=False)
                .agg(total_consumption=("total_consumption", "sum"),
                     premise_count=("premise_count", "sum"),
                     temperature=("temp_c", "mean"),
                     temp_missing=("temp_missing", "max"),
                     is_public_holiday=("is_public_holiday", "max")))
        del raw

        g[TARGET] = (g["total_consumption"] / g["premise_count"]).astype("float32")
        g["day"] = ((g["date"].dt.dayofweek >= 5) | (g["is_public_holiday"] == 1)).astype("int8")
        g["ym"] = (g["date"].dt.year * 100 + g["date"].dt.month).astype("int32")  # split key only
        g["customer_type"] = g["customer_type"].map(CT_MAP)
        assert g["customer_type"].notna().all(), "unexpected customer_type value"
        g["customer_type"] = g["customer_type"].astype("int8")
        g["hour"] = g["hour"].astype("int8")
        g["temperature"] = g["temperature"].astype("float32")
        g = g.drop(columns=["date", "total_consumption", "premise_count", "is_public_holiday"])
        parts.append(g)

    df = pd.concat(parts, ignore_index=True)
    del parts

    n0 = len(df)
    df = df[np.isfinite(df[TARGET])]                      # zero-premise rows
    print(f"rows dropped for non-finite target: {n0 - len(df)}")

    bad = set(df.loc[df["temp_missing"], "fsa"].unique())  # FSAs with any missing temperature
    df = df[~df["fsa"].isin(bad)].drop(columns="temp_missing")
    print(f"FSAs removed for missing temperature: {len(bad)}")
    return df.reset_index(drop=True), bad

def to_cat(df, fsa_cats):
    df["fsa"] = pd.Categorical(df["fsa"], categories=fsa_cats)
    df["customer_type"] = pd.Categorical(df["customer_type"], categories=[1, 2])
    return df

df, bad_fsas = build("2022-01", "2026-05")
fsa_cats = sorted(df["fsa"].unique())
df = to_cat(df, fsa_cats)
print(df.dtypes, f"\n{len(df):,} rows, {df.memory_usage(deep=True).sum()/1e9:.2f} GB")

params = dict(
    objective="regression", learning_rate=0.05, n_estimators=5000,
    num_leaves=63, max_depth=-1, min_child_samples=500,
    subsample=0.7, subsample_freq=1, colsample_bytree=1.0,
    reg_lambda=5.0, max_bin=511, cat_smooth=20, min_data_per_group=200,
    n_jobs=10, random_state=0, verbose=-1,
)
best_n = 2435
def report(name, y, p):
    print(f"{name:10s} MAE={mean_absolute_error(y, p):.4f}  "
          f"RMSE={np.sqrt(mean_squared_error(y, p)):.4f}")

final = lgb.LGBMRegressor(**{**params, "n_estimators": best_n})
final.fit(df[FEATURES], df[TARGET], categorical_feature=["fsa", "customer_type"])
final.booster_.save_model("lgbm_final.txt")

## Fitting the grid
# ---------- settings ----------
T_LO, T_HI = -30, 30                # slider range shown in the app
PAD_LO, PAD_HI = -37, 35            # wider grid, matching the range in your data
temps_wide = np.arange(PAD_LO, PAD_HI + 1, dtype="float32")
n_wide = len(temps_wide)
lo = int(np.flatnonzero(temps_wide == T_LO)[0])
hi = int(np.flatnonzero(temps_wide == T_HI)[0]) + 1
temps = temps_wide[lo:hi]           # displayed temperatures
n_temps = len(temps)

# ---------- build the grid (temperature varies fastest) ----------
idx = pd.MultiIndex.from_product(
    [fsa_cats, [1, 2], [0, 1], range(1, 25), temps_wide],
    names=["fsa", "customer_type", "day", "hour", "temperature"],
)
grid = idx.to_frame(index=False)
grid["fsa"] = pd.Categorical(grid["fsa"], categories=fsa_cats)
grid["customer_type"] = pd.Categorical(grid["customer_type"], categories=[1, 2])
grid["day"] = grid["day"].astype("int8")
grid["hour"] = grid["hour"].astype("int8")
grid["temperature"] = grid["temperature"].astype("float32")
print(f"{len(grid):,} grid rows")

# ---------- predict ----------
pred = final.predict(grid[FEATURES]).astype("float32")

curves = pred.reshape(-1, n_wide)   # one row per curve
meta = (grid.iloc[::n_wide][["fsa", "customer_type", "day", "hour"]]
            .reset_index(drop=True))
assert len(meta) == curves.shape[0]
del grid, pred

# ---------- smooth on the wide grid, then crop to the slider range ----------
curves_s = np.clip(
    savgol_filter(curves, window_length=9, polyorder=2, axis=1, mode="nearest"),
    0, None,
).astype("float32")

arr   = curves[:, lo:hi]            # raw predictions, -30 to +30
arr_s = curves_s[:, lo:hi]          # smoothed predictions, -30 to +30

# ---------- long format output ----------
out = meta.loc[meta.index.repeat(n_temps)].reset_index(drop=True)
out["temperature"] = np.tile(temps, len(meta))
out["pred_raw"] = arr.ravel()
out["pred"] = arr_s.ravel()
out.to_parquet("grid_predictions.parquet", index=False)

# ---------- sanity checks ----------
print(f"{len(out):,} rows, {len(meta):,} curves, temps {temps[0]:.0f} to {temps[-1]:.0f}")
print("NaNs:", int(np.isnan(arr_s).sum()),
      "| curves touching zero:", int((arr_s.min(axis=1) == 0).sum()))
gap = np.abs(arr_s - arr).max(axis=1) / arr.mean(axis=1)
print(f"largest smoothed-vs-raw gap: {gap.max():.1%}, median: {np.median(gap):.1%}")