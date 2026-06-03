"""
Simulation scenarios for Satellite Collision Avoidance project.

Orbital elements for sat2 objects are pre-computed to guarantee controlled
miss distances at the TCA time. All units: km, deg, km/s.

Scenario 1 -- Low-Risk Near-Miss (Pc ~ 1e-6)
Scenario 2 -- High-Risk Conjunction + Avoidance Maneuver (Pc ~ 1.6e-4)
Scenario 3 -- Delta-V Sensitivity Analysis
Scenario 4 -- Multi-Debris Conjunction Management
"""

import numpy as np
from satellite import Satellite
from collision_detection import conjunction_data, print_cdm, PC_ACTION_THRESHOLD
from avoidance import plan_avoidance_maneuver, print_maneuver_report
import visualization as viz


def _time_array(hours, dt_s=10):
    # 10-second step is fine enough for cubic-spline TCA refinement
    return np.arange(0, hours * 3600 + dt_s, dt_s, dtype=float)


# ---------------------------------------------------------------
# Primary active satellite (same for all scenarios)
# ---------------------------------------------------------------
def _primary_sat(cov_pos_var):
    # Only position covariance changes between scenarios; attitude/velocity cov fixed
    return Satellite(
        name="SAT-A (active)",
        a=6778.0, e=0.0, i=53.0, raan=0.0, argp=0.0, nu=0.0,
        covariance=np.diag([cov_pos_var] * 3 + [1e-8] * 3),
    )


# =====================================================================
# SCENARIO 1: Low-Risk Near-Miss Detection
# =====================================================================
def scenario1_low_risk_near_miss():
    print("\n" + "=" * 65)
    print("  SCENARIO 1: Low-Risk Near-Miss Detection")
    print("=" * 65)

    sat1 = _primary_sat(cov_pos_var=4.0)   # sigma = 2 km
    # Pre-computed elements: 5 km miss at T=3000 s
    sat2 = Satellite(
        name="SAT-B (debris)",
        a=6767.0, e=0.0027, i=168.06, raan=89.68, argp=66.32, nu=359.18,
        covariance=np.diag([9.0, 9.0, 9.0, 1e-7, 1e-7, 1e-7]),
    )

    t_arr = _time_array(2)
    cdm = conjunction_data(sat1, sat2, t_arr)
    print_cdm(cdm)

    viz.plot_orbits_3d(
        [cdm["positions1"], cdm["positions2"]],
        [sat1.name, sat2.name],
        title="Scenario 1 -- Low-Risk Conjunction",
        filename="s1_orbits_3d.png",
        highlight_tca=([cdm["tca_index"]], [cdm["tca_index"]]),
    )
    viz.plot_miss_distance(
        t_arr, cdm["distances"],
        cdm["tca_time_s"], cdm["miss_distance_km"],
        title="Scenario 1 -- Miss Distance Over Time",
        filename="s1_miss_distance.png",
    )
    viz.plot_relative_motion(
        cdm["positions1"], cdm["positions2"], cdm["tca_index"],
        title="Scenario 1 -- Relative Motion (LVLH Frame)",
        filename="s1_relative_motion.png",
    )
    return cdm


# =====================================================================
# SCENARIO 2: High-Risk Conjunction + Avoidance Maneuver
# =====================================================================
def scenario2_high_risk_avoidance():
    print("\n" + "=" * 65)
    print("  SCENARIO 2: High-Risk Conjunction + Avoidance Maneuver")
    print("=" * 65)

    sat1 = _primary_sat(cov_pos_var=0.01)  # sigma = 0.1 km
    # Pre-computed elements: 0.3 km miss at T=3000 s
    sat2 = Satellite(
        name="DEBRIS-1 (dead sat)",
        a=6767.0, e=0.0026, i=168.02, raan=89.7, argp=73.07, nu=352.4,
        covariance=np.diag([0.25, 0.25, 0.25, 1e-7, 1e-7, 1e-7]),
    )

    t_arr = _time_array(2)
    cdm = conjunction_data(sat1, sat2, t_arr)
    print_cdm(cdm)

    result = None
    if cdm["pc"] >= PC_ACTION_THRESHOLD or cdm["miss_distance_km"] < 1.0:
        print("\n  >> Pc above threshold -- planning avoidance maneuver...")
        result = plan_avoidance_maneuver(
            sat1, sat2, t_arr,
            strategy="optimal",
            maneuver_lead_time_s=1800,
        )
        print_maneuver_report(result)

        viz.plot_orbits_3d(
            [result["new_positions1"], result["positions2"], cdm["positions1"]],
            [sat1.name + " (post-maneuver)", sat2.name, sat1.name + " (original)"],
            title="Scenario 2 -- Post-Maneuver Orbits",
            filename="s2_orbits_3d.png",
        )
        viz.plot_miss_distance(
            t_arr, cdm["distances"],
            cdm["tca_time_s"], cdm["miss_distance_km"],
            maneuver_distances=result["new_distances"],
            title="Scenario 2 -- Miss Distance: Before vs. After Maneuver",
            filename="s2_miss_distance.png",
        )
        viz.plot_relative_motion(
            cdm["positions1"], cdm["positions2"], cdm["tca_index"],
            man_pos1=result["new_positions1"],
            title="Scenario 2 -- Relative Motion (LVLH Frame)",
            filename="s2_relative_motion.png",
        )
        print("  Rendering conjunction animation (this takes ~15 s)...")
        viz.animate_conjunction(
            cdm["positions1"], cdm["positions2"],
            t_arr, cdm["tca_time_s"],
            labels=[sat1.name, sat2.name],
            title="Scenario 2 -- Conjunction Window: Original vs. After Maneuver",
            filename="s2_conjunction_animation.gif",
            window_minutes=5,
            man_positions1=result["new_positions1"],
        )
    else:
        print("  >> Pc below threshold -- no maneuver needed.")

    return cdm, result


