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

# ---------- build training data (2022-2024) ----------
df, bad_fsas = build("2022-01", "2024-12")
fsa_cats = sorted(df["fsa"].unique())
df = to_cat(df, fsa_cats)
print(df.dtypes, f"\n{len(df):,} rows, {df.memory_usage(deep=True).sum()/1e9:.2f} GB")

# ---------- time-based split: tune on 2022-23, validate on 2024 ----------
tr = df[df["ym"] <= 202312]
va = df[df["ym"] >= 202401]
SAMPLE_FRAC = None                 # e.g. 0.1 for a quick timing run
if SAMPLE_FRAC:
    tr = tr.sample(frac=SAMPLE_FRAC, random_state=0)

params = dict(
    objective="regression", learning_rate=0.05, n_estimators=5000,
    num_leaves=63, max_depth=-1, min_child_samples=500,
    subsample=0.7, subsample_freq=1, colsample_bytree=1.0,
    reg_lambda=5.0, max_bin=511, cat_smooth=20, min_data_per_group=200,
    n_jobs=10, random_state=0, verbose=-1,
)

model = lgb.LGBMRegressor(**params)
model.fit(
    tr[FEATURES], tr[TARGET],
    eval_set=[(va[FEATURES], va[TARGET])],
    categorical_feature=["fsa", "customer_type"],
    callbacks=[lgb.early_stopping(100), lgb.log_evaluation(100)],
)
best_n = model.best_iteration_

# ---------- baseline: mean by fsa/customer_type/day/hour, ignoring temperature ----------
keys = ["fsa", "customer_type", "day", "hour"]
base = tr.groupby(keys, observed=True)[TARGET].mean().rename("base").reset_index()
vb = va.merge(base, on=keys, how="left")
vb["base"] = vb["base"].fillna(float(tr[TARGET].mean()))

def report(name, y, p):
    print(f"{name:10s} MAE={mean_absolute_error(y, p):.4f}  "
          f"RMSE={np.sqrt(mean_squared_error(y, p)):.4f}")

report("baseline", vb[TARGET], vb["base"])
pred_va = model.predict(va[FEATURES])
report("lightgbm", va[TARGET], pred_va)
for ct in [1, 2]:                                       # check each customer type separately
    m = (va["customer_type"] == ct).to_numpy()
    report(f"  type {ct}", va.loc[m, TARGET], pred_va[m])

## SGS vs Res tests:
va = va.assign(pred=pred_va, base=vb["base"].to_numpy())
va["t_bin"] = pd.cut(va["temperature"], [-50, -15, -5, 5, 15, 25, 30, 50])
out = va.groupby("t_bin", observed=True).apply(
    lambda g: pd.Series({
        "n": len(g),
        "baseline_rmse": np.sqrt(((g[TARGET] - g["base"])**2).mean()),
        "lgbm_rmse": np.sqrt(((g[TARGET] - g["pred"])**2).mean()),
    }))
print(out)

va = va.assign(pred=pred_va, base=vb["base"].to_numpy())
for ct in [1, 2]:
    g = va[va["customer_type"] == ct]
    print(ct, f"mean={g[TARGET].mean():.3f}",
          f"baseline MAE={(g[TARGET]-g['base']).abs().mean():.4f}",
          f"lgbm MAE={(g[TARGET]-g['pred']).abs().mean():.4f}",
          f"WAPE={(g[TARGET]-g['pred']).abs().sum()/g[TARGET].sum():.1%}")

# ---------- final fit on all of 2022-2024 ----------
final = lgb.LGBMRegressor(**{**params, "n_estimators": best_n})
final.fit(df[FEATURES], df[TARGET], categorical_feature=["fsa", "customer_type"])
final.booster_.save_model("lgbm_final.txt")

# Further testing
## Build grid to predict:
TEMP_MIN, TEMP_MAX = -30, 35          # adjust to the range you actually observed
temps = np.arange(TEMP_MIN, TEMP_MAX + 1, dtype="float32")
n_temps = len(temps)

idx = pd.MultiIndex.from_product(
    [fsa_cats, [1, 2], [0, 1], range(1, 25), temps],       # temperature varies fastest
    names=["fsa", "customer_type", "day", "hour", "temperature"],
)
grid = idx.to_frame(index=False)
grid["fsa"] = pd.Categorical(grid["fsa"], categories=fsa_cats)
grid["customer_type"] = pd.Categorical(grid["customer_type"], categories=[1, 2])
grid["day"] = grid["day"].astype("int8")
grid["hour"] = grid["hour"].astype("int8")
grid["temperature"] = grid["temperature"].astype("float32")

