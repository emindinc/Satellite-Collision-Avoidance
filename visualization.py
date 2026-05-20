"""
Visualization module for satellite collision avoidance simulation.
All figures are saved to the results/ directory.
"""

import os
import numpy as np
import matplotlib
matplotlib.use("Agg")          # non-interactive backend for saving
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.patches import FancyArrowPatch
from orbital_mechanics import RE

RESULTS_DIR = "results"
os.makedirs(RESULTS_DIR, exist_ok=True)


def _savefig(fig, filename):
    path = os.path.join(RESULTS_DIR, filename)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  [saved] {path}")
    return path


# ─────────────────────────────────────────────
# 1. 3-D Orbit Plot
# ─────────────────────────────────────────────
def plot_orbits_3d(trajectories, labels, title="Satellite Orbits",
                   filename="orbits_3d.png", highlight_tca=None):
    """
    trajectories : list of (N,3) position arrays (km)
    highlight_tca: (idx1, idx2) tuple of TCA indices for each trajectory
    """
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection="3d")

    # Earth sphere
    u = np.linspace(0, 2 * np.pi, 60)
    v = np.linspace(0, np.pi, 40)
    xs = RE * np.outer(np.cos(u), np.sin(v))
    ys = RE * np.outer(np.sin(u), np.sin(v))
    zs = RE * np.outer(np.ones_like(u), np.cos(v))
    ax.plot_surface(xs, ys, zs, color="deepskyblue", alpha=0.25, linewidth=0)

    colors = ["tab:blue", "tab:orange", "tab:green", "tab:red", "tab:purple"]
    for idx, (pos, lbl) in enumerate(zip(trajectories, labels)):
        c = colors[idx % len(colors)]
        ax.plot(pos[:, 0], pos[:, 1], pos[:, 2], color=c, lw=1.2, label=lbl)
        ax.scatter(pos[0, 0], pos[0, 1], pos[0, 2], color=c, s=50, zorder=5)

    if highlight_tca is not None:
        for idx, (pos, tca_i) in enumerate(zip(trajectories, highlight_tca)):
            ax.scatter(pos[tca_i, 0], pos[tca_i, 1], pos[tca_i, 2],
                       s=120, zorder=6, color=colors[idx % len(colors)],
                       edgecolors="red", linewidths=2,
                       label=f"TCA {labels[idx]}")

    ax.set_xlabel("X (km)")
    ax.set_ylabel("Y (km)")
    ax.set_zlabel("Z (km)")
    ax.set_title(title)
    ax.legend(loc="upper left", fontsize=8)
    ax.set_box_aspect([1, 1, 1])
    return _savefig(fig, filename)


# ─────────────────────────────────────────────
# 2. Miss Distance Over Time
# ─────────────────────────────────────────────
def plot_miss_distance(t_arr, distances, tca_time_s, miss_dist_km,
                       maneuver_distances=None, title="Miss Distance Over Time",
                       filename="miss_distance.png"):
    fig, ax = plt.subplots(figsize=(10, 5))
    t_h = t_arr / 3600
    ax.plot(t_h, distances * 1000, "b-", lw=2, label="Original trajectory")

    if maneuver_distances is not None:
        ax.plot(t_h, maneuver_distances * 1000, "g--", lw=2,
                label="After avoidance maneuver")

    ax.axvline(tca_time_s / 3600, color="red", ls="--", lw=1.5, label="TCA")
    ax.axhline(10, color="gray", ls=":", lw=1.2, label="Hard-body radius (10 m)")
    ax.axhline(1000, color="orange", ls=":", lw=1.2, label="Warning zone (1 km)")

    ax.scatter([tca_time_s / 3600], [miss_dist_km * 1000],
               color="red", s=100, zorder=5, label=f"Min: {miss_dist_km*1000:.1f} m")

    ax.set_xlabel("Time (hours)")
    ax.set_ylabel("Miss Distance (m)")
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_yscale("log")
    return _savefig(fig, filename)


# ─────────────────────────────────────────────
# 3. Probability of Collision vs. Time-to-TCA
# ─────────────────────────────────────────────
def plot_pc_timeline(pc_curves, lead_times_h, curve_labels=None,
                     threshold=1e-4,
                     title="Pc vs. Maneuver Lead Time",
                     filename="pc_timeline.png"):
    """
    pc_curves : list of arrays, OR single array (backwards-compatible)
    curve_labels : list of strings, one per curve
    """
    fig, ax = plt.subplots(figsize=(10, 5))

    # Accept both single array and list of arrays
    if not isinstance(pc_curves[0], (list, np.ndarray)):
        pc_curves = [pc_curves]
        curve_labels = curve_labels or ["Pc estimate"]

    palette = ["tab:blue", "tab:green", "tab:orange", "tab:red", "tab:purple"]
    for idx, (curve, lbl) in enumerate(zip(pc_curves, curve_labels or [])):
        ax.semilogy(lead_times_h, curve,
                    color=palette[idx % len(palette)],
                    marker="o", ms=4, lw=2, label=lbl)

    ax.axhline(threshold, color="red", ls="--", lw=1.5,
               label=f"Action threshold ({threshold:.0e})")
    ax.axhline(1e-5, color="orange", ls=":", lw=1.2,
               label="Monitor threshold (1e-5)")

    ax.set_xlabel("Lead Time Before TCA (hours)")
    ax.set_ylabel("Probability of Collision")
    ax.set_title(title)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.invert_xaxis()
    return _savefig(fig, filename)


