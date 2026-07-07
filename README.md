# EV Driver Behaviour Simulator

A simulator of EV driver charging behaviour.

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the interactive dashboard
streamlit run app.py

# Run as a CLI script
python run_simulation.py

# CLI options
python run_simulation.py --n-agents 100 --start 2024-01-01 --end 2024-06-30 --output results.csv
python run_simulation.py --archetype daily_commuter
python run_simulation.py --weight-by-share   # scale agents by real-world population proportions
```

---

## Project Structure

```
ev_simulator/
├── simulator/
│   ├── agent.py        # EVDriver class and DriverProfile dataclass
│   ├── archetypes.py   # Loads archetype parameters from CSV
│   └── population.py   # Runs N agents, returns aggregated DataFrame
├── data/
│   └── archetypes.csv  # Archetype parameters
├── app.py              # Streamlit dashboard (single agent + population views)
├── run_simulation.py   # CLI entry point
├── requirements.txt
└── README.md
```

---

## Design Decisions

### What I prioritised
The brief asked for two things: **when somebody plugs in** and **their SoC at plug in**. I focused on modelling these two outputs well rather than building a full drive cycle model. The result is a lightweight, interpretable simulator that directly uses the archetype data provided.

### Time Allocation
Given the guidline of 3-5 hours to spend on this task, I allocated my time as follows:
1. **Knowledge Gathering** - 3 hours: This included reading the task and Octopus report, making notes and outlining my approach to the task, anticipating any blockers, building out simple functions to get an idea for the flow of the simulator.
2. **AI-assisted Coding** - 30 minutes: Utilising Claude I built out skeletons for the simulator functions and the Streamlit app.
3. **Code Improvements** - 1.5 hours: This included fleshing out and finalising the functions, correcting some AI mistakes, stress testing the dashboard and code, and adding documentation.

### Agent model
Each agent is parameterised by an archetype (loaded from CSV) and samples independently for each day:

- **Plug in probability**: taken directly from `Plug-in frequency (per day)` in the archetype data
- **Plug in time**: sampled from a clipped Gaussian centred on the archetype's plug in hour
- **SoC at plug in**: sampled from a clipped Gaussian centred on the archetype's `Plug-in SoC`

Agents are currently stateless across days (i.i.d. sampling). This is a simplification, in reality a day of heavy driving would leave the battery lower, making the next plug-in SoC correlated with previous days.

### Assumptions made (not in the data)
Two parameters were not provided in the archetype CSV and had to be assumed:

| Parameter | Value | Rationale |
|---|---|---|
| `plugin_hour_std` | 1.0 hour | Most drivers plug in within ~1 hour of their typical time |
| `soc_std` | 0.08 | ~8% spread around mean SoC; consistent with moderate day-to-day variation |

These are flagged in `archetypes.py` as `ASSUMED_PLUGIN_HOUR_STD` and `ASSUMED_SOC_STD` so they are easy to tune.

### Why load archetypes from CSV
The archetype parameters are loaded directly from the CSV rather than hardcoded. This means the simulator behaviour can be updated without touching source code — important for a production system where parameters might be regularly revised from new data.

### What I would add with more time
1. **Day to day SoC correlation**: carry SoC state forward across days. A low SoC plug in today implies fuller battery tomorrow, which affects the next plug in SoC.
2. **Weekday/weekend split**: commuters are less likely to plug in at weekends; long distance drivers more so. The data hints at this but doesn't provide separate probabilities.
3. **Bimodal plug in times**: some archetypes likely have two plug in peaks (morning + evening). A Gaussian mixture model would capture this better than a single Gaussian.
4. **Charging session output**: extend the output to include what happens *during* the session (kW drawn over time), which is ultimately what Axle needs for grid flexibility analysis.
5. **Validation against CNZ report**: use the published summary statistics to calibrate the assumed std values rather than setting them manually.

---

## Data Sources
- Archetype definitions: provided by Axle Energy (data/archetypes.csv)
- Original research basis: [Intelligent Octopus / Centre for Net Zero Report, May 2022](https://www.centrefornetzero.org/wp-content/uploads/2022/05/Intelligent-Octopus-CNZ-Report-May-2022.pdf)
