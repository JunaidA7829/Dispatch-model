def validate(data: MarketData) -> None:
    """Raise ValueError if the input data is not usable."""
    # No empty cells anywhere
    for name, df in vars(data).items():
        if df.isna().any().any():
            raise ValueError(f"{name}: contains empty cells")

    # Hours 1..N once each (N taken from demand)
    expected = list(range(1, len(data.demand) + 1))
    for name in ["wind_loadfactors", "solar_loadfactors", "demand", "gas_prices"]:
        if sorted(getattr(data, name)["hour"]) != expected:
            raise ValueError(f"{name}: hours must be 1..{expected[-1]}, none missing or repeated")

from dataclasses import dataclass

import pandas as pd


@dataclass
class MarketData:
    """All input tables from data.xlsx, one attribute per tab."""
    wind_plants: pd.DataFrame
    wind_loadfactors: pd.DataFrame
    solar_plants: pd.DataFrame
    solar_loadfactors: pd.DataFrame
    gas_plants: pd.DataFrame
    demand: pd.DataFrame
    gas_prices: pd.DataFrame


def load_data(path: str) -> MarketData:
    """Read the 7 tabs of the Excel file into a MarketData object."""
    sheets = pd.read_excel(path, sheet_name=None)
    return MarketData(
        wind_plants=sheets["windplants"],
        wind_loadfactors=sheets["wind_loadfactors"],
        solar_plants=sheets["solarplants"],
        solar_loadfactors=sheets["solar_loadfactors"],
        gas_plants=sheets["gasplants"],
        demand=sheets["demand"],
        gas_prices=sheets["gas_prices"],
    )