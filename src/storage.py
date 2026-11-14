from dataclasses import dataclass, replace
from math import sqrt

import pandas as pd

from src.auction import (BATTERY_NAME, MWH, NAME, PRICE, TOL, Offer, build_offers,
                         clear_hour, run_hour)
from src.data_loader import MarketData

BLOCK_MWH = 500     # grid MWh moved per planning step
MIN_SPREAD = 1.0    # £/MWh a charge-discharge pair must earn after losses
HOURS_PER_DAY = 24


@dataclass
class Battery:
    """Physics only: limits, losses and what it paid. 1 h at X MW = X MWh."""
    power_mw: float = 2000     # max charge or discharge in one hour
    energy_mwh: float = 8000   # 4 hours at full power
    round_trip: float = 0.90   # energy out / energy in
    soc_mwh: float = 4000      # energy stored now: starts 50% full
    cost_per_mwh: float = 0.0  # £ paid per stored MWh, weighted average

    @property
    def one_way(self) -> float:
        return sqrt(self.round_trip)  # the loss is split equally: ~95% each way

    def max_charge_mwh(self) -> float:
        """Grid MWh it can draw this hour."""
        room = (self.energy_mwh - self.soc_mwh) / self.one_way
        return max(0.0, min(self.power_mw, room))

    def max_discharge_mwh(self) -> float:
        """MWh it can deliver to the grid this hour."""
        available = self.soc_mwh * self.one_way
        return max(0.0, min(self.power_mw, available))

    def charge(self, grid_mwh: float, price: float) -> None:
        if grid_mwh > self.max_charge_mwh() + TOL:
            raise ValueError("charge exceeds the power limit or the room left")
        total = self.soc_mwh + grid_mwh * self.one_way
        if total > 0:
            self.cost_per_mwh = (self.soc_mwh * self.cost_per_mwh + grid_mwh * price) / total
        self.soc_mwh = total

    def discharge(self, delivered_mwh: float) -> None:
        if delivered_mwh > self.max_discharge_mwh() + TOL:
            raise ValueError("discharge exceeds the power limit or the energy stored")
        self.soc_mwh = max(0.0, self.soc_mwh - delivered_mwh / self.one_way)

    def bid(self) -> float:
        """Break-even offer in £ per delivered MWh: cost of the stored energy plus the discharge loss."""
        return self.cost_per_mwh / self.one_way


def _stays_in_range(battery: Battery, charge: list, discharge: list) -> bool:
    soc = battery.soc_mwh
    for hour in range(len(charge)):
        soc += charge[hour] * battery.one_way - discharge[hour] / battery.one_way
        if soc < -TOL or soc > battery.energy_mwh + TOL:
            return False
    return True


def daily_lookahead(prices: list, spare_mwh: list, battery: Battery) -> tuple[list, list]:
    """Plans one day knowing the no-battery prices. Returns (charge, discharge) MWh per hour.
    Repeatedly pairs the cheapest hour to charge with the dearest hour to discharge, in blocks,
    while the pair earns more than MIN_SPREAD after losses and the charge level stays between 0 and full.
    spare_mwh caps charging at supply that would otherwise go unused at the same price."""
    hours = len(prices)
    charge = [0.0] * hours
    discharge = [0.0] * hours
    block_out = BLOCK_MWH * battery.round_trip  # MWh delivered by one block

    while True:
        best_pair = None
        best_spread = MIN_SPREAD
        for c in range(hours):
            room = min(battery.power_mw, spare_mwh[c])
            if discharge[c] > 0 or charge[c] + BLOCK_MWH > room + TOL:
                continue  # an hour either charges or discharges, never both
            for d in range(hours):
                if d == c or charge[d] > 0 or discharge[d] + block_out > battery.power_mw + TOL:
                    continue
                spread = battery.round_trip * prices[d] - prices[c]
                if spread <= best_spread:
                    continue
                charge[c] += BLOCK_MWH
                discharge[d] += block_out
                fits = _stays_in_range(battery, charge, discharge)
                charge[c] -= BLOCK_MWH
                discharge[d] -= block_out
                if fits:
                    best_pair = (c, d)
                    best_spread = spread
        if best_pair is None:
            return charge, discharge
        charge[best_pair[0]] += BLOCK_MWH
        discharge[best_pair[1]] += block_out


def _spare_mwh(offers: list, result: dict) -> float:
    """MWh left unused at or below the clearing price. Charging up to this much leaves the price unchanged."""
    if result["unmet"] > TOL:
        return 0.0  # no spare supply in a shortage
    spare = 0.0
    for o in offers:
        if o[PRICE] <= result["price"] + TOL:
            spare += o[MWH] - result["accepted"].get(o[NAME], 0)
    return spare


def run_with_battery(data: MarketData, battery: Battery) -> tuple[pd.DataFrame, float]:
    """Plans each day from the no-battery prices, then re-runs the auction hour by hour
    with the battery as extra demand (charging) or an offer (discharging).
    Returns (table, battery profit in £)."""
    battery = replace(battery)  # work on a copy
    hours = []
    demands = []
    base_offers = []
    prices = []
    spare = []
    price_sum = 0.0
    price_count = 0
    for _, demand_row in data.demand.iterrows():
        hour = int(demand_row["hour"])
        offers = build_offers(data, hour)
        result = clear_hour(offers, demand_row["demand"])
        hours.append(hour)
        demands.append(demand_row["demand"])
        base_offers.append(offers)
        prices.append(result["price"])
        spare.append(_spare_mwh(offers, result))
        if result["unmet"] <= TOL:  # scarcity prices would swamp the average
            price_sum += result["price"]
            price_count += 1
    battery.cost_per_mwh = price_sum / price_count  # assumption: starting energy was bought at the average price

    rows = []
    profit = 0.0
    for day_start in range(0, len(hours), HOURS_PER_DAY):
        day_end = min(day_start + HOURS_PER_DAY, len(hours))
        charge, discharge = daily_lookahead(prices[day_start:day_end], spare[day_start:day_end], battery)

        for step in range(day_end - day_start):
            h = day_start + step
            charge_mwh = min(charge[step], battery.max_charge_mwh())  # earlier hours may have gone differently to plan
            offer_mwh = min(discharge[step], battery.max_discharge_mwh())
            hour_offers = list(base_offers[h])
            if offer_mwh > TOL:
                hour_offers.append((BATTERY_NAME, battery.bid(), offer_mwh))

            row, result = run_hour(data, hours[h], demands[h], hour_offers, charge_mwh)
            price = row["price_gbp_per_mwh"]
            sold_mwh = result["accepted"].get(BATTERY_NAME, 0)  # accepted only if its bid is at or below the price
            if sold_mwh > 0:
                battery.discharge(sold_mwh)
                profit += sold_mwh * price
            if charge_mwh > 0:
                battery.charge(charge_mwh, price)
                profit -= charge_mwh * price
            row["soc_mwh"] = battery.soc_mwh
            rows.append(row)

    return pd.DataFrame(rows), profit