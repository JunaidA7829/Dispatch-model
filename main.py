from pathlib import Path

from src.auction import run_all
from src.data_loader import load_data
from src.reporting import (compare_scenarios, format_comparison, format_summary, plot_battery,
                           save_charts, save_results, summarise)
from src.storage import Battery, run_with_battery

ROOT = Path(__file__).parent  # paths relative to the repo, never to one computer


def main() -> None:
    data = load_data(ROOT / "data" / "data.xlsx")
    outputs = ROOT / "outputs"

    table = run_all(data)
    save_results(table, outputs / "hourly_results.csv")
    save_charts(table, outputs)
    print(format_summary(summarise(table)))

    with_battery, profit = run_with_battery(data, Battery())
    save_results(with_battery, outputs / "hourly_results_with_battery.csv")
    plot_battery(table, with_battery, outputs / "chart4_battery.png")
    print()
    print(format_comparison(compare_scenarios(table, with_battery, profit)))


if __name__ == "__main__":
    main()