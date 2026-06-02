# Matematiksel Model ve Varsayımlar

**Simülasyon ve Modelleme Dersi — Final Projesi**  
*Satellite Collision Avoidance*

---

## 1. Koordinat Sistemleri

### 1.1 ECI (Earth-Centered Inertial)

Simülasyonun temel çerçevesi. Orijin Dünya merkezi, X ekseni vernal equinox, Z ekseni Kuzey kutup yönü. Uydu konumu **r** ve hızı **v** bu çerçevede ifade edilir.

### 1.2 LVLH (Local Vertical Local Horizontal)

Manevra planlamada kullanılır. Üç eksen:
- **r̂** (radial): Dünya merkezinden uyduya
- **t̂** (along-track / teğet): Yörünge hareket yönü
- **n̂** (cross-track / normal): r̂ × t̂

---

## 2. Yörünge Yayma Modeli

### 2.1 İki Cisim Problemi

$$\ddot{\mathbf{r}} = -\frac{\mu}{r^3}\mathbf{r}$$

- **μ** = 398 600.4418 km³/s² (Dünya gravitasyonel parametresi)
- **r** = |**r**| (uydu-Dünya merkezi uzaklığı)

### 2.2 J2 Pertürbasyonu

Dünya'nın basıklığından kaynaklanan baskın bozucu kuvvet:

$$\mathbf{a}_{J_2} = -\frac{3}{2} \frac{J_2 \mu R_E^2}{r^5}
\begin{bmatrix}
x\left(1 - \dfrac{5z^2}{r^2}\right) \\[6pt]
y\left(1 - \dfrac{5z^2}{r^2}\right) \\[6pt]
z\left(3 - \dfrac{5z^2}{r^2}\right)
\end{bmatrix}$$

- **J₂** = 1.08262668 × 10⁻³ (Dünya J2 katsayısı)
- **Rₑ** = 6371.0 km (Dünya yarıçapı)
- x, y, z: ECI koordinatları

**Toplam hareket denklemi:**

$$\ddot{\mathbf{r}} = -\frac{\mu}{r^3}\mathbf{r} + \mathbf{a}_{J_2}$$

**Sayısal integrasyon:** SciPy `solve_ivp` — Runge-Kutta 45 (RK45), `rtol=1e-10`, `atol=1e-12`

### 2.3 Kepler Orbital Elemanları → ECI Dönüşümü

| Eleman | Sembol | Birim |
|--------|--------|-------|
| Yarı-büyük eksen | a | km |
| Eksantrisite | e | — |
| Eğim | i | derece |
| Yükselen düğüm açısı | Ω (RAAN) | derece |
| Perije argümanı | ω | derece |
| Gerçek anomali | ν | derece |

**Perifocal çerçevede konum ve hız:**

$$r = \frac{a(1-e^2)}{1 + e\cos\nu}, \quad
\mathbf{r}_{pf} = r\begin{bmatrix}\cos\nu\\\sin\nu\\0\end{bmatrix}, \quad
\mathbf{v}_{pf} = \frac{\mu}{h}\begin{bmatrix}-\sin\nu\\e+\cos\nu\\0\end{bmatrix}$$

**Perifocal → ECI:** 3-1-3 rotasyon matrisi Q(Ω, i, ω)

---

## 3. Yaklaşma Analizi (Conjunction Analysis)

### 3.1 TCA (Time of Closest Approach) Tespiti

**Adım 1 — Kaba tarama:** Her zaman adımında |**r₁**(t) − **r₂**(t)| hesaplanır; minimum indeks bulunur.

**Adım 2 — İnce arama:** Minimum etrafında ±3 noktalık pencere alınır, Cubic Spline interpolasyonu ile `minimize_scalar` kullanılarak TCA hassas şekilde bulunur.

### 3.2 Çarpışma Olasılığı — Chan 2D Yöntemi

**Çarpışma düzlemi:** Göreli hız vektörüne dik düzlem (E-R düzlemi)

**Göreli pozisyon projeksiyonu:**

