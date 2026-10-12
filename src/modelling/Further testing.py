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