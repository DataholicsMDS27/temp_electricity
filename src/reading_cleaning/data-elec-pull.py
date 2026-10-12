from pathlib import Path
import io
import zipfile

import pandas as pd
import requests


BASE_URL = (
    "https://reports-public.ieso.ca/public/"
    "HourlyConsumptionByFSA/"
)

PROCESSED_DIR = Path("data/raw")

# Set the year range you want
START_YEAR = 2023
END_YEAR = 2026


def read_ieso_csv(zip_file, csv_file):
    """Read an IESO CSV while automatically finding its header row."""

    with zip_file.open(csv_file) as f:
        for row_number, line in enumerate(f):

            line = line.decode("utf-8-sig").strip()
            columns = [column.strip() for column in line.split(",")]

            required_columns = {
                "FSA",
                "DATE",
                "HOUR",
                "CUSTOMER_TYPE",
            }

            if required_columns.issubset(columns):
                header_row = row_number
                break

        else:
            raise ValueError(
                f"Could not find header row in {csv_file}"
            )

    print(f"Found header on row {header_row}")

    with zip_file.open(csv_file) as f:
        df = pd.read_csv(
            f,
            skiprows=header_row,
            header=0,
        )

    return df


def download_and_convert_month(
    year: int,
    month: int
) -> Path | None:
    """
    Download one month's IESO ZIP file into memory,
    extract the CSV, and save it as Parquet.

    Returns the Parquet path if successful.
    Returns None if the monthly file is not available.
    """

    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    year_month = f"{year}{month:02d}"

    parquet_path = (
        PROCESSED_DIR / f"{year_month}.parquet"
    )

    # Don't re-download/re-process files that already exist
    if parquet_path.exists():
        print(f"Already exists: {parquet_path}")
        return parquet_path

    url = (
        f"{BASE_URL}"
        f"PUB_HourlyConsumptionByFSA_{year_month}_v1.zip"
    )

    print(f"Downloading {year_month}...")

    response = requests.get(
        url,
        timeout=60
    )

    # Stop if the monthly file does not exist
    if response.status_code == 404:
        print(
            f"Reached {year} and "
            f"{month:02d} is not available"
        )
        return None

    response.raise_for_status()

    # Open the downloaded ZIP directly from memory
    with zipfile.ZipFile(
        io.BytesIO(response.content)
    ) as z:

        csv_files = [
            name
            for name in z.namelist()
            if name.lower().endswith(".csv")
        ]

        if not csv_files:
            raise ValueError(
                f"No CSV found in {year_month}"
            )

        if len(csv_files) > 1:
            print(
                f"Found multiple CSV files: "
                f"{csv_files}"
            )

        csv_file = csv_files[0]

        print(f"Reading {csv_file}...")

        df = read_ieso_csv(
            z,
            csv_file
        )

    # Save only the Parquet file
    df.to_parquet(
        parquet_path,
        engine="pyarrow",
        index=False,
    )

    print(f"Saved: {parquet_path}")
    print(f"Rows: {len(df):,}")

    return parquet_path


def process_year_range(
    start_year: int,
    end_year: int
):
    """
    Download and convert every month from
    start_year through end_year.

    Stops at the first unavailable month.
    """

    for year in range(
        start_year,
        end_year + 1
    ):

        for month in range(1, 13):

            result = download_and_convert_month(
                year,
                month
            )

            # Stop completely when a month is unavailable
            if result is None:
                return

    print(
        f"Finished downloading data from "
        f"{start_year} through {end_year}."
    )


if __name__ == "__main__":
    process_year_range(
        START_YEAR,
        END_YEAR
    )