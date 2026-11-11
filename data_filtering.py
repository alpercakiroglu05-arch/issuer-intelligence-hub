
import pandas as pd
from pathlib import Path


def filter_csv_by_isin(
    input_dir: str | Path,
    output_dir: str | Path,
    target_isin: str = "DE0005545503"
) -> list[Path]:

    input_dir = Path(input_dir)
    output_dir = Path(output_dir)

    filtered_files = []

    for csv_file in input_dir.rglob("*.csv"):

        # Read CSV and preserve ISIN values as strings
        try:
            df = pd.read_csv(csv_file, dtype=str)
        except pd.errors.EmptyDataError:
            print(f"Skipped (empty file): {csv_file.name}")
            continue

        # Skip files without data
        if df.empty:
            print(f"Skipped (no data): {csv_file.name}")
            continue

        # Remove accidental whitespace from column names
        df.columns = df.columns.str.strip()

        if "ISIN" not in df.columns:
            print(f"Skipped (ISIN column missing): {csv_file.name}")
            continue

        # Filter rows by ISIN
        filtered_df = df[
            df["ISIN"].str.strip() == target_isin
        ]

        # Skip if no matching ISIN was found
        if filtered_df.empty:
            print(f"Skipped (no matching ISIN): {csv_file.name}")
            continue

        # Preserve relative folder structure
        relative_path = csv_file.relative_to(input_dir)
        output_file = output_dir / relative_path

        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Save only matching rows
        filtered_df.to_csv(output_file, index=False)

        filtered_files.append(output_file)

        print(
            f"Saved: {csv_file.name} "
            f"({len(filtered_df)} matching rows)"
        )

    print(f"\nTotal files saved: {len(filtered_files)}")

    return filtered_files


if __name__ == "__main__":

    liste = [
        "dax_mdax_sdax_liquid_spreads.20260101_20261031",
        "XETRA_FLOW_DYNAMICS_EQUITY_csv",
        "XETRA_OHLC_csv",
        "XETRA_ONBOOK_TRADES_csv",
        "XETRA_TES_OFFBOOK_TRADES_csv"
    ]

    for folder in liste:
        filter_csv_by_isin(
            input_dir=Path("Data") / folder,
            output_dir=Path("Data") / "filtered" / folder,
            target_isin="DE0005545503"
        )