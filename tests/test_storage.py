from pathlib import Path

import pytest

from src.auction import TOL, run_all
from src.data_loader import load_data
from src.storage import Battery, daily_lookahead, run_with_battery

DATA_PATH = Path(__file__).parent.parent / "data" / "data.xlsx"


@pytest.fixture(scope="module")
def data():
    return load_data(DATA_PATH)


@pytest.fixture(scope="module")
def result(data):
    return run_with_battery(data, Battery())  # (table, profit), shared by the tests below


def test_charging_loses_energy():
    battery = Battery(soc_mwh=0)
    battery.charge(1000, 50)  # 1000 MWh from the grid, ~95% stored
    assert round(battery.soc_mwh, 1) == 948.7
    assert round(battery.max_discharge_mwh(), 1) == 900.0  # 90% round trip: 1000 in, 900 out


def test_charge_over_limit_is_refused():
    with pytest.raises(ValueError):
        Battery().charge(2500, 50)  # above the 2,000 MW limit


def test_discharge_over_stored_energy_is_refused():
    with pytest.raises(ValueError):
        Battery(soc_mwh=100).discharge(500)  # only ~95 MWh deliverable


def test_empty_battery_cannot_discharge():
    assert Battery(soc_mwh=0).max_discharge_mwh() == 0


def test_full_battery_cannot_charge():
    assert Battery(soc_mwh=8000).max_charge_mwh() == 0


def test_plan_charges_cheap_hour_and_discharges_dear_hour():
    # 4 blocks of 500 in at £10, 4 blocks of 450 out at £100; the power limit stops a fifth
    charge, discharge = daily_lookahead([10, 100], [2000, 2000], Battery())
    assert charge == [2000, 0]
    assert discharge == [0, 1800]


def test_flat_prices_do_nothing():
    charge, discharge = daily_lookahead([50, 50, 50], [2000, 2000, 2000], Battery())
    assert charge == [0, 0, 0]
    assert discharge == [0, 0, 0]


def test_empty_day_does_nothing():
    assert daily_lookahead([], [], Battery()) == ([], [])


def test_no_spare_supply_means_no_charging():
    charge, _ = daily_lookahead([10, 100], [0, 0], Battery())
    assert charge == [0, 0]


def test_stored_energy_stays_in_range(result):
    table, _ = result
    assert table["soc_mwh"].min() >= -TOL
    assert table["soc_mwh"].max() <= 8000 + TOL


def test_never_charges_and_discharges_in_the_same_hour(result):
    table, _ = result
    both = table[(table["charge_mwh"] > 0) & (table["battery_mwh"] > 0)]
    assert len(both) == 0


def test_power_limit_respected(result):
    table, _ = result
    assert table["charge_mwh"].max() <= 2000 + TOL
    assert table["battery_mwh"].max() <= 2000 + TOL


def test_stored_energy_balances(result):
    table, _ = result
    one_way = Battery().one_way
    stored_in = table["charge_mwh"].sum() * one_way
    taken_out = table["battery_mwh"].sum() / one_way
    assert table["soc_mwh"].iloc[-1] == pytest.approx(4000 + stored_in - taken_out)


def test_profit_is_sales_minus_charging_cost(result):
    table, profit = result
    sales = (table["battery_mwh"] * table["price_gbp_per_mwh"]).sum()
    cost = (table["charge_mwh"] * table["price_gbp_per_mwh"]).sum()
    assert profit == pytest.approx(sales - cost)


def test_battery_does_not_make_shortages_worse(data, result):
    table, _ = result
    base = run_all(data)
    assert table["unmet_mwh"].sum() <= base["unmet_mwh"].sum() + TOL
    assert (table["status"] == "shortage").sum() <= (base["status"] == "shortage").sum()


def test_input_battery_is_not_changed(data):
    battery = Battery()
    run_with_battery(data, battery)
    assert battery.soc_mwh == 4000