# ─────────────────────────────────────────────
# 4. Delta-V vs. Miss Distance Trade-off
# ─────────────────────────────────────────────
def plot_dv_tradeoff(dv_range_ms, miss_values_m, pc_values,
                     original_miss_m, original_pc,
                     title="Delta-V Trade-off Analysis",
                     filename="dv_tradeoff.png"):
    fig, ax1 = plt.subplots(figsize=(10, 5))

    color1 = "tab:blue"
    ax1.plot(dv_range_ms, miss_values_m, color=color1, lw=2, label="Miss distance (m)")
    ax1.set_xlabel("Delta-V (m/s)")
    ax1.set_ylabel("Miss Distance (m)", color=color1)
    ax1.tick_params(axis="y", labelcolor=color1)
    ax1.axhline(original_miss_m, color=color1, ls=":", alpha=0.5,
                label=f"Original miss: {original_miss_m:.0f} m")

    ax2 = ax1.twinx()
    color2 = "tab:orange"
    ax2.semilogy(dv_range_ms, pc_values, color=color2, lw=2, ls="--", label="Pc")
    ax2.axhline(1e-4, color="red", ls="--", lw=1, label="Threshold 1e-4")
    ax2.set_ylabel("Probability of Collision", color=color2)
    ax2.tick_params(axis="y", labelcolor=color2)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=8)

    ax1.set_title(title)
    ax1.grid(True, alpha=0.3)
    return _savefig(fig, filename)


# ─────────────────────────────────────────────
# 5. Scenario Comparison Bar Chart
# ─────────────────────────────────────────────
def plot_scenario_comparison(scenario_names, miss_distances_m, pc_values,
                              filename="scenario_comparison.png"):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    colors = ["green" if m > 1000 else "orange" if m > 100 else "red"
              for m in miss_distances_m]
    bars1 = ax1.bar(scenario_names, miss_distances_m, color=colors, edgecolor="black")
    ax1.axhline(1000, color="orange", ls="--", lw=1.5, label="1 km warning")
    ax1.axhline(10, color="red", ls="--", lw=1.5, label="10 m hard body")
    ax1.set_ylabel("Miss Distance (m)")
    ax1.set_title("Miss Distance by Scenario")
    ax1.legend(fontsize=8)
    ax1.set_yscale("log")
    for bar, val in zip(bars1, miss_distances_m):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() * 1.1,
                 f"{val:.0f} m", ha="center", va="bottom", fontsize=8)

    pc_colors = ["green" if p < 1e-5 else "orange" if p < 1e-4 else "red"
                 for p in pc_values]
    bars2 = ax2.bar(scenario_names, pc_values, color=pc_colors, edgecolor="black")
    ax2.axhline(1e-4, color="red", ls="--", lw=1.5, label="Action threshold")
    ax2.axhline(1e-5, color="orange", ls="--", lw=1.5, label="Monitor threshold")
    ax2.set_ylabel("Probability of Collision")
    ax2.set_title("Pc by Scenario")
    ax2.legend(fontsize=8)
    ax2.set_yscale("log")
    for bar, val in zip(bars2, pc_values):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() * 1.5,
                 f"{val:.1e}", ha="center", va="bottom", fontsize=7, rotation=45)

    plt.suptitle("Scenario Comparison Summary", fontsize=13, fontweight="bold")
    plt.xticks(rotation=15, ha="right")
    plt.tight_layout()
    return _savefig(fig, filename)


