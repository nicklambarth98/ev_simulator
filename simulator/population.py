"""
population.py
-------------
Runs a population of EVDriver agents and aggregates their results.

This module contains only pure functions with no side effects — it is
imported by both app.py (Streamlit) and run_simulation.py (CLI) without
any risk of code executing on import.
"""

import pandas as pd
import numpy as np
from typing import Dict
from simulator.agent import EVDriver, DriverProfile


def run_population(
    archetypes: Dict[str, DriverProfile],
    n_agents_per_archetype: int,
    start_date: str,
    end_date: str,
    base_seed: int = 17,
    weight_by_population_share: bool = False,
) -> pd.DataFrame:
    """
    Simulate a population of EV drivers over a date range.

    Each archetype gets n_agents_per_archetype drivers, each with a unique
    but deterministic seed derived from base_seed — so results are
    reproducible while each agent still behaves independently.

    Parameters
    ----------
    archetypes : dict[str, DriverProfile]
        Archetype definitions, typically from load_archetypes().
    n_agents_per_archetype : int
        How many independent agents to simulate per archetype.
    start_date, end_date : str
        Simulation date range, e.g. "2024-01-01", "2024-03-31".
    base_seed : int
        Root seed for reproducibility.
    weight_by_population_share : bool
        If True, scale n_agents proportionally to population_share rather
        than using a flat count per archetype.

    Returns
    -------
    pd.DataFrame
        All plug-in events across all agents. One row per event.
        Empty DataFrame if no events occurred.
    """
    all_events = []
    driver_id = 0

    for archetype_key, profile in archetypes.items():

        # Optionally scale agent count by real world population share
        if weight_by_population_share:
            n = max(1, round(n_agents_per_archetype * profile.population_share))
        else:
            n = n_agents_per_archetype

        for i in range(n):
            # Unique but deterministic seed per agent
            seed = base_seed + driver_id

            driver = EVDriver(profile=profile, driver_id=driver_id, seed=seed)
            events = driver.simulate_period(start_date, end_date)

            if not events.empty:
                all_events.append(events)

            driver_id += 1

    if not all_events:
        return pd.DataFrame()

    return pd.concat(all_events, ignore_index=True)


def compute_hourly_stats(df: pd.DataFrame) -> pd.DataFrame:
    """ 
    Compute population-level plug-in statistics by hour of day.

    For each integer hour (0-23), returns:
    - pct_plugged_in        : fraction of all events occurring in that hour
    - soc_mean              : mean SoC at plug-in
    - soc_p05               : 5th percentile SoC
    - soc_p95               : 95th percentile SoC
    - total_flexibility_kwh : sum of flexibility across all agents plugged in during that hour
    - mean_flexibility_kwh  : mean flexibility across all agents plugged in during that hour

    Parameters
    ----------
    df : pd.DataFrame
        Output of run_population().

    Returns
    -------
    pd.DataFrame
        One row per hour (0-23).
    """
    if df.empty:
        return pd.DataFrame()

    df = df.copy()
    df["hour_bin"] = df["plugin_hour"].apply(int)

    hourly = (
        df.groupby("hour_bin")
        .agg(
            event_count=("soc_at_plugin", "count"),
            soc_mean=("soc_at_plugin", "mean"),
            soc_p05=("soc_at_plugin", lambda x: np.percentile(x, 5)),
            soc_p95=("soc_at_plugin", lambda x: np.percentile(x, 95)),
            total_flexibility_kwh=("flexibility_kwh", "sum"),  
            mean_flexibility_kwh=("flexibility_kwh", "mean"),  
        )
        .reindex(range(24), fill_value=0)
        .reset_index()
        .rename(columns={"hour_bin": "hour"})
    )

    total_events = hourly["event_count"].sum()
    hourly["pct_plugged_in"] = hourly["event_count"] / max(total_events, 1)

    return hourly
