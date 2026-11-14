SCARCITY_PRICE = 6000  # prices per MWh charged when demand can't be met
TOL = 1e-6             # prices per MWh closer than this count as equal

Offer = tuple[str, float, float]
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


def show_hour(res: dict) -> None:
    print("plant  MWh")
    for name, mwh in res["accepted"].items():
        print(f"{name:<5}  {mwh:>5.1f}")
    who = ", ".join(res["marginal"]) if res["marginal"] else "none"
    print(f"price {res['price']} | marginal {who} | unused {res['unused']:.1f} | unmet {res['unmet']}")