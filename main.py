from pathlib import Path

from src.auction import run_all
from src.data_loader import load_data
from src.reporting import format_summary, save_charts, save_results, summarise

ROOT = Path(__file__).parent  # paths relative to the repo, never to one computer


def main() -> None:
    data = load_data(ROOT / "data" / "data.xlsx")
    table = run_all(data)
    save_results(table, ROOT / "outputs" / "hourly_results.csv")
    save_charts(table, ROOT / "outputs")
    print(format_summary(summarise(table)))


if __name__ == "__main__":
    main()