$$\mathbf{x}_{2D} = \mathbf{P} \cdot (\mathbf{r}_2 - \mathbf{r}_1)$$

$$\mathbf{P} = \begin{bmatrix} \hat{e}_x^T \\ \hat{e}_y^T \end{bmatrix}, \quad
\hat{e}_z = \frac{\mathbf{v}_{rel}}{|\mathbf{v}_{rel}|}, \quad
\hat{e}_x \perp \hat{e}_z, \quad \hat{e}_y = \hat{e}_z \times \hat{e}_x$$

**Birleşik 2D kovaryans:**

$$\mathbf{C}_{2D} = \mathbf{P}(\mathbf{C}_1^{pos} + \mathbf{C}_2^{pos})\mathbf{P}^T$$

**Çarpışma olasılığı (Pc):** R_hbr yarıçaplı disk üzerinde 2D Gauss integrali:

$$P_c = \iint_{x^2+y^2 \leq R_{hbr}^2} \mathcal{N}(\mathbf{x}_{2D},\,\mathbf{C}_{2D})\,dA$$

- **R_hbr** = 10 m (birleşik hard-body yarıçapı)
- Sayısal hesaplama: SciPy `dblquad`; yetersiz kaldığında Monte Carlo (N=500 000)

**Risk Seviyeleri:**

| Pc aralığı | Risk |
|---|---|
| Pc ≥ 1e-3 | CRITICAL |
| 1e-4 ≤ Pc < 1e-3 | HIGH |
| 1e-5 ≤ Pc < 1e-4 | MEDIUM |
| Pc < 1e-5 | LOW |

---

## 4. Kaçınma Manevrası Modeli

### 4.1 Anlık İmpuls (Impulsive Maneuver)

Manevra, **t_man** anında uydu hızına anlık Δv uygulanması şeklinde modellenir:

$$\mathbf{v}^+(t_{man}) = \mathbf{v}^-(t_{man}) + \Delta\mathbf{v}$$

Manevra sonrası yörünge ayrı bir propagasyon çalışmasıyla hesaplanır.

### 4.2 Minimum Δv Optimizasyonu

Hedef: Pc'yi eylem eşiğinin 10 katı altına (≤ 1e-5) indiren minimum |Δv|

**Yöntem:** Binary search, 40 iterasyon, üst sınır = 50 m/s

Tek bir yön (along-track / radial / cross-track) için:

$$\Delta\mathbf{v} = \Delta v_{mag} \cdot \hat{d}, \quad \hat{d} \in \{\hat{t}, \hat{r}, \hat{n}\}$$

**Optimal strateji:** Üç eksende ayrı ayrı arama yapılır; en küçük |Δv| veren seçilir.

---

## 5. Kullanılan Varsayımlar

| Varsayım | Gerekçe |
|---|---|
| Yalnızca J2 pertürbasyonu | LEO'da dominant etki; güneş basıncı, atmosferik sürükleme ihmal edildi |
| Anlık impuls manevrası | Kısa yanma süresinin yörünge üzerindeki kümülatif etkisi küçük |
| Sabit kovaryans matrisi | Basitlik; gerçekte kovaryans zamanla büyür (state estimation olmaksızın) |
| Küresel hard-body yarıçapı | R_hbr = 10 m (uydunun tüm yönlerde eşit uzaydığı varsayımı) |
| İzole ikili etkileşim | Her uydu-enkaz çifti bağımsız analiz edilir (çoklu etki ihmal) |

---

## 6. Kullanılan Kütüphaneler

| Kütüphane | Sürüm | Kullanım |
|---|---|---|
| NumPy | ≥ 1.24 | Vektör/matris işlemleri, ECI hesapları |
| SciPy | ≥ 1.10 | ODE integrasyon (solve_ivp), Pc integrali (dblquad), istatistik |
| Matplotlib | ≥ 3.7 | 2D/3D görselleştirme, GIF animasyon |
| Pillow | ≥ 9.0 | GIF çerçeve yazma (PillowWriter) |
