import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple

@dataclass
class DriverProfile:
    """Archetype parameters — all distributions defined here."""
    name: str
    # Plug-in time: hour of day (Gaussian or mixture)
    plugin_hour_mean: float       # e.g. 18.5 (6:30pm)
    plugin_hour_std: float        # e.g. 1.5 hours
    # State of Charge at plug-in
    soc_mean: float               # e.g. 0.35 (35%)
    soc_std: float                # e.g. 0.15
    soc_min: float = 0.05
    soc_max: float = 0.95
    # Behaviour pattern
    weekday_prob: float = 0.8     # probability of plugging in on a weekday
    weekend_prob: float = 0.3
    battery_capacity_kwh: float = 60.0


class EVDriver:
    """A single simulated EV driver agent."""
    
    def __init__(self, profile: DriverProfile, driver_id: int, seed: int = None):
        self.profile = profile
        self.driver_id = driver_id
        self.rng = np.random.default_rng(seed)
    
    def simulate_day(self, date) -> dict | None:
        """Returns a plug-in event dict for a given day, or None if no plug-in."""
        is_weekend = date.weekday() >= 5
        prob = self.profile.weekend_prob if is_weekend else self.profile.weekday_prob
        
        if self.rng.random() > prob:
            return None  # didn't plug in today
        
        # Sample plug-in hour
        hour = self.rng.normal(self.profile.plugin_hour_mean, self.profile.plugin_hour_std)
        hour = float(np.clip(hour, 0, 23.99))
        
        # Sample SoC
        soc = self.rng.normal(self.profile.soc_mean, self.profile.soc_std)
        soc = float(np.clip(soc, self.profile.soc_min, self.profile.soc_max))
        
        return {
            "driver_id": self.driver_id,
            "archetype": self.profile.name,
            "date": date,
            "plugin_hour": round(hour, 2),
            "soc_at_plugin": round(soc, 3),
            "battery_capacity_kwh": self.profile.battery_capacity_kwh,
            "energy_needed_kwh": round((1 - soc) * self.profile.battery_capacity_kwh, 2),
        }
    
    def simulate_period(self, start_date, end_date) -> List[dict]:
        import pandas as pd
        events = []
        for date in pd.date_range(start_date, end_date):
            event = self.simulate_day(date)
            if event:
                events.append(event)
        return events