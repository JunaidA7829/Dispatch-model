import pandas as pd

from src.costs import gas_bid
from src.data_loader import MarketData

SCARCITY_PRICE = 6000  # prices per MWh charged when demand can't be met
TOL = 1e-6             # prices per MWh closer than this count as equal

Offer = tuple[str, float, float]
BATTERY_NAME = "battery"  # the battery discharging appears as an offer with this name
NAME, PRICE, MWH = 0, 1, 2

def clear_hour(offers: list[Offer], demand: float) -> dict:
    """Runs one hour's auction: cheapest offers first, and the last one needed sets the price.
    Equal bids share by size, and demand nobody can supply gets the scarcity price."""
    ranked = []
    for o in offers:
        if o[MWH] > 0:  # a 0 MWh offer can't clear anything
            ranked.append(o)
    ranked.sort(key=lambda o: o[PRICE])  # cheapest first

    free_mwh = 0  # MWh offered at £0
    for o in ranked:
        if o[PRICE] <= TOL:
            free_mwh += o[MWH]

    accepted = {}      # plant means MWh accepted
    remaining = demand # MWh not yet served
    price = 0
    marginal = []
    start = 0          # first offer of the current price group
    free_used = 0      # MWh taken from £0 offers

    while start < len(ranked) and remaining > TOL:
        end = start    # will end up just past the group
        group_mwh = 0
        while end < len(ranked) and abs(ranked[end][PRICE] - ranked[start][PRICE]) <= TOL:
            group_mwh += ranked[end][MWH]
            end += 1

        take_mwh = min(group_mwh, remaining)
        fraction = take_mwh / group_mwh  # safe - group_mwh > 0, zero offers were dropped

        marginal = []  # reset - only the last group used stays
        for idx in range(start, end):
            accepted[ranked[idx][NAME]] = ranked[idx][MWH] * fraction
            marginal.append(ranked[idx][NAME])

        if ranked[start][PRICE] <= TOL:
            free_used += take_mwh
        remaining -= take_mwh
        price = ranked[start][PRICE]
        start = end

    unused = free_mwh - free_used  # curtailment: renewable MWh switched off
    unmet = 0
    if remaining > TOL:  # every offer used and demand still unmet
        unmet = remaining
        price = SCARCITY_PRICE
        marginal = []  # no plant sets a scarcity price

    return {"price": price, "marginal": marginal, "accepted": accepted,
            "unused": unused, "unmet": unmet}


def build_offers(data: MarketData, hour: int) -> list[Offer]:
    """Offers for one hour as (name, £/MWh, MWh)."""
    offers = []
    wind_lf = data.wind_loadfactors.set_index("hour")    # look up by hour, never by row position
    solar_lf = data.solar_loadfactors.set_index("hour")
    gas_price = data.gas_prices.set_index("hour").loc[hour, "price"]  # p/therm

    for _, plant in data.wind_plants.iterrows():
        mwh = plant["capacity"] * wind_lf.loc[hour, plant["name"]]  # 1 h at X MW = X MWh
        offers.append((plant["name"], 0, mwh))
    for _, plant in data.solar_plants.iterrows():
        mwh = plant["capacity"] * solar_lf.loc[hour, plant["name"]]
        offers.append((plant["name"], 0, mwh))
    for _, plant in data.gas_plants.iterrows():
        offers.append((plant["name"], gas_bid(gas_price, plant["efficiency"]), plant["capacity"]))
    return offers


def run_hour(data: MarketData, hour: int, demand: float, offers: list[Offer],
             charge_mwh: float = 0) -> tuple[dict, dict]:
    """Clears one hour. Returns (table row, raw clear_hour result).
    demand is what consumers use; battery charging is extra demand to the auction."""
    wind_names = set(data.wind_plants["name"])
    solar_names = set(data.solar_plants["name"])
    result = clear_hour(offers, demand + charge_mwh)

    wind_mwh = 0
    solar_mwh = 0
    gas_mwh = 0
    battery_mwh = 0
    for name, mwh in result["accepted"].items():
        if name in wind_names:
            wind_mwh += mwh
        elif name in solar_names:
            solar_mwh += mwh
        elif name == BATTERY_NAME:
            battery_mwh += mwh
        else:
            gas_mwh += mwh  # every other plant is gas
    produced_mwh = wind_mwh + solar_mwh + gas_mwh + battery_mwh

    if result["unmet"] > TOL:
        status = "shortage"
    elif result["unused"] > TOL:
        status = "surplus"
    else:
        status = "normal"

    if status == "shortage":
        marginal_plant = "SCARCITY"
    elif result["price"] <= TOL:
        marginal_plant = "renewables"  # only £0 offers set the price
    else:
        marginal_plant = "+".join(result["marginal"])  # a tie shows as gas1+gas2

    pct_per_mwh = 0  # % of produced MWh per 1 MWh; stays 0 if nothing was produced
    if produced_mwh > 0:
        pct_per_mwh = 100 / produced_mwh

    row = {
        "hour": hour,
        "status": status,
        "demand_mwh": demand,
        "price_gbp_per_mwh": result["price"],
        "marginal_plant": marginal_plant,
        "wind_mwh": wind_mwh,
        "solar_mwh": solar_mwh,
        "gas_mwh": gas_mwh,
        "battery_mwh": battery_mwh,
        "charge_mwh": charge_mwh,
        "wind_pct": wind_mwh * pct_per_mwh,
        "solar_pct": solar_mwh * pct_per_mwh,
        "gas_pct": gas_mwh * pct_per_mwh,
        "battery_pct": battery_mwh * pct_per_mwh,
        "unused_mwh": result["unused"],
        "unmet_mwh": result["unmet"],
    }
    return row, result


def run_all(data: MarketData) -> pd.DataFrame:
    """One row per hour, no battery. Mix % is of MWh dispatched, so it sums to 100."""
    rows = []
    for _, demand_row in data.demand.iterrows():
        hour = int(demand_row["hour"])
        offers = build_offers(data, hour)
        row, _ = run_hour(data, hour, demand_row["demand"], offers)
        rows.append(row)
    return pd.DataFrame(rows)

