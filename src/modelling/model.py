import pandas as pd
import os
from read_parquet import read_parquet_range

import lightgbm as lgb

## Read in test data
test = read_parquet_range(2022,1,2024,12)

## Cleaning and averaging
# Cleaning
# Dropping any FSA with missing temperature
before = test["fsa"].nunique()
missing_fsas = set(
    test.loc[test["temp_c"].isna(), "fsa"]
)
test = test[~test["fsa"].isin(missing_fsas)]
after = test["fsa"].nunique()
print(f"FSAs removed: {before - after}")

# Dropping ULO data as shape doesn't fit with others
test = test[test['price_plan'] != "ULO"]

# Averaging consumption by premise count, weighting by price plans
test = test.groupby(
    ["fsa", "date", "hour", "customer_type"],
    as_index=False
).agg(
    total_consumption=("total_consumption", "sum"),
    premise_count=("premise_count", "sum"),
    temperature=("temp_c", "mean"),
    is_public_holiday=("is_public_holiday", "mean")
)

test["average_consumption"] = (
    test["total_consumption"] / test["premise_count"]
)
test["average_consumption"] = test["average_consumption"].astype("float32")
test = test.drop(columns=["total_consumption", "premise_count"])

# Converting date to Weekday-Weekend/Holiday split
test["day"] = (
    (test["date"].dt.dayofweek >= 5) | (test["is_public_holiday"] == 1)
).astype("int8")
test = test.drop(columns=["date", "is_public_holiday"])

# Convert customer type from string to binary (1 Residential, 2 SGS)
test["customer_type"] = test["customer_type"].map({
    "Residential": 1,
    "SGS <50kW": 2
}).astype("int8")

# Reorder
test = test[
    [
        "fsa",
        "day",
        "hour",
        "customer_type",
        "temperature",
        "average_consumption"
    ]
]
