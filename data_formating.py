
import gzip
import shutil
from pathlib import Path


def convert_gz_to_csv(
    input_dir: str | Path,
    output_dir: str | Path
) -> list[Path]:
    """
    Decompress all .gz files in a directory (including subdirectories)
    and save them as .csv files.

    Args:
        input_dir: Directory containing the .gz files.
        output_dir: Directory where the CSV files will be saved.

    Returns:
        List of generated CSV file paths.
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    converted_files = []

    for gz_file in input_dir.rglob("*.gz"):
        relative_path = gz_file.relative_to(input_dir)

        # Remove .gz and ensure the output has a .csv extension
        csv_name = relative_path.name[:-3]
        if not csv_name.endswith(".csv"):
            csv_name += ".csv"

        csv_file = output_dir / relative_path.parent / csv_name
        csv_file.parent.mkdir(parents=True, exist_ok=True)

        with gzip.open(gz_file, "rb") as source:
            with csv_file.open("wb") as destination:
                shutil.copyfileobj(source, destination)

        converted_files.append(csv_file)

        print(f"Converted: {gz_file.name} -> {csv_file.name}")

    print(f"\nTotal converted files: {len(converted_files)}")

    return converted_files



if __name__ == "__main__":
    convert_gz_to_csv(
        input_dir="Data/XETRA_TES_OFFBOOK_TRADES",
        output_dir="Data/XETRA_TES_OFFBOOK_TRADES_csv"
    )