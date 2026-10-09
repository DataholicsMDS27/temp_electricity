import numpy as np, pandas as pd
import lightgbm as lgb
from sklearn.metrics import mean_absolute_error, mean_squared_error
import sys
from pathlib import Path
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

# ---------- final fit on all of 2022-2024 ----------
final = lgb.LGBMRegressor(**{**params, "n_estimators": best_n})
final.fit(df[FEATURES], df[TARGET], categorical_feature=["fsa", "customer_type"])
final.booster_.save_model("lgbm_final.txt")

# ---------- test once on 2025-26 (set end to your last available month) ----------
te, _ = build("2025-01", "2026-06", drop_fsas=bad_fsas)
te = te[te["fsa"].isin(fsa_cats)]                       # drop FSAs unseen in training
te = to_cat(te, fsa_cats)
report("test lgbm", te[TARGET], final.predict(te[FEATURES]))