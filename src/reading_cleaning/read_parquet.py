from pathlib import Path

import pandas as pd


def read_parquet_range(
    start_year: int,
    start_month: int,
    end_year: int,
    end_month: int,
    data_dir: str | Path = Path(
        r"C:\Users\jonah\Desktop\personalProjects\temp_electricity\data\merged"
    ),
) -> pd.DataFrame:
    """
    Read a range of monthly Parquet files into one DataFrame.

    Parameters
    ----------
    start_year : int
    start_month : int
    end_year : int
    end_month : int
    data_dir : str or Path
        Directory containing the monthly Parquet files.

    Example
    -------
    read_parquet_range(2023, 1, 2023, 3, "data/raw")
    """

    data_dir = Path(data_dir)
    dataframes = []

    for year in range(start_year, end_year + 1):
        first_month = start_month if year == start_year else 1
        last_month = end_month if year == end_year else 12

        for month in range(first_month, last_month + 1):
            year_month = f"{year}-{month:02d}"
            parquet_path = data_dir / f"{year_month}-merged.parquet"

            if not parquet_path.exists():
                raise FileNotFoundError(
                    f"Parquet file not found: {parquet_path}"
                )

            print(f"Reading {year_month}...")
            df = pd.read_parquet(parquet_path)
            dataframes.append(df)

    return pd.concat(dataframes, ignore_index=True)