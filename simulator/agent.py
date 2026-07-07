"""
agent.py
--------
Defines the DriverProfile dataclass (archetype parameters) and the
EVDriver agent class which simulates a single driver over a time period.

Design decisions:
- DriverProfile is a plain dataclass so it is easy to serialise / inspect
- EVDriver is stateless between days (i.i.d. sampling). A natural extension
    would be to carry SoC forward across days so that a high drain day makes
    the next plug in SoC lower.
- Plug in time and SoC are both modelled as clipped Gaussians. The means
    come directly from the archetype CSV; std values are assumed (see README).
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DriverProfile:
    """
    Parameters describing one archetype of EV driver.
    All distribution parameters refer to the plug in event.
    """
    name: str
    population_share: float          # fraction of population this archetype represents

    # Plug in time (hour of day, 0-23)
    plugin_hour_mean: float          # e.g. 18.0 = 6pm
    plugin_hour_std: float           # spread in hours — assumed, not in data

    # State of charge at plug in (0.0 - 1.0)
    soc_mean: float                  # e.g. 0.68
    soc_std: float                   # spread — assumed, not in data
    soc_min: float                   # lower clip bound
    soc_max: float                   # upper clip bound 

    # Behaviour
    plugin_freq: float               # mean plug-ins per day (can be < 1)
    charger_kw: float                # charger power in kW
    battery_capacity_kwh: float      # usable battery size in kWh
    charging_duration_hrs: float     # typical session duration in hours
    miles_per_year: float            # annual mileage
    target_soc: float                # desired SoC after charging


class EVDriver:
    """
    A single simulated EV driver agent.

    For each day in a simulation period, the agent either plugs in or not,
    and if it does, samples a plug in time and SoC from its profile distributions.

    Parameters
    ----------
    profile : DriverProfile
        The archetype parameters for this driver.
    driver_id : int
        Unique identifier — useful when running population simulations.
    seed : int, optional
        Random seed for reproducibility. If None, results will differ each run.
    """

    def __init__(self, profile: DriverProfile, driver_id: int, seed: Optional[int] = None):
        self.profile = profile
        self.driver_id = driver_id
        self.rng = np.random.default_rng(seed)

    def simulate_day(self, date: pd.Timestamp) -> Optional[dict]:
        """
        Simulate one day for this agent.

        Returns a dict describing the plug in event, or None if the driver
        did not plug in that day.

        Plug in probability is taken directly from plugin_freq in the profile.
        The same probability is used for weekdays and weekends — a natural
        extension would be to split these (e.g. commuters less likely at weekends).
        """
        if self.rng.random() > self.profile.plugin_freq:
            return None

        # Sample plug in hour — clipped Gaussian, stays within 0-23
        plugin_hour = float(np.clip(
            self.rng.normal(self.profile.plugin_hour_mean, self.profile.plugin_hour_std),
            0, 23.99
        ))

        # Sample SoC at plug in — clipped Gaussian
        soc = float(np.clip(
            self.rng.normal(self.profile.soc_mean, self.profile.soc_std),
            self.profile.soc_min,
            self.profile.soc_max
        ))

        # Driver charges to target SoC
        energy_needed = max(0, self.profile.target_soc - soc) * self.profile.battery_capacity_kwh

        return {
            "driver_id":             self.driver_id,
            "archetype":             self.profile.name,
            "date":                  date.date(),
            "day_of_week":           date.day_name(),
            "plugin_hour":           round(plugin_hour, 2),
            "soc_at_plugin":         round(soc, 3),
            "target_soc":            round(self.profile.target_soc, 3),
            "energy_needed_kwh":     energy_needed,
            "charger_kw":            self.profile.charger_kw,
            "charging_duration_hrs": self.profile.charging_duration_hrs,
            "battery_capacity_kwh":  self.profile.battery_capacity_kwh,
            # Energy between target and physical max
            "flexibility_kwh":       (self.profile.soc_max - self.profile.target_soc) * self.profile.battery_capacity_kwh
        }

    def simulate_period(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Simulate this agent over a date range.

        Parameters
        ----------
        start_date, end_date : str
            Date strings in any format pandas understands, e.g. "2024-01-01".

        Returns
        -------
        pd.DataFrame
            One row per plug-in event. Empty DataFrame if no events occurred.
        """
        events = []
        for date in pd.date_range(start_date, end_date, freq="D"):
            event = self.simulate_day(date)
            if event:
                events.append(event)

        if not events:
            return pd.DataFrame()

        return pd.DataFrame(events)
