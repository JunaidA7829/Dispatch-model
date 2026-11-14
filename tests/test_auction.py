from pathlib import Path

import pytest

from src.auction import MWH, NAME, SCARCITY_PRICE, TOL, build_offers, clear_hour, run_all
from src.costs import gas_bid
from src.data_loader import load_data

DATA_PATH = Path(__file__).parent.parent / "data" / "data.xlsx"  


@pytest.fixture(scope="module")
def data():
    return load_data(DATA_PATH)


@pytest.fixture(scope="module")
def table(data):
    return run_all(data)  # runs all 168 hours once


def test_gas_bid():
    # 70 p/therm -> 0.70 * 34.121 / efficiency
    assert round(gas_bid(70, 0.55), 2) == 43.43
    assert round(gas_bid(70, 0.35), 2) == 68.24


def test_hour_1(table):
    row = table[table["hour"] == 1].iloc[0]
    assert round(row["price_gbp_per_mwh"], 2) == 68.24
    assert row["marginal_plant"] == "gas1"
    assert round(row["wind_pct"], 1) == 23.5
    assert row["solar_pct"] == 0
    assert round(row["gas_pct"], 1) == 76.5


def test_hour_12(table):
    row = table[table["hour"] == 12].iloc[0]
    assert round(row["price_gbp_per_mwh"], 2) == 67.39
    assert row["marginal_plant"] == "gas2"


def test_supply_meets_demand(table):
    produced = table["wind_mwh"] + table["solar_mwh"] + table["gas_mwh"]
    gap = produced + table["unmet_mwh"] - table["demand_mwh"]  # must be 0 in every hour
    assert gap.abs().max() < TOL


def test_no_plant_over_capacity(data):
    for _, row in data.demand.iterrows():
        offers = build_offers(data, int(row["hour"]))
        result = clear_hour(offers, row["demand"])
        offered = {}  # plant MWh available  at this hour
        for o in offers:
            offered[o[NAME]] = o[MWH]
        for name, mwh in result["accepted"].items():
            assert mwh <= offered[name] + TOL


def test_surplus_hour(table):
    row = table[table["hour"] == 81].iloc[0]
    assert row["status"] == "surplus"
    assert row["price_gbp_per_mwh"] == 0
    assert row["unused_mwh"] > 0
    assert row["gas_mwh"] == 0  # renewables alone cover demand


def test_shortage_hour(table):
    row = table[table["hour"] == 19].iloc[0]
    assert row["status"] == "shortage"
    assert row["unmet_mwh"] > 0
    assert row["price_gbp_per_mwh"] == SCARCITY_PRICE


def test_hour_counts(table):
    surplus_hours = table[table["status"] == "surplus"]["hour"].tolist()
    shortage_hours = table[table["status"] == "shortage"]["hour"].tolist()
    assert surplus_hours == list(range(81, 89)) + [134, 135, 158]
    assert shortage_hours == (list(range(19, 22)) + list(range(42, 47))
                              + list(range(114, 129)) + list(range(163, 169)))