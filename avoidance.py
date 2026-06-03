"""
Collision avoidance maneuver planning.

Strategies implemented:
  - Along-track (tangential) burn — most fuel-efficient for LEO
  - Radial burn
  - Cross-track (normal) burn
  - Optimal delta-V search (minimise |dV| while meeting Pc threshold)
"""

import numpy as np
from copy import deepcopy
from orbital_mechanics import propagate_orbit, elements_to_state, state_to_elements
from collision_detection import conjunction_data, probability_of_collision, PC_ACTION_THRESHOLD


def apply_maneuver(sat, dv_eci, maneuver_time_s, t_arr):
    """
    Create a virtual satellite with an impulsive delta-V applied at maneuver_time_s.

    The satellite is propagated to maneuver_time_s, velocity is changed by dv_eci,
    then propagated forward from that point. Returns new (positions, velocities).
    """
    from satellite import Satellite

    r0, v0 = sat.initial_state()

    # Clamp maneuver time to a valid range
    maneuver_time_s = float(np.clip(maneuver_time_s, t_arr[0], t_arr[-1]))

    if maneuver_time_s <= t_arr[0] + 1e-6:
        # Maneuver at (or before) simulation start — apply dV to initial state
        r_burn = r0
        v_burn = v0 + dv_eci
        pos_post, vel_post = propagate_orbit(r_burn, v_burn, t_arr)
        return pos_post, vel_post

    # Propagate up to the burn point (~10-second steps, same as main t_arr)
    n_steps = max(int(maneuver_time_s / 10) + 2, 3)
    t_burn = np.linspace(0.0, maneuver_time_s, n_steps)
    pos_pre, vel_pre = propagate_orbit(r0, v0, t_burn)
    r_burn = pos_pre[-1]
    v_burn = vel_pre[-1] + dv_eci  # impulsive delta-V applied instantaneously

    # Post-burn time array: reset to 0 at the maneuver point
    t_post = t_arr[t_arr >= maneuver_time_s] - maneuver_time_s
    if len(t_post) < 2:
        # Edge case: maneuver is very close to the end of the simulation
        t_post = np.array([0.0, t_arr[-1] - maneuver_time_s])
    pos_post, vel_post = propagate_orbit(r_burn, v_burn, t_post)

    # Join pre-burn and post-burn segments; n_pre is the splice index
    n_pre = int(np.searchsorted(t_arr, maneuver_time_s))
    pos_full = np.vstack([pos_pre[:n_pre], pos_post])
    vel_full = np.vstack([vel_pre[:n_pre], vel_post])

    # Pad or trim so the output always has exactly len(t_arr) rows
    N = len(t_arr)
    if len(pos_full) < N:
        pos_full = np.vstack([pos_full, np.tile(pos_full[-1], (N - len(pos_full), 1))])
        vel_full = np.vstack([vel_full, np.tile(vel_full[-1], (N - len(vel_full), 1))])
    else:
        pos_full = pos_full[:N]
        vel_full = vel_full[:N]

    return pos_full, vel_full


def _lvlh_axes(r, v):
    """
    Compute LVLH (Local Vertical Local Horizontal) unit vectors.
    Returns: r_hat (radial), t_hat (along-track), n_hat (cross-track)
    """
    r_hat = r / np.linalg.norm(r)         # radial: points away from Earth center
    h_vec = np.cross(r, v)
    n_hat = h_vec / np.linalg.norm(h_vec) # normal: perpendicular to orbital plane
    t_hat = np.cross(n_hat, r_hat)        # along-track: tangent to orbit, prograde
    return r_hat, t_hat, n_hat


def plan_avoidance_maneuver(sat1, sat2, t_arr, strategy="along-track",
                            maneuver_lead_time_s=3600.0):
    """
    Plan a collision avoidance maneuver for sat1 to avoid sat2.

    Parameters
    ----------
    sat1, sat2          : Satellite objects
    t_arr               : time array (s)
    strategy            : 'along-track' | 'radial' | 'cross-track' | 'optimal'
    maneuver_lead_time_s: how many seconds before TCA to burn

    Returns
    -------
    result dict with maneuver details and new trajectory
    """
    # Baseline conjunction
    cdm0 = conjunction_data(sat1, sat2, t_arr)
    tca_t = cdm0["tca_time_s"]
    t_man = max(tca_t - maneuver_lead_time_s, t_arr[0])

    # LVLH frame at maneuver point
    pos1, vel1 = sat1.propagate(t_arr)
    idx_man = int(np.searchsorted(t_arr, t_man))
    r_man = pos1[idx_man]
    v_man = vel1[idx_man]
    r_hat, t_hat, n_hat = _lvlh_axes(r_man, v_man)

    if strategy == "optimal":
        return _optimal_maneuver(sat1, sat2, t_arr, t_man, r_hat, t_hat, n_hat, cdm0)

    # Direction vector in ECI
    direction = {"along-track": t_hat, "radial": r_hat, "cross-track": n_hat}[strategy]

    # Binary search for minimum delta-V that reduces Pc below threshold
    dv_mag = _find_minimum_dv(sat1, sat2, t_arr, t_man, direction, cdm0)

    dv_eci = dv_mag * direction
    new_pos1, new_vel1 = apply_maneuver(sat1, dv_eci, t_man, t_arr)

    # Recompute Pc with new trajectory
    pos2, vel2 = sat2.propagate(t_arr)
    new_distances = np.linalg.norm(new_pos1 - pos2, axis=1)
    new_idx = int(np.argmin(new_distances))
    new_miss = new_distances[new_idx]
    new_pc = probability_of_collision(
        new_pos1[new_idx], pos2[new_idx],
        new_vel1[new_idx], vel2[new_idx],
        sat1.covariance, sat2.covariance,
    )

    return {
        "strategy": strategy,
        "maneuver_time_s": t_man,
        "maneuver_time_h": t_man / 3600,
        "lead_time_h": (tca_t - t_man) / 3600,
        "dv_mag_m_s": dv_mag * 1000,      # m/s
        "dv_eci_km_s": dv_eci,
        "original_pc": cdm0["pc"],
        "new_pc": new_pc,
        "original_miss_km": cdm0["miss_distance_km"],
        "new_miss_km": new_miss,
        "new_positions1": new_pos1,
        "new_velocities1": new_vel1,
        "new_distances": new_distances,
        "positions2": pos2,
        "original_cdm": cdm0,
    }


