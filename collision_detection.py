"""
Conjunction analysis and probability of collision calculations.

Methods implemented:
  - TCA (Time of Closest Approach) via minimisation
  - Miss distance and relative velocity at TCA
  - Probability of Collision (Pc) using Chan's 2D analytical formula
"""

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.interpolate import CubicSpline


HARD_BODY_RADIUS = 0.010  # km  (combined hard-body radius, ~10 m)
PC_ACTION_THRESHOLD = 1e-4  # standard operations threshold


def _miss_distance(t, pos1_func, pos2_func):
    """Scalar miss distance at time t (for minimisation)."""
    return np.linalg.norm(pos1_func(t) - pos2_func(t))


def find_tca(positions1, positions2, t_arr):
    """
    Find Time of Closest Approach (TCA).

    Coarse scan over the propagated arrays, then cubic-spline refinement
    around the minimum to recover sub-step accuracy.

    Returns
    -------
    tca_index : int    nearest index in t_arr
    tca_time  : float  refined TCA time (s)
    miss_dist : float  refined miss distance (km)
    """
    diffs = np.linalg.norm(positions1 - positions2, axis=1)
    idx = int(np.argmin(diffs))

    # Refine with spline over a window of ±3 points around the coarse minimum
    i_lo = max(0, idx - 3)
    i_hi = min(len(t_arr) - 1, idx + 3)
    t_win = t_arr[i_lo:i_hi + 1]
    d_win = diffs[i_lo:i_hi + 1]

    if len(t_win) >= 4:
        cs = CubicSpline(t_win, d_win)
        res = minimize_scalar(cs, bounds=(t_win[0], t_win[-1]), method="bounded")
        tca_time = float(res.x)
        miss_dist = float(res.fun)
    else:
        tca_time = t_arr[idx]
        miss_dist = diffs[idx]

    return idx, tca_time, miss_dist


def _interp_state(positions, velocities, t_arr, t_query):
    """Linearly interpolate position and velocity at t_query."""
    idx = int(np.searchsorted(t_arr, t_query))
    idx = np.clip(idx, 1, len(t_arr) - 1)
    t0, t1 = t_arr[idx - 1], t_arr[idx]
    alpha = (t_query - t0) / (t1 - t0) if t1 != t0 else 0.0
    r = positions[idx - 1] + alpha * (positions[idx] - positions[idx - 1])
    v = velocities[idx - 1] + alpha * (velocities[idx] - velocities[idx - 1])
    return r, v


def conjunction_data(sat1, sat2, t_arr):
    """
    Full conjunction data message (CDM) for a satellite pair.

    Returns a dict with:
        tca_time, tca_index, miss_distance, relative_speed,
        pc, risk_level, positions1, positions2, velocities1, velocities2
    """
    pos1, vel1 = sat1.propagate(t_arr)
    pos2, vel2 = sat2.propagate(t_arr)

    idx, tca_time, miss_dist = find_tca(pos1, pos2, t_arr)

    # Interpolated state at true TCA for accurate Pc
    r1_tca, v1_tca = _interp_state(pos1, vel1, t_arr, tca_time)
    r2_tca, v2_tca = _interp_state(pos2, vel2, t_arr, tca_time)

    rel_vel = np.linalg.norm(v1_tca - v2_tca)

    pc = probability_of_collision(
        r1_tca, r2_tca, v1_tca, v2_tca,
        sat1.covariance, sat2.covariance,
    )

    risk = _risk_level(pc)

    return {
        "sat1": sat1.name,
        "sat2": sat2.name,
        "tca_time_s": tca_time,
        "tca_time_h": tca_time / 3600,
        "tca_index": idx,
        "miss_distance_km": miss_dist,
        "relative_speed_km_s": rel_vel,
        "pc": pc,
        "risk_level": risk,
        "positions1": pos1,
        "positions2": pos2,
        "velocities1": vel1,
        "velocities2": vel2,
        "distances": np.linalg.norm(pos1 - pos2, axis=1),
    }