# =====================================================================
# SCENARIO 3: Delta-V Sensitivity Analysis
# =====================================================================
def scenario3_dv_sensitivity():
    print("\n" + "=" * 65)
    print("  SCENARIO 3: Delta-V Sensitivity Analysis")
    print("=" * 65)

    sat1 = _primary_sat(cov_pos_var=0.01)
    sat2 = Satellite(
        name="DEBRIS-1",
        a=6767.0, e=0.0026, i=168.02, raan=89.7, argp=73.07, nu=352.4,
        covariance=np.diag([0.25, 0.25, 0.25, 1e-7, 1e-7, 1e-7]),
    )

    t_arr = _time_array(2)
    cdm = conjunction_data(sat1, sat2, t_arr)
    print(f"  Baseline: miss={cdm['miss_distance_km']*1000:.1f} m  Pc={cdm['pc']:.3e}")

    from avoidance import apply_maneuver, _lvlh_axes
    from collision_detection import probability_of_collision

    tca_t = cdm["tca_time_s"]
    t_man = max(tca_t - 1800, t_arr[0])
    pos1, vel1 = sat1.propagate(t_arr)
    pos2, vel2 = sat2.propagate(t_arr)
    idx_man = int(np.searchsorted(t_arr, t_man))
    r_hat, t_hat, n_hat = _lvlh_axes(pos1[idx_man], vel1[idx_man])

    dv_range_ms = np.linspace(0, 50, 40)
    miss_vals, pc_vals = [], []

    print("  Computing Pc vs. delta-V curve (along-track)...")
    for dv_ms in dv_range_ms:
        dv_km = (dv_ms / 1000) * t_hat
        np1, nv1 = apply_maneuver(sat1, dv_km, t_man, t_arr)
        nd = np.linalg.norm(np1 - pos2, axis=1)
        idx_tca = int(np.argmin(nd))
        pc = probability_of_collision(
            np1[idx_tca], pos2[idx_tca],
            nv1[idx_tca], vel2[idx_tca],
            sat1.covariance, sat2.covariance,
        )
        miss_vals.append(nd[idx_tca] * 1000)
        pc_vals.append(max(pc, 1e-14))

    viz.plot_dv_tradeoff(
        dv_range_ms, miss_vals, pc_vals,
        original_miss_m=cdm["miss_distance_km"] * 1000,
        original_pc=cdm["pc"],
        title="Scenario 3 -- Delta-V vs. Miss Distance & Pc",
        filename="s3_dv_tradeoff.png",
    )

    # Lead-time sweep — 4 different dV magnitudes
    lead_times_h = np.arange(0.1, 1.01, 0.05)
    dv_levels_ms = [2, 5, 15, 50]   # m/s
    all_pc_curves, all_labels = [], []

    print("  Computing Pc vs. lead-time for multiple dV levels...")
    for dv_ms in dv_levels_ms:
        pc_leads = []
        for lt_h in lead_times_h:
            t_man_lt = max(tca_t - lt_h * 3600, t_arr[0])
            idx_lt = int(np.searchsorted(t_arr, t_man_lt))
            _, t_hat_lt, _ = _lvlh_axes(pos1[idx_lt], vel1[idx_lt])
            dv_km_lt = (dv_ms / 1000) * t_hat_lt
            np1, nv1 = apply_maneuver(sat1, dv_km_lt, t_man_lt, t_arr)
            nd = np.linalg.norm(np1 - pos2, axis=1)
            idx_tca = int(np.argmin(nd))
            pc = probability_of_collision(
                np1[idx_tca], pos2[idx_tca],
                nv1[idx_tca], vel2[idx_tca],
                sat1.covariance, sat2.covariance,
            )
            pc_leads.append(max(pc, 1e-14))
        all_pc_curves.append(pc_leads)
        all_labels.append(f"dV = {dv_ms} m/s")

    viz.plot_pc_timeline(
        all_pc_curves, lead_times_h,
        curve_labels=all_labels,
        title="Scenario 3 -- Pc vs. Maneuver Lead Time (along-track burn)",
        filename="s3_pc_vs_leadtime.png",
    )

    print(f"  Min Pc @ 50 m/s burn: {min(pc_vals):.3e}")
    return cdm, dv_range_ms, miss_vals, pc_vals


