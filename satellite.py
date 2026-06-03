import numpy as np
from dataclasses import dataclass, field
from orbital_mechanics import elements_to_state, propagate_orbit, orbital_period


@dataclass
class Satellite:
    """
    Represents a satellite defined by its Keplerian orbital elements.

    Elements:
        a    : semi-major axis (km)
        e    : eccentricity
        i    : inclination (deg)
        raan : right ascension of ascending node (deg)
        argp : argument of perigee (deg)
        nu   : true anomaly (deg)
    """
    name: str
    a: float        # km
    e: float
    i: float        # deg
    raan: float     # deg
    argp: float     # deg
    nu: float       # deg
    mass: float = 100.0          # kg
    cross_section: float = 4.0   # m^2
    # 6x6 position-velocity covariance matrix in ECI (km^2, km^2/s^2)
    covariance: np.ndarray = field(
        default_factory=lambda: np.diag([1e-4, 1e-4, 1e-4, 1e-8, 1e-8, 1e-8])
    )

    def _rad_elements(self):
        # Angular elements are stored in degrees; propagator expects radians
        return (
            self.a, self.e,
            np.deg2rad(self.i),
            np.deg2rad(self.raan),
            np.deg2rad(self.argp),
            np.deg2rad(self.nu),
        )

    def initial_state(self):
        """Return initial ECI position (km) and velocity (km/s)."""
        return elements_to_state(*self._rad_elements())

    def propagate(self, t_arr):
        """
        Propagate satellite over time array t_arr (seconds from epoch).
        Returns positions (N,3) km and velocities (N,3) km/s.
        """
        r0, v0 = self.initial_state()
        return propagate_orbit(r0, v0, t_arr)

    def period(self):
        """Orbital period in seconds."""
        return orbital_period(self.a)

    def altitude(self):
        """Mean orbital altitude (km) above Earth surface."""
        from orbital_mechanics import RE
        return self.a * (1 - self.e) - RE  # perigee altitude approx

    def __repr__(self):
        return (f"Satellite('{self.name}', a={self.a:.1f} km, "
                f"e={self.e:.4f}, i={self.i:.2f}°, alt~{self.altitude():.1f} km)")
