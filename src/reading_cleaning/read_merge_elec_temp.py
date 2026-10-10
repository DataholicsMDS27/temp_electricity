from pathlib import Path
import pandas as pd
import requests

PROCESSED_DIR = Path(
r"C:\Users\jonah\Desktop\personalProjects\temp_electricity\data\raw"
)

MERGED_DIR = PROCESSED_DIR.parent / "merged"

# ---------------------------------------------------------
# Public holidays
# ---------------------------------------------------------
def get_ontario_holidays(start_year: int, end_year: int) -> pd.DataFrame:
    """
    Retrieve Ontario public holidays from the Canada Holidays API
    for the requested range of years.
    """
    holidays = []

    for year in range(start_year, end_year + 1):
        url = "https://canada-holidays.ca/api/v1/provinces/ON"

        response = requests.get(
            url,
            params={"year": year},
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()
        province = data.get("province", data)

        for holiday in province["holidays"]:
            holidays.append({
                "DATE": pd.Timestamp(holiday["date"]),
                "HOLIDAY": holiday["nameEn"],
            })

    return pd.DataFrame(holidays).drop_duplicates(
        subset=["DATE", "HOLIDAY"]
    )

def read_parquet_range(
start_year: int,
start_month: int,
end_year: int,
end_month: int,
) -> None:
    """
    Read monthly electricity and temperature Parquet files,
    merge them, and save each month separately.

    ```
    Example:
        read_parquet_range(2023, 1, 2023, 12)

    Saves:
        data/merged/2023-01-merged.parquet
        data/merged/2023-02-merged.parquet
        ...
    """

    # Create output directory if it doesn't exist
    MERGED_DIR.mkdir(parents=True, exist_ok=True)
    # Generate public holidays for the requested years
    holidays_df = get_ontario_holidays(start_year, end_year)
    holiday_dates = set(holidays_df["DATE"])


    for year in range(start_year, end_year + 1):
        first_month = start_month if year == start_year else 1
        last_month = end_month if year == end_year else 12

        for month in range(first_month, last_month + 1):
            year_month = f"{year}{month:02d}"
            year_month_temp = f"{year}-{month:02d}-temp"
            year_month_merged = f"{year}-{month:02d}-merged"

            # Input file paths
            parquet_path = PROCESSED_DIR / f"{year_month}.parquet"
            temperature_path = (
                PROCESSED_DIR / f"{year_month_temp}.parquet"
            )

            # Check that both input files exist
            if not parquet_path.exists():
                raise FileNotFoundError(
                    f"Electricity Parquet file not found: {parquet_path}"
                )

            if not temperature_path.exists():
                raise FileNotFoundError(
                    f"Temperature Parquet file not found: {temperature_path}"
                )

            print(f"Processing {year_month}...")

            # Read electricity data
            df = pd.read_parquet(parquet_path)
            df.columns = df.columns.str.lower()
            
            # Cleaning
            df["date"] = pd.to_datetime(df["date"])
            df = df[df["fsa"].str.len() == 3]

            # Add public holiday indicator
            df["is_public_holiday"] = (
                df["date"].dt.normalize()
                .isin(holiday_dates)
                .astype("int8")
            )

            # Read temperature data
            temp_df = pd.read_parquet(temperature_path)
            temp_df.columns = temp_df.columns.str.lower()
            temp_df["date"] = pd.to_datetime(temp_df["date"])

            # Merge temperature into electricity data
            merged_df = df.merge(
                temp_df,
                on=["fsa", "date", "hour"],
                how="left",
                suffixes=("", "_temp"),
            )

            # Save the merged monthly dataframe
            output_path = MERGED_DIR / f"{year_month_merged}.parquet"
            merged_df.to_parquet(output_path, index=False)

            print(f"Saved {output_path}")
# No return value

if __name__ == "__main__":
    read_parquet_range(2022, 1, 2026, 12)