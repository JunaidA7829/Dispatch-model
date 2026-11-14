from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # no window needed: charts are saved to files
import matplotlib.pyplot as plt
import matplotlib.ticker
import pandas as pd

from src.auction import SCARCITY_PRICE, TOL

SURFACE = "#fcfcfb"  # chart background
INK = "#0b0b0b"      # titles, values
INK_2 = "#52514e"    # subtitles, legend text
MUTED = "#898781"    # axis labels
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
BLUE = "#2a78d6"     # wind, and single-series charts
ORANGE = "#eb6834"   # solar
AQUA = "#1baf7a"     # gas
ALERT = "#d03b3b"    # shortage shading


def save_results(table: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)  # outputs/ may not exist on a fresh clone
    table.round(2).to_csv(path, index=False)  # 2 decimals: £ and MWh


def summarise(table: pd.DataFrame) -> dict:
    """Week totals. Shortage hours are priced at SCARCITY_PRICE, so the average is also given without them."""
    wind_mwh = table["wind_mwh"].sum()
    solar_mwh = table["solar_mwh"].sum()
    gas_mwh = table["gas_mwh"].sum()
    produced_mwh = wind_mwh + solar_mwh + gas_mwh

    not_shortage = table[table["status"] != "shortage"]
    zero_price = table[table["price_gbp_per_mwh"] <= TOL]
    shortage = table[table["status"] == "shortage"]

    # count hours per marginal gas plant; SCARCITY and renewables are not plants
    plant_hours = table["marginal_plant"].value_counts()
    plant_hours = plant_hours.drop(["SCARCITY", "renewables"], errors="ignore")

    return {
        "hours": len(table),
        "avg_price": table["price_gbp_per_mwh"].mean(),
        "avg_price_no_shortage": not_shortage["price_gbp_per_mwh"].mean(),
        "min_price": table["price_gbp_per_mwh"].min(),
        "max_price": table["price_gbp_per_mwh"].max(),
        "wind_pct": 100 * wind_mwh / produced_mwh,
        "solar_pct": 100 * solar_mwh / produced_mwh,
        "gas_pct": 100 * gas_mwh / produced_mwh,
        "zero_price_hours": len(zero_price),
        "unused_mwh": table["unused_mwh"].sum(),
        "shortage_hours": len(shortage),
        "unmet_mwh": table["unmet_mwh"].sum(),
        "top_plant": plant_hours.index[0],
        "top_plant_hours": int(plant_hours.iloc[0]),
    }


def format_summary(s: dict) -> str:
    lines = [
        f"Hours simulated: {s['hours']}",
        f"Price £/MWh: avg {s['avg_price']:.2f} | min {s['min_price']:.2f} | max {s['max_price']:.2f}",
        f"Avg price excluding shortage hours: £{s['avg_price_no_shortage']:.2f}/MWh",
        f"Energy mix: wind {s['wind_pct']:.1f}% | solar {s['solar_pct']:.1f}% | gas {s['gas_pct']:.1f}%",
        f"£0 price hours: {s['zero_price_hours']} | unused renewable MWh: {s['unused_mwh']:,.0f}",
        f"Shortage hours: {s['shortage_hours']} | unmet MWh: {s['unmet_mwh']:,.0f}",
        f"Most common marginal plant: {s['top_plant']} ({s['top_plant_hours']} hours)",
    ]
    return "\n".join(lines)


def _style(ax, grid_axis: str) -> None:
    ax.set_facecolor(SURFACE)
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.tick_params(colors=MUTED, length=0, labelsize=9)
    ax.grid(axis=grid_axis, color=GRID, linewidth=0.8, linestyle="-")
    ax.set_axisbelow(True)


def _titles(ax, title: str, subtitle: str) -> None:
    ax.set_title(title, loc="left", fontsize=14, fontweight="bold", color=INK, pad=30)
    ax.text(0, 1.03, subtitle, transform=ax.transAxes, fontsize=10, color=INK_2)


