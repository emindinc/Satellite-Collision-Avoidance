"""
Monte Carlo Replikasyon Modülü
================================
Simülasyon ve Modelleme Dersi — Final Projesi

Ders gereksinimi (PDF, Sayfa 5):
  "Simülasyonun sadece bir kez değil, güven aralığı oluşturacak kadar
  (örn: 100 replikasyon) koşturulması beklenmektedir."

Yaklaşım:
  Her replikasyonda uyduların başlangıç durumu (pozisyon + hız),
  nominal durumun üzerine uydu kovaryans matrisinden çekilen
  Gauss gürültüsü eklenerek bozulur. Bu, ölçüm belirsizliğini
  ve başlangıç koşulu hassasiyetini modeller.

Çıktılar:
  - Pc dağılımı (histogram + CDF)
  - Miss distance dağılımı
  - %95 bootstrap güven aralığı
  - Konsol özet tablosu
  - results/mc_pc_histogram.png
  - results/mc_cdf.png
  - results/mc_report.txt
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os

from orbital_mechanics import propagate_orbit
from collision_detection import conjunction_data, probability_of_collision, HARD_BODY_RADIUS
from satellite import Satellite

RESULTS_DIR = "results"
os.makedirs(RESULTS_DIR, exist_ok=True)


# temel yardımcılar

def _perturb_state(sat, rng):
    """
    Uydunun başlangıç durumunu kovaryans matrisinden çekilen
    Gaussian gürültü ile boz.

    Returns
    -------
    r_new, v_new : np.ndarray (3,)
    """
    r0, v0 = sat.initial_state()
    cov6 = sat.covariance                    # (6,6)

    # Pozisyon kovaryansı (3x3) ve hız kovaryansı (3x3)
    cov_pos = cov6[:3, :3]
    cov_vel = cov6[3:, 3:]

    dr = rng.multivariate_normal(np.zeros(3), cov_pos)
    dv = rng.multivariate_normal(np.zeros(3), cov_vel)

    return r0 + dr, v0 + dv


def _single_replication(sat1, sat2, t_arr, rng):
    """
    Bir Monte Carlo replikasyonu:
      1. İki uydunun başlangıç durumunu kovaryans ile boz
      2. Yörüngeleri yay
      3. TCA'da Pc ve miss distance hesapla

    Returns
    -------
    pc : float
    miss_km : float
    """
    # Bozulmuş başlangıç koşulları
    r1, v1 = _perturb_state(sat1, rng)
    r2, v2 = _perturb_state(sat2, rng)

    # Yay
    pos1, vel1 = propagate_orbit(r1, v1, t_arr)
    pos2, vel2 = propagate_orbit(r2, v2, t_arr)

    # TCA (kaba tarama)
    dists = np.linalg.norm(pos1 - pos2, axis=1)
    idx = int(np.argmin(dists))
    miss_km = float(dists[idx])

    # Pc
    pc = probability_of_collision(
        pos1[idx], pos2[idx],
        vel1[idx], vel2[idx],
        sat1.covariance, sat2.covariance,
    )
    return float(pc), miss_km


def _bootstrap_ci(data, n_boot=2000, ci=0.95, seed=0):
    """
    Bootstrap ile %95 güven aralığı (ortalama için).

    Returns
    -------
    (ci_lo, ci_hi) : float
    """
    rng = np.random.default_rng(seed)
    means = [np.mean(rng.choice(data, size=len(data), replace=True))
             for _ in range(n_boot)]
    alpha = (1 - ci) / 2
    return float(np.quantile(means, alpha)), float(np.quantile(means, 1 - alpha))


# ana simülasyon döngüsü

def run_monte_carlo(sat1, sat2, t_arr, N=200, seed=42, scenario_name="S2"):
    """
    N replikasyonluk Monte Carlo simülasyonu.

    Parameters
    ----------
    sat1, sat2    : Satellite  — nominal uydu tanımları
    t_arr         : np.ndarray — zaman dizisi (s)
    N             : int        — replikasyon sayısı (varsayılan 200)
    seed          : int        — tekrar üretilebilirlik için RNG tohumu
    scenario_name : str        — grafik başlıkları için

    Returns
    -------
    results : dict
        pc_values, miss_values, mean_pc, std_pc, ci95, P_exceed
    """
    print(f"\n{'='*65}")
    print(f"  MONTE CARLO SİMÜLASYONU — {scenario_name}  (N={N})")
    print(f"{'='*65}")

    rng = np.random.default_rng(seed)
    pc_values   = np.zeros(N)
    miss_values = np.zeros(N)

    for i in range(N):
        pc, miss = _single_replication(sat1, sat2, t_arr, rng)
        pc_values[i]   = pc
        miss_values[i] = miss
        if (i + 1) % 50 == 0 or i == 0:
            print(f"  Rep {i+1:3d}/{N}  Pc={pc:.3e}  miss={miss*1000:.1f} m")

    # İstatistikler
    mean_pc   = float(np.mean(pc_values))
    std_pc    = float(np.std(pc_values))
    median_pc = float(np.median(pc_values))
    mean_miss = float(np.mean(miss_values))
    std_miss  = float(np.std(miss_values))

    ci95_lo, ci95_hi = _bootstrap_ci(pc_values)
    P_exceed = float(np.mean(pc_values >= 1e-4))  # P(Pc ≥ eylem eşiği)

    results = {
        "scenario": scenario_name,
        "N": N,
        "seed": seed,
        "pc_values": pc_values,
        "miss_values": miss_values,
        "mean_pc": mean_pc,
        "std_pc": std_pc,
        "median_pc": median_pc,
        "mean_miss_km": mean_miss,
        "std_miss_km": std_miss,
        "ci95_lo": ci95_lo,
        "ci95_hi": ci95_hi,
        "P_exceed_threshold": P_exceed,
    }

    _print_summary(results)
    _save_plots(results)
    _save_report(results)

    return results


# çıktılar

def _print_summary(r):
    print(f"\n  {'─'*55}")
    print(f"  MONTE CARLO SONUÇ ÖZETİ — {r['scenario']} (N={r['N']})")
    print(f"  {'─'*55}")
    print(f"  Ortalama Pc             : {r['mean_pc']:.4e}")
    print(f"  Standart sapma          : {r['std_pc']:.4e}")
    print(f"  Medyan Pc               : {r['median_pc']:.4e}")
    print(f"  %95 Güven Aralığı       : [{r['ci95_lo']:.4e}, {r['ci95_hi']:.4e}]")
    print(f"  P(Pc ≥ 1e-4)            : {r['P_exceed_threshold']:.3f}  "
          f"({'Manevra gerekli' if r['P_exceed_threshold'] > 0.1 else 'İzle'})")
    print(f"  Ort. miss distance      : {r['mean_miss_km']*1000:.1f} ± "
          f"{r['std_miss_km']*1000:.1f} m")
    print(f"  {'─'*55}\n")


def _save_plots(r):
    pc   = r["pc_values"]
    miss = r["miss_values"] * 1000  # m

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(
        f"Monte Carlo Simülasyonu — {r['scenario']}  (N={r['N']})",
        fontsize=14, fontweight="bold"
    )

    # 1. Pc Histogramı
    ax = axes[0, 0]
    ax.hist(np.log10(pc + 1e-15), bins=30, color="steelblue",
            edgecolor="white", alpha=0.85)
    ax.axvline(np.log10(r["mean_pc"]), color="red", lw=2,
               label=f"Ort. = {r['mean_pc']:.2e}")
    ax.axvline(np.log10(1e-4), color="orange", ls="--", lw=1.5,
               label="Eylem eşiği 1e-4")
    ax.set_xlabel("log₁₀(Pc)")
    ax.set_ylabel("Frekans")
    ax.set_title("Pc Dağılımı (Histogram)")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # 2. Pc Kümülatif Dağılım (CDF)
    ax = axes[0, 1]
    sorted_pc = np.sort(pc)
    cdf = np.arange(1, len(pc) + 1) / len(pc)
    ax.semilogx(sorted_pc + 1e-15, cdf, color="royalblue", lw=2)
    ax.axvline(1e-4, color="red", ls="--", lw=1.5, label="Eylem eşiği")
    ax.axhline(0.95, color="gray", ls=":", lw=1.2, label="%95 CDF")
    # Güven aralığı gösterimi
    ax.axvspan(r["ci95_lo"], r["ci95_hi"], alpha=0.15, color="green",
               label=f"%95 CI: [{r['ci95_lo']:.1e}, {r['ci95_hi']:.1e}]")
    ax.set_xlabel("Çarpışma Olasılığı (Pc)")
    ax.set_ylabel("Kümülatif Olasılık")
    ax.set_title("Pc Kümülatif Dağılımı (CDF)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # 3. Miss Distance Histogramı
    ax = axes[1, 0]
    ax.hist(miss, bins=30, color="darkorange", edgecolor="white", alpha=0.85)
    ax.axvline(r["mean_miss_km"] * 1000, color="red", lw=2,
               label=f"Ort. = {r['mean_miss_km']*1000:.1f} m")
    ax.axvline(10, color="darkred", ls="--", lw=1.5, label="Hard-body 10 m")
    ax.axvline(1000, color="orange", ls=":", lw=1.5, label="Uyarı 1 km")
    ax.set_xlabel("Miss Distance (m)")
    ax.set_ylabel("Frekans")
    ax.set_title("Miss Distance Dağılımı")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # 4. Pc vs. Miss Scatter
    ax = axes[1, 1]
    sc = ax.scatter(miss, pc + 1e-15, c=np.arange(len(pc)),
                    cmap="viridis", alpha=0.5, s=18)
    plt.colorbar(sc, ax=ax, label="Replikasyon indeksi")
    ax.axhline(1e-4, color="red", ls="--", lw=1.5, label="Eylem eşiği")
    ax.axvline(1000, color="orange", ls=":", lw=1.2, label="1 km")
    ax.set_xlabel("Miss Distance (m)")
    ax.set_ylabel("Pc")
    ax.set_yscale("log")
    ax.set_title("Pc vs. Miss Distance (scatter)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    path = os.path.join(RESULTS_DIR, "mc_pc_histogram.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  [saved] {path}")


def _save_report(r):
    path = os.path.join(RESULTS_DIR, "mc_report.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("SATELLITE COLLISION AVOIDANCE — MONTE CARLO RAPORU\n")
        f.write("=" * 65 + "\n\n")
        f.write(f"Senaryo          : {r['scenario']}\n")
        f.write(f"Replikasyon (N)  : {r['N']}\n")
        f.write(f"RNG tohumu       : {r['seed']}\n\n")
        f.write("ÇARPIŞMA OLASILIĞI (Pc)\n")
        f.write(f"  Ortalama       : {r['mean_pc']:.6e}\n")
        f.write(f"  Std. sapma     : {r['std_pc']:.6e}\n")
        f.write(f"  Medyan         : {r['median_pc']:.6e}\n")
        f.write(f"  %95 CI (boot.) : [{r['ci95_lo']:.6e}, {r['ci95_hi']:.6e}]\n")
        f.write(f"  P(Pc >= 1e-4)  : {r['P_exceed_threshold']:.4f}\n\n")
        f.write("MISS DISTANCE\n")
        f.write(f"  Ortalama       : {r['mean_miss_km']*1000:.2f} m\n")
        f.write(f"  Std. sapma     : {r['std_miss_km']*1000:.2f} m\n\n")
        f.write("YORUM\n")
        action = r["P_exceed_threshold"] > 0.1
        f.write(
            f"  N={r['N']} replikasyonun {r['P_exceed_threshold']*100:.1f}%'inde "
            f"Pc eylem eşiğini (1e-4) aşmaktadır.\n"
        )
        f.write(
            f"  {'Manevra planlanması önerilir.' if action else 'İzleme yeterlidir.'}\n"
        )
    print(f"  [saved] {path}")


# hazır senaryo çalıştırıcısı — Senaryo 2 (yüksek riskli)

def run_scenario2_monte_carlo(N=200):
    """
    Senaryo 2 (yüksek riskli konjunksiyon) üzerinde
    N replikasyonluk Monte Carlo analizi.
    """
    sat1 = Satellite(
        name="SAT-A (active)",
        a=6778.0, e=0.0, i=53.0, raan=0.0, argp=0.0, nu=0.0,
        covariance=np.diag([0.01] * 3 + [1e-8] * 3),
    )
    sat2 = Satellite(
        name="DEBRIS-1 (dead sat)",
        a=6767.0, e=0.0026, i=168.02, raan=89.7, argp=73.07, nu=352.4,
        covariance=np.diag([0.25, 0.25, 0.25, 1e-7, 1e-7, 1e-7]),
    )
    t_arr = np.arange(0, 2 * 3600 + 10, 10, dtype=float)

    return run_monte_carlo(sat1, sat2, t_arr, N=N, seed=42, scenario_name="S2-Yüksek Risk")


if __name__ == "__main__":
    run_scenario2_monte_carlo(N=200)
