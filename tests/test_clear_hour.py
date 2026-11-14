import pytest

from src.auction import SCARCITY_PRICE, TOL, clear_hour


def test_tiny_market():
    offers = [("w", 0, 100), ("g1", 50, 100), ("g2", 80, 100)]
    result = clear_hour(offers, 150)  # w gives 100, g1 gives the last 50
    assert result["accepted"] == {"w": 100, "g1": 50}
    assert result["price"] == 50
    assert result["marginal"] == ["g1"]
    assert result["unused"] == 0
    assert result["unmet"] == 0


def test_tie_split():
    offers = [("a", 50, 100), ("b", 50, 300)]
    result = clear_hour(offers, 200)  # 200 of 400 offered, so each gives 50% of its offer
    assert result["accepted"]["a"] == pytest.approx(50)
    assert result["accepted"]["b"] == pytest.approx(150)
    assert result["price"] == 50
    assert result["marginal"] == ["a", "b"]


def test_near_tie():
    tiny_gap = TOL / 10  # float noise, smaller than the tolerance
    offers = [("a", 50, 100), ("b", 50 + tiny_gap, 100)]
    result = clear_hour(offers, 100)
    assert result["marginal"] == ["a", "b"]  # treated as one price group
    assert result["accepted"]["a"] == pytest.approx(50)
    assert result["accepted"]["b"] == pytest.approx(50)


def test_empty_offers():
    result = clear_hour([], 100)
    assert result["accepted"] == {}
    assert result["marginal"] == []
    assert result["price"] == SCARCITY_PRICE
    assert result["unmet"] == 100


def test_zero_demand():
    offers = [("w", 0, 100), ("g1", 50, 100)]
    result = clear_hour(offers, 0)
    assert result["accepted"] == {}
    assert result["marginal"] == []
    assert result["price"] == 0
    assert result["unmet"] == 0
    assert result["unused"] == 100  # all the £0 MWh is switched off


def test_zero_mwh_offer_ignored():
    offers = [("s", 0, 0), ("g1", 50, 100)]  # solar at night
    result = clear_hour(offers, 50)
    assert result["accepted"] == {"g1": 50}
    assert result["price"] == 50


def test_exact_supply():
    offers = [("w", 0, 100), ("g1", 50, 100)]
    result = clear_hour(offers, 200)  # demand equals supply, so no shortage
    assert result["accepted"] == {"w": 100, "g1": 100}
    assert result["price"] == 50  # not the scarcity price
    assert result["unmet"] == 0


def test_surplus_shared_evenly():
    offers = [("w", 0, 100), ("s", 0, 300)]
    result = clear_hour(offers, 100)  # both cut by the same 75%
    assert result["accepted"]["w"] == pytest.approx(25)
    assert result["accepted"]["s"] == pytest.approx(75)
    assert result["price"] == 0
    assert result["unused"] == pytest.approx(300)