grid["pred"] = final.predict(grid[FEATURES]).astype("float32")
grid.to_parquet("grid_predictions.parquet", index=False)
print(f"{len(grid):,} rows")           # about 518 FSAs x 2 x 2 x 24 x 66, roughly 3.3 million

# Curves for a handful of FSAs
rng = np.random.default_rng(0)
picks = [rng.choice([f for f in fsa_cats if f.startswith(p)])
         for p in "KLMNP" if any(f.startswith(p) for f in fsa_cats)]
HOURS = [4, 9, 14, 19]                 # overnight, morning, afternoon, evening
CT_NAME = {1: "Residential", 2: "SGS"}

def plot_fsa(fsa, hours=HOURS):
    sub = grid[grid["fsa"] == fsa]
    fig, axes = plt.subplots(len(hours), 2, figsize=(10, 2.6 * len(hours)), sharex=True)
    for j, ct in enumerate([1, 2]):
        for i, h in enumerate(hours):
            ax = axes[i, j]
            for day, label in [(0, "weekday"), (1, "weekend/holiday")]:
                g = sub[(sub["customer_type"] == ct) & (sub["day"] == day) & (sub["hour"] == h)]
                ax.plot(g["temperature"], g["pred"], label=label)
            ax.set_title(f"{CT_NAME[ct]}, hour {h}", fontsize=9)
            ax.grid(alpha=0.3)
            if j == 0:
                ax.set_ylabel("predicted avg consumption")
            if i == 0 and j == 0:
                ax.legend(fontsize=8)
    for ax in axes[-1]:
        ax.set_xlabel("temperature (°C)")
    fig.suptitle(f"FSA {fsa}")
    fig.tight_layout()
    fig.savefig(f"curves_{fsa}.png", dpi=120)
    plt.show()

for f in picks:
    plot_fsa(f)

# Daily profiles @ fixed temps
def plot_profiles(fsa, ct, temps_to_show=(-10, 15, 28)):
    sub = grid[(grid["fsa"] == fsa) & (grid["customer_type"] == ct)]
    fig, axes = plt.subplots(1, len(temps_to_show), figsize=(12, 3.2), sharey=True)
    for ax, t in zip(axes, temps_to_show):
        for day, label in [(0, "weekday"), (1, "weekend/holiday")]:
            g = sub[(sub["day"] == day) & (sub["temperature"] == t)].sort_values("hour")
            ax.plot(g["hour"], g["pred"], label=label)
        ax.set_title(f"{CT_NAME[ct]} at {t}°C", fontsize=9)
        ax.set_xlabel("hour")
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("predicted avg consumption")
    axes[0].legend(fontsize=8)
    fig.suptitle(f"FSA {fsa}")
    fig.tight_layout()
    plt.show()

for f in picks:
    plot_profiles(f, ct=1)

# Automatic checks across all curves
arr = grid["pred"].to_numpy().reshape(-1, n_temps)          # one row per curve
meta = grid.iloc[::n_temps][["fsa", "customer_type", "day", "hour"]].reset_index(drop=True)

# direction changes, ignoring tiny moves (under 0.5% of the curve's mean)
d = np.diff(arr, axis=1)
d[np.abs(d) < 0.005 * arr.mean(axis=1, keepdims=True)] = 0
s = np.sign(d)
pos = np.where(s != 0, np.arange(s.shape[1]), 0)
np.maximum.accumulate(pos, axis=1, out=pos)
last = np.take_along_axis(s, pos, axis=1)                   # last nonzero direction so far
prev = np.concatenate([np.zeros((s.shape[0], 1)), last[:, :-1]], axis=1)
meta["changes"] = ((s != 0) & (prev != 0) & (s != prev)).sum(axis=1)

# roughness: average size of second differences relative to the curve's level
meta["rough"] = np.abs(np.diff(arr, 2, axis=1)).mean(axis=1) / arr.mean(axis=1)

# where each curve bottoms out
amin = arr.argmin(axis=1)
meta["t_min"] = temps[amin]
meta["min_at_edge"] = (amin == 0) | (amin == n_temps - 1)

print(meta["changes"].value_counts().sort_index())          # 0 = monotone, 1 = U shape
print(meta["rough"].describe())
print(meta.groupby(["customer_type", "day"])["t_min"].describe())
print(meta.groupby("customer_type")["min_at_edge"].mean())

worst = meta.sort_values("rough", ascending=False).head(6)
fig, axes = plt.subplots(2, 3, figsize=(12, 6))
for ax, (i, r) in zip(axes.ravel(), worst.iterrows()):
    ax.plot(temps, arr[i])
    ax.set_title(f"{r.fsa} ct{int(r.customer_type)} day{int(r.day)} h{int(r.hour)}", fontsize=9)
