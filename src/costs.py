THERMS_PER_MWH = 34.121  # therms of gas energy in 1 MWh

def gas_bid(pence_per_therm: float, efficiency: float) -> float:
    """Bid in £/MWh of electricity for a gas plant."""
    if efficiency <= 0 or efficiency > 1:  # efficiency must be above 0 and at most 1
        raise ValueError(f"bad efficiency: {efficiency}")

    price_per_therm = pence_per_therm / 100       # pence -> pounds
    fuel_cost = price_per_therm * THERMS_PER_MWH  # pounds per MWh burned
    return fuel_cost / efficiency                 # lower efficiency = more gas per MWh of power