from pathlib import Path

import pandas as pd

from src.auction import TOL


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