fig.tight_layout()
plt.show()

## Finding out where roughness from 4 comes from:
meta["wiggly"] = meta["changes"] >= 3
print(meta.groupby("customer_type")["wiggly"].mean().round(3))
print(meta.groupby("day")["wiggly"].mean().round(3))
print(meta.groupby("hour")["wiggly"].mean().round(2).to_string())

dd = np.abs(np.diff(arr, 2, axis=1)) / arr.mean(axis=1, keepdims=True)
t_mid = temps[1:-1]
for name, m in [("cold (< -10)", t_mid < -10),
                ("middle (-10 to 25)", (t_mid >= -10) & (t_mid <= 25)),
                ("hot (> 25)", t_mid > 25)]:
    print(f"{name:20s} mean relative roughness = {dd[:, m].mean():.4f}")

## Smooth each curve and recheck
def count_changes(a, rel_thresh=0.005):
    d = np.diff(a, axis=1)
    d[np.abs(d) < rel_thresh * a.mean(axis=1, keepdims=True)] = 0
    s = np.sign(d)
    pos = np.where(s != 0, np.arange(s.shape[1]), 0)
    np.maximum.accumulate(pos, axis=1, out=pos)
    last = np.take_along_axis(s, pos, axis=1)
    prev = np.concatenate([np.zeros((s.shape[0], 1)), last[:, :-1]], axis=1)
    return ((s != 0) & (prev != 0) & (s != prev)).sum(axis=1)

#arr_s = np.clip(savgol_filter(arr, window_length=9, polyorder=2, axis=1, mode="interp"), 0, None)
arr_s = np.clip(savgol_filter(arr, window_length=9, polyorder=2, axis=1, mode="nearest"), 0, None)
ch = count_changes(arr_s)
print(pd.Series(ch).value_counts().sort_index().head(10))
print("share with >=3 turns:", (ch >= 3).mean().round(3), " (before:", (meta["changes"] >= 3).mean().round(3), ")")

## Comparing pre and post smoothness from above
HOURS_CHECK = [4, 7, 14, 19]   # overnight, the roughest morning hour, afternoon, evening
DAY_CHECK = 0                  # 0 = weekday, 1 = weekend/holiday
EDGE = 4                       # half of the 9-point smoothing window

def row_index(fsa, ct, day, hour):
    m = ((meta["fsa"] == fsa) & (meta["customer_type"] == ct)
         & (meta["day"] == day) & (meta["hour"] == hour))
    return int(np.flatnonzero(m.to_numpy())[0])

def compare_fsa(fsa, hours=HOURS_CHECK, day=DAY_CHECK):
    fig, axes = plt.subplots(len(hours), 2, figsize=(10, 2.6 * len(hours)), sharex=True)
    for j, ct in enumerate([1, 2]):
        for i, h in enumerate(hours):
            ax = axes[i, j]
            k = row_index(fsa, ct, day, h)
            raw, sm = arr[k], arr_s[k]
            ax.plot(temps, raw, color="lightgray", lw=2.0, label="raw")
            ax.plot(temps, sm, color="tab:red", lw=1.2, label="smoothed")
            ax.axvspan(temps[0], temps[EDGE], color="gold", alpha=0.25)
            ax.axvspan(temps[-EDGE - 1], temps[-1], color="gold", alpha=0.25)
            gap = np.abs(sm - raw).max() / raw.mean()
            ax.set_title(f"{CT_NAME[ct]}, hour {h}  (max gap {gap:.1%})", fontsize=9)
            ax.grid(alpha=0.3)
            if j == 0:
                ax.set_ylabel("predicted avg consumption")
            if i == 0 and j == 0:
                ax.legend(fontsize=8)
    for ax in axes[-1]:
        ax.set_xlabel("temperature (°C)")
    day_label = "weekday" if day == 0 else "weekend/holiday"
    fig.suptitle(f"FSA {fsa}, {day_label}")
    fig.tight_layout()
    fig.savefig(f"smooth_check_{fsa}_day{day}.png", dpi=120)
    plt.show()

for f in picks:
    compare_fsa(f)

# optional: the same check for weekends
# compare_fsa(picks[0], day=1)

# ---------- test once on 2025-26 (set end to your last available month) ----------
te, _ = build("2025-01", "2026-06", drop_fsas=bad_fsas)
te = te[te["fsa"].isin(fsa_cats)]                       # drop FSAs unseen in training
te = to_cat(te, fsa_cats)
report("test lgbm", te[TARGET], final.predict(te[FEATURES]))