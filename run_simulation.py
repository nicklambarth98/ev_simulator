"""
run_simulation.py
-----------------
Command-line entry point for the EV driver simulator.

Examples
--------
# Run all archetypes, 50 agents each, for 30 days
python run_simulation.py

# Customise the run
python run_simulation.py --n-agents 100 --start 2024-01-01 --end 2024-06-30

# Save output to CSV
python run_simulation.py --output results.csv

# Weight agent counts by real-world population share
python run_simulation.py --weight-by-share
"""

import argparse
import pandas as pd
from simulator.archetypes import load_archetypes
from simulator.population import run_population, compute_hourly_stats


def parse_args():
    parser = argparse.ArgumentParser(
        description="EV Driver Behaviour Simulator — CLI runner"
    )
    parser.add_argument(
        "--n-agents", type=int, default=50,
        help="Number of agents per archetype (default: 50)"
    )
    parser.add_argument(
        "--start", type=str, default="2024-01-01",
        help="Simulation start date YYYY-MM-DD (default: 2024-01-01)"
    )
    parser.add_argument(
        "--end", type=str, default="2024-01-31",
        help="Simulation end date YYYY-MM-DD (default: 2024-01-31)"
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for reproducibility (default: 42)"
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Optional path to save results CSV, e.g. results.csv"
    )
    parser.add_argument(
        "--weight-by-share", action="store_true",
        help="Scale agent counts by real-world population share"
    )
    parser.add_argument(
        "--archetype", type=str, default=None,
        help="Run a single archetype only, e.g. 'daily_commuter'"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    archetypes = load_archetypes()

    # Optionally filter to a single archetype
    if args.archetype:
        if args.archetype not in archetypes:
            print(f"Unknown archetype '{args.archetype}'. Available:")
            for key in archetypes:
                print(f"  {key}")
            return
        archetypes = {args.archetype: archetypes[args.archetype]}

    print(f"\nRunning simulation...")
    print(f"  Archetypes : {', '.join(archetypes.keys())}")
    print(f"  Agents/archetype : {args.n_agents}")
    print(f"  Period : {args.start} to {args.end}")
    print(f"  Seed : {args.seed}\n")

    df = run_population(
        archetypes=archetypes,
        n_agents_per_archetype=args.n_agents,
        start_date=args.start,
        end_date=args.end,
        base_seed=args.seed,
        weight_by_population_share=args.weight_by_share,
    )

    if df.empty:
        print("No plug-in events generated.")
        return

    print(f"Generated {len(df):,} plug-in events\n")

    # Summary by archetype
    summary = (
        df.groupby("archetype")
        .agg(
            events=("soc_at_plugin", "count"),
            mean_soc=("soc_at_plugin", "mean"),
            mean_plugin_hour=("plugin_hour", "mean"),
            mean_energy_kwh=("energy_needed_kwh", "mean"),
        )
        .round(3)
    )
    print("── Summary by archetype ──────────────────────────────")
    print(summary.to_string())

    # Hourly stats
    hourly = compute_hourly_stats(df)
    peak_hour = hourly.loc[hourly["pct_plugged_in"].idxmax(), "hour"]
    print(f"\nPeak plug-in hour: {int(peak_hour):02d}:00")

    # Optionally save
    if args.output:
        df.to_csv(args.output, index=False)
        print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
