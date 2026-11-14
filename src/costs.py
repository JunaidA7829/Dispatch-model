THERMS_PER_MWH = 34.121  # therms of gas energy in 1 MWh

def gas_bid(price_pence_per_therm, efficiency):
    """Bid (£ per MWh of electricity) for one gas plant."""
    if not 0 < efficiency <= 1:  # guard: efficiency must be in (0, 1]
        raise ValueError(f"efficiency must be in (0, 1], got {efficiency}")

    price_gbp_per_therm = price_pence_per_therm / 100  # pence -> pounds
    gas_cost_per_mwh_heat = price_gbp_per_therm * THERMS_PER_MWH  # £ per MWh of gas burned
    return gas_cost_per_mwh_heat / efficiency  # lower efficiency = more gas per MWh of power = higher bid