def probability_of_collision(r1, r2, v1, v2, cov1, cov2, R_hbr=HARD_BODY_RADIUS):
    """
    Probability of Collision using Chan's 2D projection method.

    The relative position is projected onto the collision plane
    (perpendicular to relative velocity). Combined positional covariance
    is used to compute Pc analytically.

    Parameters
    ----------
    r1, r2 : np.ndarray (3,)   positions at TCA (km)
    v1, v2 : np.ndarray (3,)   velocities at TCA (km/s)
    cov1, cov2 : np.ndarray (6,6)   ECI covariance matrices
    R_hbr  : float             combined hard-body radius (km)

    Returns
    -------
    pc : float   probability of collision [0, 1]
    """
    r_rel = r2 - r1
    v_rel = v2 - v1
    v_rel_mag = np.linalg.norm(v_rel)

    if v_rel_mag < 1e-12:
        return 0.0

    # Unit vectors for collision plane
    e_z = v_rel / v_rel_mag
    e_x = _perpendicular_unit(r_rel, e_z)
    e_y = np.cross(e_z, e_x)

    # Combined position covariance (3x3)
    C_combined = cov1[:3, :3] + cov2[:3, :3]

    # Project onto collision plane (2x3 projection matrix)
    P = np.array([e_x, e_y])          # (2, 3)
    C2d = P @ C_combined @ P.T        # (2, 2)
    x2d = P @ r_rel                   # (2,) — relative position in collision plane

    pc = _chan_pc_2d(x2d, C2d, R_hbr)
    return float(np.clip(pc, 0.0, 1.0))


def _chan_pc_2d(mu, sigma, R):
    """
    Numerically integrate the 2D Gaussian over a disk of radius R.

    Pc = integral over {x^2+y^2 <= R^2} of N(mu, sigma) dA

    Uses scipy.integrate.dblquad for accuracy. Falls back to Monte Carlo
    if the integrand is too concentrated (very small sigma).
    """
    from scipy.integrate import dblquad
    from scipy.stats import multivariate_normal

    # Clamp covariance eigenvalues to avoid singular matrix
    eigvals, eigvecs = np.linalg.eigh(sigma)
    eigvals = np.maximum(eigvals, 1e-20)
    sigma_clamped = eigvecs @ np.diag(eigvals) @ eigvecs.T

    rv = multivariate_normal(mean=mu, cov=sigma_clamped)

    try:
        result, _ = dblquad(
            lambda y, x: rv.pdf([x, y]),
            -R, R,
            lambda x: -np.sqrt(max(R**2 - x**2, 0.0)),
            lambda x:  np.sqrt(max(R**2 - x**2, 0.0)),
            epsabs=1e-10, epsrel=1e-8,
        )
        return float(result)
    except Exception:
        return _mc_pc(mu, sigma_clamped, R)


def _mc_pc(mu, sigma, R, N=500_000):
    """Monte Carlo Pc estimate."""
    rng = np.random.default_rng(42)
    samples = rng.multivariate_normal(mu, sigma, size=N)
    return float(np.sum(np.linalg.norm(samples, axis=1) <= R) / N)


def _perpendicular_unit(v, ref):
    """Unit vector perpendicular to ref in the plane spanned by v and ref."""
    proj = np.dot(v, ref) * ref
    perp = v - proj
    mag = np.linalg.norm(perp)
    if mag < 1e-12:
        # v parallel to ref — pick arbitrary perpendicular
        perp = np.array([1.0, 0.0, 0.0]) - ref[0] * ref
        mag = np.linalg.norm(perp)
    return perp / mag


def _risk_level(pc):
    if pc >= 1e-3:
        return "CRITICAL"
    elif pc >= 1e-4:
        return "HIGH"
    elif pc >= 1e-5:
        return "MEDIUM"
    else:
        return "LOW"


def print_cdm(cdm):
    """Print a formatted Conjunction Data Message."""
    print("=" * 60)
    print("  CONJUNCTION DATA MESSAGE (CDM)")  # noqa
    print("=" * 60)
    print(f"  Primary   : {cdm['sat1']}")
    print(f"  Secondary : {cdm['sat2']}")
    print(f"  TCA       : {cdm['tca_time_h']:.4f} h ({cdm['tca_time_s']:.1f} s)")
    print(f"  Miss Dist : {cdm['miss_distance_km']*1000:.1f} m  ({cdm['miss_distance_km']:.4f} km)")
    print(f"  Rel Speed : {cdm['relative_speed_km_s']:.3f} km/s "
          f"({cdm['relative_speed_km_s']*1000:.1f} m/s)")
    print(f"  Pc        : {cdm['pc']:.3e}")
    print(f"  Risk      : {cdm['risk_level']}")
    print("=" * 60)
