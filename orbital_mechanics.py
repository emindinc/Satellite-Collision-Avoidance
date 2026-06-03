import numpy as np
from scipy.integrate import solve_ivp

MU = 398600.4418   # Earth gravitational parameter (km^3/s^2)
RE = 6371.0        # Earth radius (km)
J2 = 1.08262668e-3 # J2 perturbation coefficient


def elements_to_state(a, e, i, raan, argp, nu):
    """Convert Keplerian orbital elements to ECI position/velocity vectors."""
    p = a * (1 - e**2)          # semi-latus rectum (km)
    r_mag = p / (1 + e * np.cos(nu))  # orbital radius from focal point (km)

    # Position and velocity in perifocal (PQW) frame
    r_pf = r_mag * np.array([np.cos(nu), np.sin(nu), 0.0])
    h = np.sqrt(MU * p)         # specific angular momentum magnitude
    v_pf = (MU / h) * np.array([-np.sin(nu), e + np.cos(nu), 0.0])

    Q = _rotation_pf_to_eci(raan, i, argp)  # rotation from PQW to ECI
    return Q @ r_pf, Q @ v_pf


def _rotation_pf_to_eci(raan, i, argp):
    """3-1-3 rotation matrix: perifocal -> ECI."""
    # Pre-compute trig values to avoid repeated calls
    cr, sr = np.cos(raan), np.sin(raan)
    ci, si = np.cos(i),    np.sin(i)
    cw, sw = np.cos(argp), np.sin(argp)
    # Standard R3(-Ω) · R1(-i) · R3(-ω) product written out element-by-element
    return np.array([
        [cr*cw - sr*sw*ci,  -cr*sw - sr*cw*ci,  sr*si],
        [sr*cw + cr*sw*ci,  -sr*sw + cr*cw*ci, -cr*si],
        [sw*si,              cw*si,              ci   ],
    ])


def state_to_elements(r, v):
    """Convert ECI state vector to Keplerian orbital elements."""
    r_mag = np.linalg.norm(r)
    v_mag = np.linalg.norm(v)

    h_vec = np.cross(r, v)      # specific angular momentum vector
    h = np.linalg.norm(h_vec)
    n_vec = np.cross([0.0, 0.0, 1.0], h_vec)  # node vector (points to ascending node)
    n = np.linalg.norm(n_vec)

    # Eccentricity vector — points toward periapsis
    e_vec = ((v_mag**2 - MU / r_mag) * r - np.dot(r, v) * v) / MU
    e = np.linalg.norm(e_vec)

    # Vis-viva energy → semi-major axis
    energy = v_mag**2 / 2 - MU / r_mag
    a = -MU / (2 * energy)
    # Inclination: angle between h_vec and Z axis
    i = np.arccos(np.clip(h_vec[2] / h, -1.0, 1.0))

    raan = np.arccos(np.clip(n_vec[0] / n, -1.0, 1.0))
    if n_vec[1] < 0:  # quadrant fix: RAAN ∈ [π, 2π] when node vector has negative y
        raan = 2 * np.pi - raan

    argp = np.arccos(np.clip(np.dot(n_vec, e_vec) / (n * e), -1.0, 1.0))
    if e_vec[2] < 0:  # quadrant fix: ω ∈ [π, 2π] when eccentricity vector points below equatorial plane
        argp = 2 * np.pi - argp

    nu = np.arccos(np.clip(np.dot(e_vec, r) / (e * r_mag), -1.0, 1.0))
    if np.dot(r, v) < 0:  # quadrant fix: ν ∈ [π, 2π] when satellite is past apoapsis (r·v < 0)
        nu = 2 * np.pi - nu

    return a, e, i, raan, argp, nu


def _ode_j2(t, state):
    """Two-body + J2 equations of motion."""
    r = state[:3]
    v = state[3:]
    r_mag = np.linalg.norm(r)
    z2 = r[2]**2   # z² cached — used twice in J2 formula

    a2body = -MU / r_mag**3 * r  # standard two-body gravity
    factor = -1.5 * J2 * MU * RE**2 / r_mag**5  # common J2 pre-factor
    aj2 = factor * np.array([
        r[0] * (1 - 5 * z2 / r_mag**2),   # x component of J2 acceleration
        r[1] * (1 - 5 * z2 / r_mag**2),   # y component
        r[2] * (3 - 5 * z2 / r_mag**2),   # z component (different coefficient)
    ])
    return np.concatenate([v, a2body + aj2])  # [ṙ, r̈]


def propagate_orbit(r0, v0, t_arr):
    """
    Propagate orbit with J2 perturbation over array of times.
    Returns positions (N,3) and velocities (N,3) in km and km/s.
    """
    state0 = np.concatenate([r0, v0])  # 6-element initial state vector
    sol = solve_ivp(
        _ode_j2, (t_arr[0], t_arr[-1]), state0,
        method='RK45', t_eval=t_arr,
        rtol=1e-10, atol=1e-12  # tight tolerances to keep TCA error < 1 m
    )
    # sol.y shape is (6, N); transpose to (N, 6) and split position / velocity
    return sol.y[:3].T, sol.y[3:].T


def orbital_period(a):
    """Orbital period in seconds."""
    return 2 * np.pi * np.sqrt(a**3 / MU)


def relative_velocity(v1, v2):
    """Relative speed between two satellites (km/s)."""
    return np.linalg.norm(v1 - v2)
