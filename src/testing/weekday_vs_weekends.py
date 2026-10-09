import pandas as pd
from read_elec_parquet import read_parquet_range
import random
import matplotlib.pyplot as plt

df = read_parquet_range(
    2023, 1,
    2023, 12
)
df = df.query("CUSTOMER_TYPE == 'Residential'")
df['DATE'] = pd.to_datetime(df['DATE'], format='%Y-%m-%d')
df['Avg_Consumptions_Unit'] = df['TOTAL_CONSUMPTION'] / df['PREMISE_COUNT']

sampled_values = random.sample(df['FSA'].dropna().unique().tolist(), 20)
df = df[df["FSA"].isin(sampled_values)]
df["Day"] = df["DATE"].dt.day_name()

df1 = df.copy()

## Each day unique
# Define the desired day-of-week order
day_order = [
    'Monday',
    'Tuesday',
    'Wednesday',
    'Thursday',
    'Friday',
    'Saturday',
    'Sunday'
]

# Calculate average consumption for each FSA × day × hour
hourly_avg = (
    df.groupby(['FSA', 'Day', 'HOUR'])['Avg_Consumptions_Unit']
      .mean()
      .reset_index()
)

# Plot one chart for each FSA
for fsa in hourly_avg['FSA'].unique():

    fsa_data = hourly_avg[hourly_avg['FSA'] == fsa]

    plt.figure(figsize=(12, 6))

    for day in day_order:
        day_data = fsa_data[fsa_data['Day'] == day]

        if not day_data.empty:
            plt.plot(
                day_data['HOUR'],
                day_data['Avg_Consumptions_Unit'],
                marker='o',
                label=day
            )

    plt.title(f'Average Hourly Consumption Profile — FSA {fsa}')
    plt.xlabel('Hour')
    plt.ylabel('Average Consumption')
    plt.xticks(range(1, 25))
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.show()

## By pricing plan:
#Tiered
tiered = df[df["PRICE_PLAN"]=="Tiered"]

hourly_avg_tiered = (
    tiered.groupby(['FSA', 'Day', 'HOUR'])['Avg_Consumptions_Unit']
      .mean()
      .reset_index()
)
for fsa in hourly_avg_tiered['FSA'].unique():

    fsa_data = hourly_avg_tiered[hourly_avg_tiered['FSA'] == fsa]

    plt.figure(figsize=(12, 6))

    for day in day_order:
        day_data = fsa_data[fsa_data['Day'] == day]

        if not day_data.empty:
            plt.plot(
                day_data['HOUR'],
                day_data['Avg_Consumptions_Unit'],
                marker='o',
                label=day
            )

    plt.title(f'Average Hourly Consumption Profile — FSA {fsa} - Tiered')
    plt.xlabel('Hour')
    plt.ylabel('Average Consumption')
    plt.xticks(range(1, 25))
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.show()

# TOU
tou = df[df["PRICE_PLAN"]=="TOU"]
hourly_avg_tou = (
    tou.groupby(['FSA', 'Day', 'HOUR'])['Avg_Consumptions_Unit']
      .mean()
      .reset_index()
)

for fsa in hourly_avg_tou['FSA'].unique():

    fsa_data = hourly_avg_tou[hourly_avg_tou['FSA'] == fsa]

    plt.figure(figsize=(12, 6))

    for day in day_order:
        day_data = fsa_data[fsa_data['Day'] == day]

        if not day_data.empty:
            plt.plot(
                day_data['HOUR'],
                day_data['Avg_Consumptions_Unit'],
                marker='o',
                label=day
            )

    plt.title(f'Average Hourly Consumption Profile — FSA {fsa} - TOU')
    plt.xlabel('Hour')
    plt.ylabel('Average Consumption')
    plt.xticks(range(1, 25))
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.show()

# Choose the FSA you want to examine
fsa = 'L5A'

# Filter to the selected FSA and Wednesday/Sunday
plot_df = df[
    (df['FSA'] == fsa) &
    (df['Day'].isin(['Wednesday', 'Sunday']))
].copy()

# Calculate average consumption for each:
# Day × Hour × Pricing Plan
avg_consumption = (
    plot_df
    .groupby(['Day', 'HOUR', 'PRICE_PLAN'])['Avg_Consumptions_Unit']
    .mean()
    .reset_index()
)

# Pivot pricing plans into columns
pivot = avg_consumption.pivot_table(
    index=['Day', 'HOUR'],
    columns='PRICE_PLAN',
    values='Avg_Consumptions_Unit'
)

# Plot Wednesday and Sunday separately
for day in ['Wednesday', 'Sunday']:

    day_data = pivot.loc[day]

    plt.figure(figsize=(12, 6))

    # Plot each pricing plan
    for plan in day_data.columns:
        plt.plot(
            day_data.index,
            day_data[plan],
            marker='o',
            label=plan
        )

    plt.title(f'Average Hourly Consumption by Pricing Plan — {fsa} — {day}')
    plt.xlabel('Hour')
    plt.ylabel('Average Consumption')
    plt.xticks(range(1, 25))
    plt.grid(True, alpha=0.3)
    plt.legend(title='Pricing Plan')
    plt.tight_layout()
    plt.show()