# =====================================================================
# SCENARIO 4: Multi-Debris Environment
# =====================================================================
def scenario4_multi_debris():
    print("\n" + "=" * 65)
    print("  SCENARIO 4: Multi-Debris Conjunction Management")
    print("=" * 65)

    active = _primary_sat(cov_pos_var=0.01)

    # Pre-computed elements with controlled miss distances at staggered TCAs
    debris_catalog = [
        Satellite(
            "DEBRIS-A", a=6775.7, e=0.0012, i=132.49,
            raan=89.75, argp=355.18, nu=11.83,
            covariance=np.diag([4.0, 4.0, 4.0, 1e-7, 1e-7, 1e-7]),
        ),  # 8 km miss @ ~3600s -> LOW
        Satellite(
            "DEBRIS-B", a=6775.3, e=0.0017, i=86.54,
            raan=90.02, argp=201.92, nu=118.98,
            covariance=np.diag([0.25, 0.25, 0.25, 1e-7, 1e-7, 1e-7]),
        ),  # 0.4 km miss @ ~4200s -> HIGH
        Satellite(
            "DEBRIS-C", a=6776.0, e=0.0005, i=29.41,
            raan=90.36, argp=352.47, nu=291.89,
            covariance=np.diag([1.0, 1.0, 1.0, 1e-7, 1e-7, 1e-7]),
        ),  # 2 km miss @ ~5000s -> LOW/MEDIUM
        Satellite(
            "DEBRIS-D", a=6778.0, e=0.0001, i=2.19,
            raan=90.51, argp=358.18, nu=271.78,
            covariance=np.diag([0.01, 0.01, 0.01, 1e-8, 1e-8, 1e-8]),
        ),  # 0.15 km miss @ ~5500s -> CRITICAL
        Satellite(
            "DEBRIS-E", a=6778.5, e=0.001, i=111.34,
            raan=269.71, argp=153.9, nu=224.24,
            covariance=np.diag([4.0, 4.0, 4.0, 1e-7, 1e-7, 1e-7]),
        ),  # 6 km miss @ ~7200s -> LOW
    ]

    t_arr = _time_array(3)
    cdm_list = []

    for debris in debris_catalog:
        cdm = conjunction_data(active, debris, t_arr)
        cdm_list.append(cdm)
        print_cdm(cdm)

    cdm_list.sort(key=lambda c: c["pc"], reverse=True)

    viz.plot_multi_conjunction_timeline(
        cdm_list, t_total_h=3,
        filename="s4_conjunction_timeline.png",
    )

    # Handle the highest-risk conjunction
    highest = cdm_list[0]
    result = None
    if highest["pc"] >= PC_ACTION_THRESHOLD or highest["miss_distance_km"] < 1.0:
        print(f"\n  >> Most critical: {highest['sat2']} -- planning maneuver...")
        debris_obj = next(d for d in debris_catalog if d.name == highest["sat2"])
        result = plan_avoidance_maneuver(
            active, debris_obj, t_arr,
            strategy="optimal",
            maneuver_lead_time_s=1800,
        )
        print_maneuver_report(result)

    return cdm_list, result


# =====================================================================
# Summary comparison across all scenarios
# =====================================================================
def plot_all_scenario_summary(s1_cdm, s2_cdm, s2_result, s4_cdm_list):
    scenarios = [
        "S1: Low Risk",
        "S2: High Risk\n(before maneuver)",
    ]
    misses = [
        s1_cdm["miss_distance_km"] * 1000,
        s2_cdm["miss_distance_km"] * 1000,
    ]
    pcs = [
        s1_cdm["pc"],
        s2_cdm["pc"],
    ]

    if s2_result:
        scenarios.append("S2: High Risk\n(after maneuver)")
        misses.append(s2_result["new_miss_km"] * 1000)
        pcs.append(s2_result["new_pc"])

    for cdm in s4_cdm_list[:3]:
        scenarios.append(f"S4: {cdm['sat2']}")
        misses.append(cdm["miss_distance_km"] * 1000)
        pcs.append(max(cdm["pc"], 1e-14))

    viz.plot_scenario_comparison(
        scenarios, misses, pcs,
        filename="all_scenarios_comparison.png",
    )
