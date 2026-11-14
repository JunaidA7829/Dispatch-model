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

    # Load factors in [0, 1] and columns match plant names
    for kind, plants in [("wind", data.wind_plants), ("solar", data.solar_plants)]:
        lf = getattr(data, f"{kind}_loadfactors").drop(columns="hour")
        if ((lf < 0) | (lf > 1)).any().any():
            raise ValueError(f"{kind}_loadfactors: values must be between 0 and 1")
        if set(lf.columns) != set(plants["name"]):
            raise ValueError(f"{kind}_loadfactors: columns do not match plant names")

    # Efficiency must be above 0 and at most 1
    eff = data.gas_plants["efficiency"]
    if ((eff <= 0) | (eff > 1)).any():
        raise ValueError("gas_plants: efficiency must be above 0 and at most 1")


def load_data(path: str) -> MarketData:
    """Read the 7 tabs of the Excel file, validate them, return MarketData."""
    sheets = pd.read_excel(path, sheet_name=None)
    data = MarketData(
        wind_plants=sheets["windplants"],
        wind_loadfactors=sheets["wind_loadfactors"],
        solar_plants=sheets["solarplants"],
        solar_loadfactors=sheets["solar_loadfactors"],
        gas_plants=sheets["gasplants"],
        demand=sheets["demand"],
        gas_prices=sheets["gas_prices"],
    )
    validate(data)
    return data