def _find_minimum_dv(sat1, sat2, t_arr, t_man, direction, cdm0,
                     max_dv=0.05, n_steps=40):
    """
    Binary search for smallest dV (km/s) that lowers Pc to 10x below threshold.
    Target = 1e-5 so that the maneuver produces a clearly visible miss distance change.
    max_dv = 0.05 km/s = 50 m/s upper bound.
    """
    target_pc = PC_ACTION_THRESHOLD / 10   # 1e-5 — one order of magnitude safety margin
    pos2, vel2 = sat2.propagate(t_arr)
    lo, hi = 0.0, max_dv  # search bracket in km/s

    for _ in range(n_steps):
        mid = (lo + hi) / 2  # bisect
        dv_eci = mid * direction
        new_pos1, new_vel1 = apply_maneuver(sat1, dv_eci, t_man, t_arr)
        new_dist = np.linalg.norm(new_pos1 - pos2, axis=1)
        idx = int(np.argmin(new_dist))  # new TCA index after the maneuver
        pc = probability_of_collision(
            new_pos1[idx], pos2[idx],
            new_vel1[idx], vel2[idx],
            sat1.covariance, sat2.covariance,
        )
        if pc < target_pc:
            hi = mid  # maneuver works — try a smaller dV
        else:
            lo = mid  # not enough — need a bigger dV

    # hi converges to the smallest dV that satisfies the Pc target
    return hi


def _optimal_maneuver(sat1, sat2, t_arr, t_man, r_hat, t_hat, n_hat, cdm0):
    """
    Search over all six axes (±along-track, ±radial, ±cross-track) to find
    the minimum-delta-V maneuver. Retrograde burns are often more efficient
    and are now included in the search space.
    """
    best = None
    # Test all 6 LVLH directions: retrograde burns are often cheaper than prograde
    for strategy, direction in [
        ("along-track (+)", t_hat),
        ("along-track (-)", -t_hat),
        ("radial (+)",      r_hat),
        ("radial (-)",      -r_hat),
        ("cross-track (+)", n_hat),
        ("cross-track (-)", -n_hat),
    ]:
        pos2, vel2 = sat2.propagate(t_arr)
        dv_mag = _find_minimum_dv(sat1, sat2, t_arr, t_man, direction, cdm0)

        if best is None or dv_mag < best["dv_mag"]:  # keep the cheapest direction
            dv_eci = dv_mag * direction
            new_pos1, new_vel1 = apply_maneuver(sat1, dv_eci, t_man, t_arr)
            new_dist = np.linalg.norm(new_pos1 - pos2, axis=1)
            idx = int(np.argmin(new_dist))
            pc = probability_of_collision(
                new_pos1[idx], pos2[idx],
                new_vel1[idx], vel2[idx],
                sat1.covariance, sat2.covariance,
            )
            best = {
                "dv_mag": dv_mag,
                "strategy": strategy,
                "dv_eci": dv_eci,
                "new_pc": pc,
                "new_miss": new_dist[idx],
                "new_pos1": new_pos1,
                "new_vel1": new_vel1,
                "new_dist": new_dist,
                "pos2": pos2,
            }

    return {
        "strategy": f"optimal ({best['strategy']})",
        "maneuver_time_s": t_man,
        "maneuver_time_h": t_man / 3600,
        "lead_time_h": (cdm0["tca_time_s"] - t_man) / 3600,
        "dv_mag_m_s": best["dv_mag"] * 1000,
        "dv_eci_km_s": best["dv_eci"],
        "original_pc": cdm0["pc"],
        "new_pc": best["new_pc"],
        "original_miss_km": cdm0["miss_distance_km"],
        "new_miss_km": best["new_miss"],
        "new_positions1": best["new_pos1"],
        "new_velocities1": best["new_vel1"],
        "new_distances": best["new_dist"],
        "positions2": best["pos2"],
        "original_cdm": cdm0,
    }


def print_maneuver_report(result):
    print("\n" + "=" * 60)
    print("  AVOIDANCE MANEUVER REPORT")
    print("=" * 60)
    print(f"  Strategy    : {result['strategy']}")
    print(f"  Burn time   : T-{result['lead_time_h']:.2f} h before TCA")
    print(f"  Delta-V     : {result['dv_mag_m_s']:.4f} m/s")
    print(f"  Pc before   : {result['original_pc']:.3e}  "
          f"Miss: {result['original_miss_km']*1000:.1f} m")
    print(f"  Pc after    : {result['new_pc']:.3e}  "
          f"Miss: {result['new_miss_km']*1000:.1f} m")
    status = "SUCCESS" if result['new_pc'] < PC_ACTION_THRESHOLD else "INSUFFICIENT"
    print(f"  Status      : {status}")
    print("=" * 60)
