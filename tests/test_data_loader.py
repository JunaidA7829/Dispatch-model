from pathlib import Path

import pandas as pd
import pytest

from src.data_loader import load_data

DATA_PATH = Path(__file__).parent.parent / "data" / "data.xlsx"  


def read_tables() -> dict:
    return pd.read_excel(DATA_PATH, sheet_name=None)  # every tab: name -> table


def write_copy(tables: dict, broken_path: Path) -> None:
    with pd.ExcelWriter(broken_path) as writer:
        for sheet, frame in tables.items():  # keep the original tab names
            frame.to_excel(writer, sheet_name=sheet, index=False)


def check_rejected(tables: dict, broken_path: Path, message: str) -> None:
    write_copy(tables, broken_path)
    with pytest.raises(ValueError, match=message):
        load_data(broken_path)


def test_unedited_copy_loads(tmp_path):
    # control: an unedited copy must load, so the tests below fail for the right reason
    broken_path = tmp_path / "copy.xlsx"
    write_copy(read_tables(), broken_path)
    load_data(broken_path)


def test_missing_hour(tmp_path):
    tables = read_tables()
    frame = tables["demand"]
    tables["demand"] = frame[frame["hour"] != 5]  # hour 5 removed
    check_rejected(tables, tmp_path / "broken.xlsx", "hours must be")


def test_repeated_hour(tmp_path):
    tables = read_tables()
    frame = tables["gas_prices"]
    frame.loc[4, "hour"] = 3  # hour 3 now appears twice, hour 5 is gone
    check_rejected(tables, tmp_path / "broken.xlsx", "hours must be")


def test_load_factor_above_one(tmp_path):
    tables = read_tables()
    frame = tables["wind_loadfactors"]
    frame.loc[2, "wind1"] = 1.5
    check_rejected(tables, tmp_path / "broken.xlsx", "between 0 and 1")


def test_blank_cell(tmp_path):
    tables = read_tables()
    frame = tables["gas_prices"]
    frame["price"] = frame["price"].astype(float)  # a whole-number column can't hold NaN
    frame.loc[0, "price"] = float("nan")
    check_rejected(tables, tmp_path / "broken.xlsx", "empty cells")


def test_plant_name_mismatch(tmp_path):
    tables = read_tables()
    frame = tables["solar_loadfactors"]
    tables["solar_loadfactors"] = frame.rename(columns={"solar1": "solarX"})
    check_rejected(tables, tmp_path / "broken.xlsx", "do not match plant names")


def test_bad_efficiency(tmp_path):
    tables = read_tables()
    frame = tables["gasplants"]
    frame.loc[0, "efficiency"] = 1.2  # above 100%
    check_rejected(tables, tmp_path / "broken.xlsx", "efficiency must be")