
import pandas as pd
from pathlib import Path


def merge_csv_files(
    input_dir: str | Path,
    output_file: str | Path
) -> Path | None:

    input_dir = Path(input_dir)
    output_file = Path(output_file)

    csv_files = list(input_dir.rglob("*.csv"))

    if not csv_files:
        print(f"No CSV files found in {input_dir}")
        return None

    dataframes = []

    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file, dtype=str)

            if df.empty:
                print(f"Skipped (empty): {csv_file.name}")
                continue

            dataframes.append(df)

            print(f"Loaded: {csv_file.name} ({len(df)} rows)")

        except pd.errors.EmptyDataError:
            print(f"Skipped (empty file): {csv_file.name}")

    if not dataframes:
        print("No data available for merging.")
        return None

    # Merge all DataFrames
    merged_df = pd.concat(dataframes, ignore_index=True)

    # Create output directory
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Save merged CSV
    merged_df.to_csv(output_file, index=False)

    print(f"\nMerged {len(dataframes)} files.")
    print(f"Total rows: {len(merged_df)}")
    print(f"Output: {output_file}")

    return output_file


if __name__ == "__main__":

    base_dir = Path("Data/filtered")
    output_dir = Path("Data/merged")

    folders = [
        "XETRA_FLOW_DYNAMICS_EQUITY_csv",
        "XETRA_OHLC_csv"
    ]

    for folder in folders:

        merge_csv_files(
            input_dir=base_dir / folder,
            output_file=output_dir / f"{folder}_merged.csv"
        )