# ─────────────────────────────────────────────
# 6. Multi-debris conjunction timeline
# ─────────────────────────────────────────────
def plot_multi_conjunction_timeline(cdm_list, t_total_h,
                                    filename="multi_conjunction_timeline.png"):
    fig, ax = plt.subplots(figsize=(12, 5))

    risk_colors = {"LOW": "green", "MEDIUM": "gold",
                   "HIGH": "orange", "CRITICAL": "red"}
    for i, cdm in enumerate(cdm_list):
        color = risk_colors.get(cdm["risk_level"], "blue")
        # Smaller miss distance = larger bubble (more dangerous)
        bubble = min(2500, 80 / (cdm["miss_distance_km"] + 0.005))
        ax.scatter(cdm["tca_time_h"], i,
                   s=bubble, color=color, edgecolors="black", zorder=5)
        ax.annotate(
            f"{cdm['sat2']}\nPc={cdm['pc']:.1e}\n{cdm['miss_distance_km']*1000:.0f} m",
            (cdm["tca_time_h"], i), textcoords="offset points",
            xytext=(8, 0), fontsize=7, va="center"
        )

    ax.set_yticks(range(len(cdm_list)))
    ax.set_yticklabels([c["sat2"] for c in cdm_list])
    ax.set_xlabel("Time (hours from epoch)")
    ax.set_title("Multi-Debris Conjunction Timeline\n"
                 "(bubble size ∝ miss distance — smaller = closer approach)")
    ax.set_xlim(0, t_total_h)
    ax.grid(True, axis="x", alpha=0.3)

    # Legend
    for risk, color in risk_colors.items():
        ax.scatter([], [], color=color, label=risk, s=60, edgecolors="black")
    ax.legend(title="Risk Level", loc="lower right", fontsize=8)

    return _savefig(fig, filename)


# ─────────────────────────────────────────────
# 7. Relative motion in LVLH frame
# ─────────────────────────────────────────────
def plot_relative_motion(pos1, pos2, tca_idx,
                         man_pos1=None, title="Relative Motion (LVLH Frame)",
                         filename="relative_motion.png"):
    """Plot relative position of sat2 w.r.t. sat1 in along-track vs radial plane."""
    rel = pos2 - pos1
    r_hats = pos1 / np.linalg.norm(pos1, axis=1, keepdims=True)

    radial = np.einsum("ij,ij->i", rel, r_hats)
    along = np.linalg.norm(rel - radial[:, None] * r_hats, axis=1)
    along *= np.sign(rel[:, 0] - radial * r_hats[:, 0] + 1e-15)

    fig, ax = plt.subplots(figsize=(8, 8))
    sc = ax.scatter(along / 1000, radial / 1000,
                    c=np.arange(len(along)), cmap="plasma", s=8)
    plt.colorbar(sc, ax=ax, label="Time step index")

    ax.scatter(along[tca_idx] / 1000, radial[tca_idx] / 1000,
               color="red", s=200, zorder=6, label="TCA")

    if man_pos1 is not None:
        rel_m = pos2 - man_pos1
        r_hats_m = man_pos1 / np.linalg.norm(man_pos1, axis=1, keepdims=True)
        rad_m = np.einsum("ij,ij->i", rel_m, r_hats_m)
        al_m = np.linalg.norm(rel_m - rad_m[:, None] * r_hats_m, axis=1)
        al_m *= np.sign(rel_m[:, 0] - rad_m * r_hats_m[:, 0] + 1e-15)
        ax.plot(al_m / 1000, rad_m / 1000, "g--", lw=1.5,
                label="After maneuver", alpha=0.7)

    ax.set_xlabel("Along-Track (km)")
    ax.set_ylabel("Radial (km)")
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_aspect("equal")
    return _savefig(fig, filename)


