"""
Satellite Collision Avoidance Simulation
========================================
Simülasyon ve Modelleme Dersi — Final Projesi

Bu program, düşük Dünya yörüngesindeki (LEO) uydu çarpışmalarını
tespit etmek ve kaçınma manevrası planlamak için bir simülasyon sunar.

Kullanım:
    python main.py [--scenario {1,2,3,4,all}]

Gereksinimler:
    pip install numpy scipy matplotlib
"""

import sys
import time
import argparse
import numpy as np

import scenarios as sc


BANNER = """
=================================================================
   SATELLITE COLLISION AVOIDANCE SIMULATION
   Simulasyon ve Modelleme Dersi - Proje
=================================================================
"""


def run_all():
    print(BANNER)
    start = time.time()

    # ── Scenario 1 ──────────────────────────────────────────
    s1_cdm = sc.scenario1_low_risk_near_miss()

    # ── Scenario 2 ──────────────────────────────────────────
    s2_cdm, s2_result = sc.scenario2_high_risk_avoidance()

    # ── Scenario 3 ──────────────────────────────────────────
    s3_cdm, dv_range, miss_vals, pc_vals = sc.scenario3_dv_sensitivity()

    # ── Scenario 4 ──────────────────────────────────────────
    s4_cdm_list, s4_result = sc.scenario4_multi_debris()

    # ── Summary comparison ───────────────────────────────────
    print("\n  Generating summary comparison plot…")
    sc.plot_all_scenario_summary(s1_cdm, s2_cdm, s2_result, s4_cdm_list)

    elapsed = time.time() - start
    print(f"\n{'='*65}")
    print(f"  Simulation complete in {elapsed:.1f} s")
    print(f"  All figures saved to:  results/")
    print(f"{'='*65}")

    _print_summary_table(s1_cdm, s2_cdm, s2_result, s4_cdm_list)


def _print_summary_table(s1, s2, s2_result, s4_list):
    print("\n  RESULTS SUMMARY")
    print(f"  {'Scenario':<30} {'Miss (m)':>12} {'Pc':>12} {'Risk':<10}")
    print("  " + "-" * 68)
    rows = [
        ("S1: Low-Risk Near-Miss",
         s1["miss_distance_km"] * 1000, s1["pc"], s1["risk_level"]),
        ("S2: High-Risk (original)",
         s2["miss_distance_km"] * 1000, s2["pc"], s2["risk_level"]),
    ]
    if s2_result:
        rows.append(("S2: After Avoidance Maneuver",
                     s2_result["new_miss_km"] * 1000, s2_result["new_pc"],
                     "LOW" if s2_result["new_pc"] < 1e-5 else "MEDIUM"))
    for cdm in s4_list:
        rows.append((f"S4: {cdm['sat2']}",
                     cdm["miss_distance_km"] * 1000, cdm["pc"], cdm["risk_level"]))

    for name, miss, pc, risk in rows:
        print(f"  {name:<30} {miss:>12.1f} {pc:>12.3e} {risk:<10}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Satellite Collision Avoidance Simulation"
    )
    parser.add_argument(
        "--scenario", choices=["1", "2", "3", "4", "all"],
        default="all", help="Which scenario to run (default: all)"
    )
    args = parser.parse_args()

    print(BANNER)

    if args.scenario == "1":
        sc.scenario1_low_risk_near_miss()
    elif args.scenario == "2":
        sc.scenario2_high_risk_avoidance()
    elif args.scenario == "3":
        sc.scenario3_dv_sensitivity()
    elif args.scenario == "4":
        sc.scenario4_multi_debris()
    else:
        run_all()


if __name__ == "__main__":
    main()
