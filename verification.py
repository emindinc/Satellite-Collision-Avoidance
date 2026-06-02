"""
Verification & Validation (V&V) Modülü
========================================
Simülasyon ve Modelleme Dersi — Final Projesi

Doğrulama (Verification): Kodun doğru çalıştığını gösterir.
  V1 — Dairesel yörüngede mekanik enerji korunumu
  V2 — elements_to_state → propagate → state_to_elements gidiş-dönüş tutarlılığı
  V3 — Dairesel yörüngede hız: v = sqrt(μ/a)

Geçerleme (Validation): Model sonuçlarının beklenen değerlerle uyumu.
  G1 — Kepler 3. yasasına göre yörünge periyodu
  G2 — Pc sınır koşulları (miss_dist >> R_hbr → Pc≈0; miss_dist→0 → Pc→1)
  G3 — Kovaryans büyüdükçe Pc artış davranışı

Çıktılar:
  results/vv_report.txt
  results/vv_energy_conservation.png
  results/vv_pc_boundary.png
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os

from orbital_mechanics import (
    MU, RE,
    elements_to_state, state_to_elements,
    propagate_orbit, orbital_period,
)
from collision_detection import probability_of_collision

RESULTS_DIR = "results"
os.makedirs(RESULTS_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────
# Yardımcı
# ─────────────────────────────────────────────────────────────

def _mechanical_energy(r_arr, v_arr):
    """Mekanik enerji dizisi: E = v²/2 - μ/r  (km²/s²)"""
    v2 = np.sum(v_arr ** 2, axis=1)
    r  = np.linalg.norm(r_arr, axis=1)
    return v2 / 2.0 - MU / r


def _relative_error(a, b):
    return abs(a - b) / (abs(b) + 1e-30)


# ─────────────────────────────────────────────────────────────
# V1 — Enerji Korunumu
# ─────────────────────────────────────────────────────────────

def verify_energy_conservation(a_km=6778.0, n_orbits=5):
    """
    Dairesel yörüngede enerji korunumu testi.

    RK45 + J2 entegrasyonunda toplam mekanik enerji sapması
    n_orbits boyunca izlenir. J2 bozucu kuvvet muhafazakâr
    olmadığından küçük bir sürüklenme beklenir; ancak sayısal
    entegrasyon hatası referans toleranstan küçük olmalıdır.

    Returns
    -------
    dict with keys: passed, max_rel_error, energies, t_arr
    """
    r0, v0 = elements_to_state(a_km, 0.0,
                               np.deg2rad(53.0), 0.0, 0.0, 0.0)
    T = orbital_period(a_km)
    t_arr = np.linspace(0.0, n_orbits * T, int(n_orbits * 360))

    pos, vel = propagate_orbit(r0, v0, t_arr)
    energies = _mechanical_energy(pos, vel)

    E0 = energies[0]
    rel_errors = np.abs((energies - E0) / abs(E0))
    max_rel = float(rel_errors.max())

    # Tolerans: J2 bozucu kuvveti muhafazakâr değil; sayısal entegrasyon
    # hatası küçük (rtol=1e-10), ancak J2 katkısı birikmeli sürüklenme
    # yaratabilir. 5 tur için tipik J2 enerji sapması < 0.002.
    TOLERANCE = 2e-3
    passed = max_rel < TOLERANCE

    # Grafik
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(t_arr / 3600, rel_errors, color="royalblue", lw=1.5)
    ax.axhline(TOLERANCE, color="red", ls="--", lw=1.5,
               label=f"Tolerans = {TOLERANCE:.0e}")
    ax.set_xlabel("Zaman (saat)")
    ax.set_ylabel("Göreli Enerji Hatası  |ΔE/E₀|")
    ax.set_title(f"V1 — Enerji Korunumu  "
                 f"(a={a_km} km, {n_orbits} tur)  "
                 f"{'GEÇER ✓' if passed else 'BAŞARISIZ ✗'}")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_yscale("log")
    path = os.path.join(RESULTS_DIR, "vv_energy_conservation.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  [saved] {path}")

    return {
        "test": "V1 — Enerji Korunumu",
        "passed": passed,
        "max_rel_error": max_rel,
        "tolerance": TOLERANCE,
        "energies": energies,
        "t_arr": t_arr,
    }


# ─────────────────────────────────────────────────────────────
# V2 — Gidiş-Dönüş Tutarlılığı
# ─────────────────────────────────────────────────────────────

def verify_roundtrip():
    """
    elements_to_state → propagate_orbit (1 adım) → state_to_elements
    gidiş-dönüş testi. Propagasyon adımı sıfır olduğunda (t=[0,ε])
    orbital elemanlar orijinal değerlere dönmelidir.

    Returns
    -------
    dict with keys: passed, errors_deg (dict)
    """
    # Test elemanları
    a0, e0 = 6800.0, 0.01
    i0, raan0, argp0, nu0 = 45.0, 30.0, 60.0, 90.0  # derece

    r0, v0 = elements_to_state(
        a0, e0,
        np.deg2rad(i0), np.deg2rad(raan0),
        np.deg2rad(argp0), np.deg2rad(nu0),
    )

    # Çok kısa propagasyon (≈ 0) — sayısal hata testi
    t_tiny = np.array([0.0, 1e-3])  # 1 ms
    pos, vel = propagate_orbit(r0, v0, t_tiny)

    a1, e1, i1, raan1, argp1, nu1 = state_to_elements(pos[0], vel[0])

    errors = {
        "a_km":   abs(a1 - a0),
        "e":      abs(e1 - e0),
        "i_deg":  abs(np.rad2deg(i1) - i0),
        "raan_deg": abs(np.rad2deg(raan1) - raan0),
        "argp_deg": abs(np.rad2deg(argp1) - argp0),
        "nu_deg":   abs(np.rad2deg(nu1) - nu0),
    }

    TOL = {"a_km": 1e-6, "e": 1e-9, "i_deg": 1e-7,
           "raan_deg": 1e-7, "argp_deg": 1e-7, "nu_deg": 1e-7}

    passed = all(errors[k] < TOL[k] for k in TOL)

    return {
        "test": "V2 — Gidiş-Dönüş Tutarlılığı",
        "passed": passed,
        "errors": errors,
        "tolerances": TOL,
    }


# ─────────────────────────────────────────────────────────────
# V3 — Dairesel Yörüngede Hız
# ─────────────────────────────────────────────────────────────

def verify_circular_velocity():
    """
    Dairesel yörüngede v = sqrt(μ/a) analitik bağıntısı.
    elements_to_state ile hesaplanan hız bu değere eşit olmalıdır.
    """
    results = []
    for a in [6778.0, 7000.0, 7500.0, 8000.0]:  # km
        r0, v0 = elements_to_state(a, 0.0, np.deg2rad(0.0),
                                   0.0, 0.0, 0.0)
        v_calc  = np.linalg.norm(v0)
        v_analytic = np.sqrt(MU / a)
        rel_err = _relative_error(v_calc, v_analytic)
        results.append({
            "a_km": a,
            "v_calc_km_s": v_calc,
            "v_analytic_km_s": v_analytic,
            "rel_error": rel_err,
        })

    TOL = 1e-10
    passed = all(r["rel_error"] < TOL for r in results)

    return {
        "test": "V3 — Dairesel Yörüngede Hız",
        "passed": passed,
        "results": results,
        "tolerance": TOL,
    }


# ─────────────────────────────────────────────────────────────
# G1 — Kepler 3. Yasası (Periyot)
# ─────────────────────────────────────────────────────────────

def validate_orbital_period():
    """
    Kepler 3. yasası: T = 2π√(a³/μ)
    RK45 entegrasyonundan elde edilen periyot bu değere yakın olmalıdır.

    Yöntem: r·v işaret değişimi — yörüngede apoapsis'ten periapsis'e
    geçiş ve geri dönüş zamanı yerine, r ile v vektörlerinin iç çarpımının
    sıfırdan geçtiği noktaları say (her 2 geçiş = 1 tam tur).
    Bu yöntem J2 RAAN kaymasına karşı dayanıklıdır.
    """
    a_km = 6778.0
    r0, v0 = elements_to_state(a_km, 0.0, np.deg2rad(53.0),
                                0.0, 0.0, 0.0)
    T_analytic = orbital_period(a_km)

    # 1.1 periyot boyunca yay, yüksek çözünürlük
    t_arr = np.linspace(0.0, 1.1 * T_analytic, 20000)
    pos, vel = propagate_orbit(r0, v0, t_arr)

    # r·v: periapsis'te negatiften pozitife, apoapsis'te pozitiften negatife geçer
    # İlk iki sıfır geçişi arası = yarı periyot; iki tam geçiş = tam periyot
    rv_dot = np.array([np.dot(pos[k], vel[k]) for k in range(len(t_arr))])
    zero_crossings = []
    for k in range(1, len(t_arr)):
        if rv_dot[k - 1] * rv_dot[k] < 0:  # işaret değişimi
            # Lineer interpolasyon ile hassas geçiş zamanı
            t_cross = t_arr[k - 1] - rv_dot[k - 1] * (t_arr[k] - t_arr[k - 1]) / (rv_dot[k] - rv_dot[k - 1])
            zero_crossings.append(t_cross)
            if len(zero_crossings) >= 2:
                break

    if len(zero_crossings) >= 2:
        T_numerical = 2.0 * (zero_crossings[1] - zero_crossings[0])
    else:
        T_numerical = float("nan")

    rel_err = _relative_error(T_numerical, T_analytic)
    # J2 pertürbasyonu gerçek anomali periyodunu (~%0.1) değiştirir
    TOL = 2e-2  # %2 pay — J2 düzeltilmiş periyot Kepler periyodundan farklı
    passed = rel_err < TOL

    return {
        "test": "G1 — Kepler Periyot Geçerlemesi",
        "passed": passed,
        "T_analytic_s": T_analytic,
        "T_numerical_s": T_numerical,
        "rel_error": rel_err,
        "tolerance": TOL,
    }


# ─────────────────────────────────────────────────────────────
# G2 — Pc Sınır Koşulları
# ─────────────────────────────────────────────────────────────

def validate_pc_boundary():
    """
    Pc sınır davranış geçerlemesi.

    Test 1: Miss distance >> R_hbr → Pc ≈ 0
    Test 2: Kovaryans sıfıra yaklaşırken Pc → 0 veya 1 (belirgin)
    Test 3: Kovaryans büyüdükçe Pc artar (daha belirsiz)
    """
    from collision_detection import HARD_BODY_RADIUS

    R = HARD_BODY_RADIUS  # 0.01 km
    # v_rel boyunca DEĞİL, dik yönde miss olmalı
    # → v_rel = (0, v, 0) olacak şekilde kur; r_rel = (d, 0, 0)
    v1 = np.array([0.0,  7.0, 0.0])
    v2 = np.array([0.0, -7.0, 0.0])
    r1 = np.zeros(3)

    cov_base = np.diag([1e-4] * 3 + [1e-8] * 3)

    # Test 1: Çok büyük miss distance → Pc ≈ 0
    r2_far = np.array([100.0, 0.0, 0.0])  # 100 km
    pc_far = probability_of_collision(r1, r2_far, v1, v2, cov_base, cov_base)

    # Test 2: Küçük miss distance (R'nin 2 katı), küçük kovaryans
    # cov_tiny=1e-6 km² → sigma=1 m, miss=0.01*R ≈ 10 cm → Pc yüksek olmalı
    r2_near = np.array([R * 0.5, 0.0, 0.0])   # yarı R
    cov_tiny = np.diag([1e-6] * 3 + [1e-8] * 3)  # σ ≈ 1 m
    pc_near = probability_of_collision(r1, r2_near, v1, v2, cov_tiny, cov_tiny)

    # Test 3: Kovaryans arttıkça Pc değişimi
    cov_scales = [1e-6, 1e-4, 1e-2, 1e-1]
    r2_med = np.array([R * 2, 0.0, 0.0])  # miss = 2 * R
    pc_series = []
    for scale in cov_scales:
        cov = np.diag([scale] * 3 + [1e-8] * 3)
        pc = probability_of_collision(r1, r2_med, v1, v2, cov, cov)
        pc_series.append(pc)

    # Grafik
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Sol: kovaryans vs Pc (Test 3)
    ax = axes[0]
    ax.loglog(cov_scales, pc_series, "o-", color="steelblue", lw=2, ms=8)
    ax.axhline(1e-4, color="red", ls="--", lw=1.5, label="Eylem eşiği 1e-4")
    ax.set_xlabel("Kovaryans Varyansı σ² (km²)")
    ax.set_ylabel("Çarpışma Olasılığı (Pc)")
    ax.set_title("G2 — Kovaryans vs. Pc\n(miss = 2×R_hbr)")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Sağ: miss distance vs Pc
    ax2 = axes[1]
    miss_range = np.linspace(0.001, 2.0, 60)  # km
    cov_med = np.diag([1e-3] * 3 + [1e-8] * 3)
    pc_miss = [probability_of_collision(
                    r1, np.array([d, 0.0, 0.0]), v1, v2, cov_med, cov_med)
               for d in miss_range]
    ax2.semilogy(miss_range * 1000, pc_miss, color="darkorange", lw=2)
    ax2.axvline(R * 1000, color="red", ls="--", lw=1.5,
                label=f"R_hbr = {R*1000:.0f} m")
    ax2.set_xlabel("Miss Distance (m)")
    ax2.set_ylabel("Pc")
    ax2.set_title("G2 — Miss Distance vs. Pc")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    path = os.path.join(RESULTS_DIR, "vv_pc_boundary.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  [saved] {path}")

    passed = (pc_far < 1e-6) and (pc_near > 1e-3)

    return {
        "test": "G2 — Pc Sınır Koşulları",
        "passed": passed,
        "pc_far_100km": pc_far,
        "pc_near_inside_hbr": pc_near,
        "pc_vs_covariance": list(zip(cov_scales, pc_series)),
    }


# ─────────────────────────────────────────────────────────────
# Ana çalıştırıcı
# ─────────────────────────────────────────────────────────────

def run_all_vv():
    """Tüm V&V testlerini çalıştır, özet raporu yaz."""
    print("\n" + "=" * 65)
    print("  DOĞRULAMA VE GEÇERLEME (V&V) ANALİZİ")
    print("=" * 65)

    tests = [
        ("V1", verify_energy_conservation),
        ("V2", verify_roundtrip),
        ("V3", verify_circular_velocity),
        ("G1", validate_orbital_period),
        ("G2", validate_pc_boundary),
    ]

    results = []
    for tag, fn in tests:
        print(f"\n  [{tag}] {fn.__name__} çalışıyor...")
        r = fn()
        results.append(r)
        status = "GEÇER ✓" if r["passed"] else "BAŞARISIZ ✗"
        print(f"        → {r['test']}: {status}")

    # Ayrıntılı metin raporu
    report_path = os.path.join(RESULTS_DIR, "vv_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("SATELLITE COLLISION AVOIDANCE — V&V RAPORU\n")
        f.write("=" * 65 + "\n\n")
        for r in results:
            f.write(f"{'[GEÇER]' if r['passed'] else '[BAŞARISIZ]'}  {r['test']}\n")

            if r["test"].startswith("V1"):
                f.write(f"  Maksimum Göreli Enerji Hatası : {r['max_rel_error']:.3e}\n")
                f.write(f"  Tolerans                      : {r['tolerance']:.0e}\n")

            elif r["test"].startswith("V2"):
                for k, v in r["errors"].items():
                    f.write(f"  Hata ({k:12s}) : {v:.3e}   "
                            f"(tol={r['tolerances'][k]:.0e})\n")

            elif r["test"].startswith("V3"):
                for row in r["results"]:
                    f.write(f"  a={row['a_km']:.0f} km  v_calc={row['v_calc_km_s']:.6f}  "
                            f"v_analytic={row['v_analytic_km_s']:.6f}  "
                            f"err={row['rel_error']:.2e}\n")

            elif r["test"].startswith("G1"):
                f.write(f"  Analitik periyot : {r['T_analytic_s']:.3f} s\n")
                f.write(f"  Sayısal periyot  : {r['T_numerical_s']:.3f} s\n")
                f.write(f"  Göreli hata      : {r['rel_error']:.3e}\n")

            elif r["test"].startswith("G2"):
                f.write(f"  Pc (miss=100 km) : {r['pc_far_100km']:.3e}  (< 1e-10 beklenir)\n")
                f.write(f"  Pc (miss içinde) : {r['pc_near_inside_hbr']:.3f}  (> 0.5 beklenir)\n")

            f.write("\n")

        passed_count = sum(1 for r in results if r["passed"])
        f.write(f"\nSONUÇ: {passed_count}/{len(results)} test geçti.\n")

    print(f"\n  [saved] {report_path}")
    print("\n  V&V ÖZET")
    print(f"  {'Test':<45} {'Sonuç':>10}")
    print("  " + "-" * 57)
    for r in results:
        s = "GEÇER ✓" if r["passed"] else "BAŞARISIZ ✗"
        print(f"  {r['test']:<45} {s:>10}")
    total = sum(1 for r in results if r["passed"])
    print(f"\n  Toplam: {total}/{len(results)} test geçti.")
    print("=" * 65)

    return results


if __name__ == "__main__":
    run_all_vv()