# ─────────────────────────────────────────────
# 8. Conjunction Window Animation
# ─────────────────────────────────────────────
def animate_conjunction(positions1, positions2, t_arr, tca_time_s,
                        labels, title="Conjunction Animation",
                        filename="conjunction_animation.gif",
                        window_minutes=5, fps=15,
                        man_positions1=None):
    """
    Animate the conjunction window (TCA ± window_minutes).

    If man_positions1 is given, renders a side-by-side comparison:
    left = original trajectory, right = post-maneuver trajectory.
    Saves as GIF (requires Pillow: pip install pillow).
    """
    from matplotlib.animation import FuncAnimation, PillowWriter

    t_start = max(tca_time_s - window_minutes * 60, t_arr[0])
    t_end   = min(tca_time_s + window_minutes * 60, t_arr[-1])
    mask    = (t_arr >= t_start) & (t_arr <= t_end)
    t_win   = t_arr[mask]
    p1w     = positions1[mask]
    p2w     = positions2[mask]
    man_p1w = man_positions1[mask] if man_positions1 is not None else None

    dists_orig = np.linalg.norm(p1w - p2w, axis=1)
    dists_man  = (np.linalg.norm(man_p1w - p2w, axis=1)
                  if man_p1w is not None else None)
    tca_min_dist = dists_orig.min()

    n_panels = 2 if man_p1w is not None else 1
    fig = plt.figure(figsize=(7 * n_panels, 5.5))
    axes = [fig.add_subplot(1, n_panels, i + 1, projection="3d")
            for i in range(n_panels)]

    sat_colors = ["dodgerblue", "tomato"]
    trail_len  = 20   # frames of trail

    def _draw_earth(ax):
        u = np.linspace(0, 2 * np.pi, 18)
        v = np.linspace(0, np.pi, 12)
        xs = RE * np.outer(np.cos(u), np.sin(v))
        ys = RE * np.outer(np.sin(u), np.sin(v))
        zs = RE * np.outer(np.ones_like(u), np.cos(v))
        ax.plot_surface(xs, ys, zs, color="deepskyblue", alpha=0.2, linewidth=0)

    def _draw_full_traj(ax, p1_full, p2_full):
        ax.plot(p1_full[:, 0], p1_full[:, 1], p1_full[:, 2],
                color=sat_colors[0], alpha=0.08, lw=0.7)
        ax.plot(p2_full[:, 0], p2_full[:, 1], p2_full[:, 2],
                color=sat_colors[1], alpha=0.08, lw=0.7)

    def _setup_ax(ax, subtitle=""):
        ax.set_xlabel("X (km)", fontsize=8)
        ax.set_ylabel("Y (km)", fontsize=8)
        ax.set_zlabel("Z (km)", fontsize=8)
        ax.set_title(subtitle, fontsize=9)
        span = RE * 1.35
        ax.set_xlim(-span, span)
        ax.set_ylim(-span, span)
        ax.set_zlim(-span, span)
        ax.view_init(elev=20, azim=30)

    def update(frame):
        for ax in axes:
            ax.clear()
            _draw_earth(ax)

        t_rel  = t_win[frame] - tca_time_s
        t_label = f"T{'+' if t_rel >= 0 else ''}{t_rel:.0f} s"
        d_orig = dists_orig[frame] * 1000
        is_tca = dists_orig[frame] <= tca_min_dist * 1.05

        # ── Panel 0: original ──────────────────────────────────────────
        ax0 = axes[0]
        _draw_full_traj(ax0, positions1, positions2)

        trail_s = max(0, frame - trail_len)
        ax0.plot(p1w[trail_s:frame+1, 0], p1w[trail_s:frame+1, 1],
                 p1w[trail_s:frame+1, 2], color=sat_colors[0], lw=2)
        ax0.plot(p2w[trail_s:frame+1, 0], p2w[trail_s:frame+1, 1],
                 p2w[trail_s:frame+1, 2], color=sat_colors[1], lw=2)

        dot_size   = 350 if is_tca else 120
        edge_color = "yellow" if is_tca else "white"
        ax0.scatter(p1w[frame, 0], p1w[frame, 1], p1w[frame, 2],
                    color=sat_colors[0], s=dot_size, edgecolors=edge_color,
                    linewidths=2.5, zorder=6)
        ax0.scatter(p2w[frame, 0], p2w[frame, 1], p2w[frame, 2],
                    color=sat_colors[1], s=dot_size, edgecolors=edge_color,
                    linewidths=2.5, zorder=6)

        subtitle0 = (f"ORIGINAL  |  {t_label}  |  Miss: {d_orig:.0f} m"
                     + ("  *** TCA ***" if is_tca else ""))
        _setup_ax(ax0, subtitle0)

        # ── Panel 1: post-maneuver (if provided) ───────────────────────
        if man_p1w is not None:
            ax1 = axes[1]
            _draw_full_traj(ax1, man_positions1, positions2)

            ax1.plot(man_p1w[trail_s:frame+1, 0], man_p1w[trail_s:frame+1, 1],
                     man_p1w[trail_s:frame+1, 2], color=sat_colors[0], lw=2)
            ax1.plot(p2w[trail_s:frame+1, 0], p2w[trail_s:frame+1, 1],
                     p2w[trail_s:frame+1, 2], color=sat_colors[1], lw=2)

            d_man = dists_man[frame] * 1000
            ax1.scatter(man_p1w[frame, 0], man_p1w[frame, 1], man_p1w[frame, 2],
                        color=sat_colors[0], s=120, edgecolors="white",
                        linewidths=2, zorder=6)
            ax1.scatter(p2w[frame, 0], p2w[frame, 1], p2w[frame, 2],
                        color=sat_colors[1], s=120, edgecolors="white",
                        linewidths=2, zorder=6)
            _setup_ax(ax1, f"AFTER MANEUVER  |  {t_label}  |  Miss: {d_man:.0f} m")

        fig.suptitle(title, fontsize=12, fontweight="bold")
        return []

    # Use every other frame to halve file size while keeping smooth motion
    frame_indices = list(range(0, len(t_win), 2))
    anim = FuncAnimation(fig, update, frames=frame_indices,
                         interval=1000 // fps, blit=False)

    path = os.path.join(RESULTS_DIR, filename)
    anim.save(path, writer=PillowWriter(fps=fps), dpi=72)
    plt.close(fig)
    print(f"  [saved] {path}")
    return path
