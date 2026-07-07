"""
app.py
------
Streamlit dashboard for the EV driver behaviour simulator.

Two tabs:
    1. Single Agent  — simulate one driver, see their plug in times and SoC
    2. Population    — simulate many agents, see aggregate hourly patterns

Run with:
    streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta

from simulator.archetypes import load_archetypes
from simulator.agent import EVDriver
from simulator.population import run_population, compute_hourly_stats

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="EV Driver Simulator",
    page_icon="🔋",
    layout="wide",
)

st.title("🔋 EV Driver Behaviour Simulator")
st.caption("Axle Energy — Data Science Technical Exercise")

# ── Load archetypes (cached so we don't re-read CSV on every interaction) ─────
@st.cache_data
def get_archetypes():
    return load_archetypes()

archetypes = get_archetypes()
archetype_names = {v.name: k for k, v in archetypes.items()}

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab1, tab2 = st.tabs(["🚗 Single Agent", "👥 Population"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — SINGLE AGENT
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.subheader("Single Agent Simulation")
    st.write(
        "Simulate one EV driver over a chosen period. "
        "Each run with the same seed is fully reproducible."
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        selected_name = st.selectbox(
            "Archetype",
            options=list(archetype_names.keys()),
        )
        profile = archetypes[archetype_names[selected_name]]

        st.markdown("**Archetype summary**")
        st.markdown(f"- Population share: **{profile.population_share:.0%}**")
        st.markdown(f"- Battery: **{profile.battery_capacity_kwh} kWh**")
        st.markdown(f"- Charger: **{profile.charger_kw} kW**")
        st.markdown(f"- Avg plug-in freq: **{profile.plugin_freq:.1f}/day**")
        st.markdown(f"- Mean plug-in SoC: **{profile.soc_mean:.0%}**")

    with col2:
        start = st.date_input("Start date", value=date(2024, 1, 1))
        end = st.date_input("End date", value=date(2024, 3, 31))

    with col3:
        seed = st.number_input("Random seed", value=42, min_value=0, max_value=9999)
        st.write("")
        run_single = st.button("▶ Run simulation", key="single")

    if run_single:
        if end <= start:
            st.error("End date must be after start date.")
        else:
            driver = EVDriver(profile=profile, driver_id=0, seed=int(seed))
            df = driver.simulate_period(str(start), str(end))

            if df.empty:
                st.warning("No plug-in events in this period — try a longer range.")
            else:
                st.success(f"**{len(df)} plug-in events** over {(end - start).days} days")

                m1, m2, m3 = st.columns(3)

                m1.metric(
                    "Total plug-in events",
                    f"{len(df_pop):,}"
                )
                m2.metric(
                    "Total energy needed (kWh)",
                    f"{df_pop['energy_needed_kwh'].sum():,.0f}"
                )
                m3.metric(
                    "Total flexibility available (kWh)",
                    f"{df_pop['flexibility_kwh'].sum():,.0f}"
                )
                col_a, col_b = st.columns(2)

                # Chart 1: plug-in events over time (x=date, y=hour, size=SoC)
                with col_a:
                    fig1 = px.scatter(
                        df,
                        x="date",
                        y="plugin_hour",
                        color="soc_at_plugin",
                        size="energy_needed_kwh",
                        color_continuous_scale="RdYlGn",
                        range_color=[0, 1],
                        labels={
                            "plugin_hour": "Plug-in hour",
                            "soc_at_plugin": "SoC at plug-in",
                            "date": "Date",
                            "energy_needed_kwh": "Energy needed (kWh)",
                        },
                        title="Plug-in events over time",
                    )
                    fig1.update_layout(yaxis=dict(range=[0, 24]))
                    st.plotly_chart(fig1, use_container_width=True)

                # Chart 2: SoC at plug-in histogram
                with col_b:
                    fig2 = px.histogram(
                        df,
                        x="soc_at_plugin",
                        nbins=20,
                        color_discrete_sequence=["#FF6B35"],
                        labels={"soc_at_plugin": "SoC at plug-in"},
                        title="Distribution of SoC at plug-in",
                    )
                    fig2.update_layout(xaxis=dict(tickformat=".0%", range=[0, 1]))
                    st.plotly_chart(fig2, use_container_width=True)

                # Raw data expander
                with st.expander("View raw data"):
                    st.dataframe(df)
                    csv = df.to_csv(index=False)
                    st.download_button("Download CSV", csv, "agent_events.csv", "text/csv")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — POPULATION
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("Population Simulation")
    st.write(
        "Run many agents simultaneously to see population-level patterns. "
        "Compare archetypes or view the aggregate distribution of plug-in behaviour."
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        n_agents = st.slider(
            "Agents per archetype", min_value=5, max_value=100, value=30, step=5
        )
        weight_by_share = st.checkbox(
            "Weight by population share",
            value=False,
            help="Scale agent counts proportionally to real-world archetype prevalence",
        )

    with col2:
        pop_start = st.date_input("Start date", value=date(2024, 1, 1), key="pop_start")
        pop_end = st.date_input("End date", value=date(2024, 3, 31), key="pop_end")

    with col3:
        selected_archetypes = st.multiselect(
            "Archetypes to include",
            options=list(archetype_names.keys()),
            default=list(archetype_names.keys()),
        )
        pop_seed = st.number_input("Random seed", value=42, min_value=0, max_value=9999, key="pop_seed")
        run_pop = st.button("▶ Run population simulation", key="population")

    if run_pop:
        if pop_end <= pop_start:
            st.error("End date must be after start date.")
        elif not selected_archetypes:
            st.error("Select at least one archetype.")
        else:
            filtered_archetypes = {
                archetype_names[name]: archetypes[archetype_names[name]]
                for name in selected_archetypes
            }

            with st.spinner("Simulating population..."):
                df_pop = run_population(
                    archetypes=filtered_archetypes,
                    n_agents_per_archetype=n_agents,
                    start_date=str(pop_start),
                    end_date=str(pop_end),
                    base_seed=int(pop_seed),
                    weight_by_population_share=weight_by_share,
                )

            if df_pop.empty:
                st.warning("No events generated — try more agents or a longer period.")
            else:
                total_agents = n_agents * len(filtered_archetypes)
                st.success(
                    f"**{len(df_pop):,} plug-in events** from "
                    f"**{total_agents} agents** over "
                    f"**{(pop_end - pop_start).days} days**"
                )

                hourly = compute_hourly_stats(df_pop)

                col_a, col_b = st.columns(2)

                # Chart 1: % plugged in by hour with SoC overlay
                with col_a:
                    fig3 = go.Figure()

                    fig3.add_trace(go.Bar(
                        x=hourly["hour"],
                        y=hourly["pct_plugged_in"],
                        name="% plugged in",
                        marker_color="#FF6B35",
                        opacity=0.7,
                        yaxis="y1",
                    ))

                    fig3.add_trace(go.Scatter(
                        x=hourly["hour"],
                        y=hourly["soc_mean"],
                        name="Mean SoC",
                        line=dict(color="#2196F3", width=2),
                        yaxis="y2",
                    ))

                    fig3.add_trace(go.Scatter(
                        x=hourly["hour"],
                        y=hourly["soc_p95"],
                        name="95th percentile SoC",
                        line=dict(color="#2196F3", width=1, dash="dash"),
                        yaxis="y2",
                    ))

                    fig3.add_trace(go.Scatter(
                        x=hourly["hour"],
                        y=hourly["soc_p05"],
                        name="5th percentile SoC",
                        line=dict(color="#2196F3", width=1, dash="dot"),
                        yaxis="y2",
                    ))

                    fig3.update_layout(
                        title="Plug-in frequency and SoC by hour of day",
                        xaxis=dict(title="Hour of day", tickmode="linear", dtick=2),
                        yaxis=dict(title="Fraction of events", tickformat=".0%"),
                        yaxis2=dict(
                            title="SoC at plug-in",
                            overlaying="y",
                            side="right",
                            tickformat=".0%",
                            range=[0, 1],
                        ),
                        legend=dict(orientation="h", y=-0.2),
                    )
                    st.plotly_chart(fig3, use_container_width=True)

                # Chart 2: SoC distribution by archetype
                with col_b:
                    fig4 = px.box(
                        df_pop,
                        x="archetype",
                        y="soc_at_plugin",
                        color="archetype",
                        labels={
                            "soc_at_plugin": "SoC at plug-in",
                            "archetype": "Archetype",
                        },
                        title="SoC at plug-in by archetype",
                    )
                    fig4.update_layout(
                        yaxis=dict(tickformat=".0%", range=[0, 1]),
                        showlegend=False,
                    )
                    st.plotly_chart(fig4, use_container_width=True)

                # Chart 3: plug-in hour distribution by archetype
                fig5 = px.histogram(
                    df_pop,
                    x="plugin_hour",
                    color="archetype",
                    nbins=48,
                    barmode="overlay",
                    opacity=0.6,
                    labels={"plugin_hour": "Hour of day", "archetype": "Archetype"},
                    title="Plug-in time distribution by archetype",
                )
                fig5.update_layout(xaxis=dict(range=[0, 24], dtick=2))
                st.plotly_chart(fig5, use_container_width=True)

                # Chart 4: aggregate flexibility available by hour
                st.markdown("---")
                st.markdown("### ⚡ Grid Flexibility Available by Hour")
                st.write(
                    "Flexibility is the energy each driver *could* accept beyond their target SoC. "
                    "This represents the headroom Axle could use for grid balancing."
                )

                col_c, col_d = st.columns(2)

                with col_c:
                    fig6 = go.Figure()

                    # Bar: total fleet flexibility by hour
                    fig6.add_trace(go.Bar(
                        x=hourly["hour"],
                        y=hourly["total_flexibility_kwh"],
                        name="Total flexibility (kWh)",
                        marker_color="#4CAF50",
                        opacity=0.8,
                    ))

                    fig6.update_layout(
                        title="Total fleet flexibility available by hour",
                        xaxis=dict(title="Hour of day", dtick=2),
                        yaxis=dict(title="Flexibility (kWh)"),
                        showlegend=False,
                    )
                    st.plotly_chart(fig6, use_container_width=True)
                
                with col_d:
                    fig7 = px.box(
                        df_pop,
                        x="archetype",
                        y="flexibility_kwh",
                        color="archetype",
                        labels={
                            "flexibility_kwh": "Flexibility per session (kWh)",
                            "archetype": "Archetype",
                        },
                        title="Per-session flexibility by archetype",
                    )
                    fig7.update_layout(showlegend=False)
                    st.plotly_chart(fig7, use_container_width=True)

                with st.expander("View raw data"):
                    st.dataframe(df_pop)
                    csv_pop = df_pop.to_csv(index=False)
                    st.download_button(
                        "Download CSV", csv_pop, "population_events.csv", "text/csv"
                    )
                    