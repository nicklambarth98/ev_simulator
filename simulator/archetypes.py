"""
archetypes.py
-------------
Loads archetype parameters directly from the CSV provided,
converting them into DriverProfile objects ready for simulation.

Design decisions:
- Loading from CSV rather than hardcoding means the archetypes can be
    updated without touching source code. Important for a production system
    where parameters may be tuned.
- Two parameters are NOT in the CSV and must be assumed:
    plugin_hour_std : set to 1.0 hour (i.e. most plug-ins within 1hr of mean)
    soc_std         : set to 0.08 (i.e. ~8% spread around the mean SoC)
Both are clearly flagged here and in the README.
"""

import pandas as pd
from pathlib import Path
from typing import Dict
from simulator.agent import DriverProfile

# Resolving path relative to this file so it works from any directory
DATA_PATH = Path(__file__).parent.parent / "data" / "archetypes.csv"

# Assumed std values — not provided in the archetype data
ASSUMED_PLUGIN_HOUR_STD = 1.0   # hours
ASSUMED_SOC_STD = 0.08          # fraction of full charge


def _parse_percent(value: str) -> float:
    """Convert '68%' to 0.68, handling both string and numeric input."""
    return float(str(value).strip("%")) / 100


def _parse_hour(time_str: str) -> float:
    """Convert '6:00 PM' to 18.0, '10:00 PM' to 22.0, '12:00 AM' to 0.0"""
    return float(pd.to_datetime(time_str, format="%I:%M %p").hour)


def _make_key(name: str) -> str:
    """Convert 'Average (UK)' to 'average_uk' for use as dict key."""
    return (
        name.lower()
        .replace(" ", "_")
        .replace("(", "")
        .replace(")", "")
        .strip("_")
    )

def validate_archetypes(archetypes: Dict[str, DriverProfile]) -> None:
    """
    Validate the archetypes DataFrame to ensure that the values are within expected ranges.

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame containing archetype data.

    Raises
    ------
    ValueError
        If any validation checks fail.
    """
    for key, profile in archetypes.items():
        assert 0 <= profile.soc_mean <= 1, f"{profile.name}: soc_mean out of range"
        assert 0 <= profile.target_soc <= 1, f"{profile.name}: target_soc out of range"
        assert profile.plugin_freq >= 0, f"{profile.name}: plugin_freq must be positive"



def load_archetypes(path: Path = DATA_PATH) -> Dict[str, DriverProfile]:
    """
    Load archetype definitions from CSV and return a dict of DriverProfiles.

    Parameters
    ----------
    path : Path
        Path to the archetypes CSV file.

    Returns
    -------
    Dict[str, DriverProfile]
        Keys are snake_case archetype names, values are DriverProfile objects.

    """
    # Raising an error if data not found at expected path, rather than silently failing or returning empty dict.
    if not path.exists():
        raise FileNotFoundError(
            f"Archetypes CSV not found at {path}. "
        )

    df = pd.read_csv(path)
    archetypes = {}

    for _, row in df.iterrows():
        plugin_hour = _parse_hour(row["Plug-in time"])
        soc_at_plugin = _parse_percent(row["Plug-in SoC"])
        soc_requirement = _parse_percent(row["SoC requirement"])
        target_soc = _parse_percent(row["Target SoC"])
        population_share = _parse_percent(row["% of population"])

        key = _make_key(row["Name"])

        archetypes[key] = DriverProfile(
            name=str(row["Name"]),
            population_share=population_share,

            plugin_hour_mean=plugin_hour,
            plugin_hour_std=ASSUMED_PLUGIN_HOUR_STD,

            soc_mean=soc_at_plugin,
            soc_std=ASSUMED_SOC_STD,
            soc_min=max(0.05, soc_at_plugin - soc_requirement - 0.10),
            soc_max=0.95,  # Some buffer for battery health
            target_soc=target_soc,

            plugin_freq=float(row["Plug-in frequency (per day)"]),
            charger_kw=float(row["Charger kW"]),
            battery_capacity_kwh=float(row["Battery (kWh)"]),
            charging_duration_hrs=float(row["Charging duration (hrs)"]),
            miles_per_year=float(row["Miles/yr"]),
        )
    validate_archetypes(archetypes)

    return archetypes