def _day_ticks(ax) -> None:
    ax.set_xticks(range(1, 169, 24))  # hour 1 is midnight, so every 24th hour starts a day
    ax.set_xticklabels([f"Day {d}" for d in range(1, 8)])
    ax.set_xlim(1, 168)


def _shortage_spans(table: pd.DataFrame) -> list:
    """(left, right) edges of each run of consecutive shortage hours."""
    spans = []
    start = None
    last = None
    for hour, status in zip(table["hour"], table["status"]):
        if status == "shortage":
            if start is None:
                start = hour
            last = hour
        elif start is not None:
            spans.append((start - 0.5, last + 0.5))
            start = None
    if start is not None:
        spans.append((start - 0.5, last + 0.5))
    return spans


def plot_price(table: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 4.5), facecolor=SURFACE)
    # shortage hours are priced at SCARCITY_PRICE, far off the scale: leave a gap in the line
    price = table["price_gbp_per_mwh"].where(table["status"] != "shortage")
    for left, right in _shortage_spans(table):
        ax.axvspan(left, right, color=ALERT, alpha=0.12, linewidth=0)
    ax.plot(table["hour"], price, color=BLUE, linewidth=2, solid_capstyle="round")
    ax.set_ylim(0, price.max() * 1.15)
    ax.set_ylabel("£/MWh", color=MUTED, fontsize=9)
    n_short = int((table["status"] == "shortage").sum())
    _titles(ax, "Electricity price by hour",
            f"Red bands: the {n_short} shortage hours, priced at £{SCARCITY_PRICE:,}/MWh (off the scale).")
    _style(ax, "y")
    _day_ticks(ax)
    fig.savefig(path, dpi=150, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)


def plot_mix(table: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 5), facecolor=SURFACE)
    for i, (left, right) in enumerate(_shortage_spans(table)):
        label = "Shortage hours" if i == 0 else None  # one legend entry for all bands
        ax.axvspan(left, right, color=ALERT, alpha=0.12, linewidth=0, label=label)
    ax.stackplot(table["hour"], table["wind_mwh"], table["solar_mwh"], table["gas_mwh"],
                 labels=["Wind", "Solar", "Gas"], colors=[BLUE, ORANGE, AQUA],
                 edgecolor=SURFACE, linewidth=1.5, zorder=2)  # surface-coloured edge = gap between layers
    ax.plot(table["hour"], table["demand_mwh"], color=INK, linewidth=2, label="Demand", zorder=3)
    ax.set_ylabel("MWh per hour", color=MUTED, fontsize=9)
    ax.yaxis.set_major_formatter(matplotlib.ticker.StrMethodFormatter("{x:,.0f}"))
    _titles(ax, "Generation mix and demand",
            "Where the stack falls short of the demand line, demand went unmet.")
    _style(ax, "y")
    _day_ticks(ax)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=5, frameon=False,
              fontsize=10, labelcolor=INK_2)
    fig.savefig(path, dpi=150, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)


def plot_marginal(table: pd.DataFrame, path: Path) -> None:
    counts = table["marginal_plant"].value_counts().sort_values()  # smallest first, so the biggest bar is on top
    fig, ax = plt.subplots(figsize=(8, 4), facecolor=SURFACE)
    ax.barh(counts.index, counts.values, height=0.5, color=BLUE)
    for row, hours in enumerate(counts.values):
        ax.text(hours + 0.5, row, str(hours), va="center", fontsize=10, color=INK)
    ax.set_xlim(0, counts.max() * 1.12)
    ax.set_xlabel("Hours", color=MUTED, fontsize=9)
    _titles(ax, "Which plant set the price?",
            f"Hours each plant was the marginal plant, out of {len(table)}.")
    _style(ax, "x")
    ax.tick_params(axis="y", colors=INK_2, labelsize=10)
    fig.savefig(path, dpi=150, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)


def save_charts(table: pd.DataFrame, folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    plot_price(table, folder / "chart1_price.png")
    plot_mix(table, folder / "chart2_mix.png")
    plot_marginal(table, folder / "chart3_marginal.png")

