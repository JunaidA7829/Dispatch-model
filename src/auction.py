Offer = tuple[str, float, float]  
NAME, PRICE, MWH = 0, 1, 2   
 
def clear_hour(offers: list[Offer], demand: float) -> dict:
    """Normal hours only. Offers at the same price share the marginal MWh."""
    ranked = []
    for o in offers:
        if o[MWH] > 0:  # a 0 MWh offer can't clear anything
            ranked.append(o)
    ranked.sort(key=lambda o: o[PRICE])  # cheapest first

    accepted = {}      # plant -> MWh accepted
    remaining = demand # MWh not yet served
    price = 0
    marginal = []
    start = 0          # first offer of the current price group

    while start < len(ranked) and remaining > 0:
        end = start    # will end up just past the group
        group_mwh = 0
        # assumes exact price ties
        while end < len(ranked) and ranked[end][PRICE] == ranked[start][PRICE]:
            group_mwh += ranked[end][MWH]
            end += 1

        take_mwh = min(group_mwh, remaining)
        fraction = take_mwh / group_mwh  # safe - group_mwh > 0, zero offers were dropped

        marginal = []  # reset - only the last group used stays
        for idx in range(start, end):
            accepted[ranked[idx][NAME]] = ranked[idx][MWH] * fraction
            marginal.append(ranked[idx][NAME])

        remaining -= take_mwh
        price = ranked[start][PRICE]
        start = end

    return {"price": price, "marginal": marginal, "accepted": accepted, "unserved": remaining}


def show_hour(res: dict) -> None:
    print("plant  MWh")
    for name, mwh in res["accepted"].items():
        print(f"{name:<5}  {mwh:>5.1f}")
    print(f"price {res['price']} | marginal {', '.join(res['marginal'])} | unserved {res['unserved']}")