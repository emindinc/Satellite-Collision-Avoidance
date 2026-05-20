# Satellite Collision Avoidance Simulation

Simülasyon ve Modelleme Dersi — Final Projesi  
**Konu:** Uzay ve Navigasyon Sistemleri / Satellite Collision Avoidance

---

## Proje Hakkında

Düşük Dünya yörüngesindeki (LEO) uyduların birbirine yaklaşma durumlarını (conjunction) tespit eden, çarpışma olasılığını hesaplayan ve gerektiğinde kaçınma manevrası planlayan bir Python simülasyonu.

---

## Modelleme

- **Yörünge yayma:** İki cisim problemi + J2 pertürbasyonu (Dünya'nın basıklığı), RK45 entegrasyon
- **Koordinat sistemi:** ECI (Earth-Centered Inertial), Kepler orbital elemanları
- **Çarpışma olasılığı (Pc):** Chan 2D projeksiyon yöntemi — göreli hıza dik çarpışma düzleminde kovaryans matrisi ile Gauss integrali
- **Manevra planlama:** Along-track / radial / cross-track eksenlerde binary search ile minimum delta-V

---

## Simülasyon Senaryoları

| Senaryo | Açıklama | Miss Distance | Pc | Risk |
|---|---|---|---|---|
| S1: Low-Risk Near-Miss | i=53° ve i=90° kavşak yörüngesi | 5424 m | 1.2e-6 | LOW |
| S2: High-Risk Conjunction | Aynı kavşak, daha yakın geçiş | 585 m | 1.9e-4 | HIGH |
| S2: After Maneuver | 0.43 m/s along-track yakıt | 1300 m | 1.0e-5 | LOW |
| S3: Delta-V Analizi | dV vs. miss distance & Pc eğrileri | — | — | — |
| S4: Multi-Debris | 5 debris nesnesi, öncelik sıralaması | 253–7145 m | — | — |

---

## Kurulum ve Çalıştırma

```bash
pip install numpy scipy matplotlib pillow
python main.py
```

Belirli bir senaryo için:

```bash
python main.py --scenario 2
```

---

## Dosya Yapısı

```
├── orbital_mechanics.py    # Fizik motoru — J2, RK45, koordinat dönüşümleri
├── satellite.py            # Uydu veri modeli
├── collision_detection.py  # TCA bulma, Pc hesabı
├── avoidance.py            # Delta-V manevra planlama
├── scenarios.py            # 4 simülasyon senaryosu
├── visualization.py        # Grafik ve animasyon üretimi
├── main.py                 # Giriş noktası
├── requirements.txt
└── results/                # Üretilen grafikler ve animasyon
```

---

## Sonuçlar

### Senaryo 1 — Düşük Risk
![S1 Orbits](results/s1_orbits_3d.png)
![S1 Miss Distance](results/s1_miss_distance.png)

### Senaryo 2 — Yüksek Risk + Manevra
![S2 Miss Distance](results/s2_miss_distance.png)
![S2 Relative Motion](results/s2_relative_motion.png)

### Senaryo 3 — Delta-V Analizi
![dV Tradeoff](results/s3_dv_tradeoff.png)
![Pc vs Lead Time](results/s3_pc_vs_leadtime.png)

### Senaryo 4 — Çoklu Debris
![Multi-Debris Timeline](results/s4_conjunction_timeline.png)

### Tüm Senaryolar Karşılaştırması
![Comparison](results/all_scenarios_comparison.png)

---

## Animasyon

Senaryo 2 konjunksiyon penceresi (orijinal vs. manevra sonrası):

![Conjunction Animation](results/s2_conjunction_animation.gif)

> Not: GIF animasyon VS Code'da statik görünür. Tarayıcıda açınız.
