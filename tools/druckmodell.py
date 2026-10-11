"""
TIPSYLAB Druckmodell (Entwurf, Stand 11.10.2026)

Zwei Rechnungen, beide nach Liger-Belair et al. (2013), J. Food Eng. 116, 78-85
(Henry-Konstante aus den Daten von Agabaliantz 1963):

1. Pet Nat: Ueberdruck in der Flasche, wenn der Restzucker beim Abfuellen vollstaendig vergaert.
2. Charmat: Sollwert fuer den Tankdruck, damit der Wein nach isobarer Abfuellung den Zieldruck hat.

Die Henry-Konstante gilt fuer Champagner (12,5 % vol, 10 g/L Zucker). Sie ist ein Startwert;
gemessene Druecke in Messflaschen korrigieren die Annahmen pro Haus.

Aufruf:  python3 druckmodell.py      (druckt die Tabellen aus dem Plan)
"""

import math

R = 8.314        # J/(mol K)
K298 = 1.21      # g/(L bar), Henry-Konstante CO2 in Champagner bei 25 degC
DH = 24_800.0    # J/mol, Loesungsenthalpie von CO2
Y = 0.47         # g CO2 je g vergorenem Zucker (theoretisch 0,489)
Y_MALIC = 0.328  # g CO2 je g abgebauter Aepfelsaeure (Malo: C4H6O5 -> C3H6O3 + CO2, 44/134)
P_ATM = 1.013    # bar

# Annahmen beim Abfuellen: (Saettigung des Weins mit CO2 bei 1 bar, Luftanteil im Kopfraum)
CASES = {
    "mittel": (0.8, 0.4),
    "unguenstig": (1.0, 0.79),   # gesaettigt, Luft im Kopfraum -> hoechster Druck
    "guenstig": (0.6, 0.0),      # teilweise entgast, Kopfraum mit CO2
}

# Flaschen: (Weinvolumen L, Kopfraum L, Grenze in bar nach deinen Kronkorken-Werten)
BOTTLES = {
    "330 ml": (0.318, 0.012, 4.5),
    "750 ml": (0.730, 0.020, 6.0),
}


def k_h(t_c: float) -> float:
    """Henry-Konstante in g/(L bar) bei t_c Grad Celsius (Van-'t-Hoff-Form)."""
    t_k = t_c + 273.15
    return K298 * math.exp(DH / R * (1.0 / t_k - 1.0 / 298.15))


def pet_nat_gauge(sugar_g_l: float, t_c: float, bottle: str = "750 ml", case: str = "mittel",
                  t_bottling_c: float = 12.0, malic_g_l: float = 0.0) -> float:
    """Ueberdruck (bar) bei t_c nach vollstaendiger Vergaerung von sugar_g_l in der Flasche.

    malic_g_l: Aepfelsaeure, die erst in der Flasche abgebaut wird (Malo nach dem Abfuellen).
    """
    wine_l, head_l, _ = BOTTLES[bottle]
    saturation, air = CASES[case]
    c0 = saturation * k_h(t_bottling_c) * 1.0            # g/L CO2 beim Abfuellen
    m = wine_l * (c0 + Y * sugar_g_l + Y_MALIC * malic_g_l)   # g CO2 in der Flasche
    t_k = t_c + 273.15
    p_co2 = m * R * t_k / (4.4e3 * head_l + k_h(t_c) * R * t_k * wine_l)
    p_air = air * P_ATM * t_k / (t_bottling_c + 273.15)
    return p_co2 + p_air - P_ATM


def sugar_for(target_bar: float, t_c: float = 20.0, bottle: str = "750 ml", case: str = "mittel") -> float:
    """Restzucker (g/L) beim Abfuellen, der bei t_c den Ziel-Ueberdruck ergibt."""
    lo, hi = 0.0, 80.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if pet_nat_gauge(mid, t_c, bottle, case) > target_bar:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def charmat_setpoint(target_bar_20c: float, tank_c: float, filling_loss: float = 0.08) -> float:
    """Tank-Sollwert (bar Ueberdruck) bei tank_c, damit die Flasche bei 20 degC target_bar_20c hat.

    Annahmen: Kopfraum des Tanks mit CO2 gespuelt, Gleichgewicht zwischen Gas und Wein,
    filling_loss = Anteil CO2, der beim isobaren Abfuellen verloren geht.
    """
    c_target = k_h(20.0) * (target_bar_20c + P_ATM) / (1.0 - filling_loss)
    return c_target / k_h(tank_c) - P_ATM


def empfindlichkeit(target_bar: float = 2.5) -> None:
    """Wie stark verschiebt jede Annahme den Oeffnungsdruck? (750 ml, mittlerer Fall als Basis)"""
    global K298, Y
    s = sugar_for(target_bar)
    b20, b10 = pet_nat_gauge(s, 20), pet_nat_gauge(s, 10)
    print(f"   Basis: {s:.1f} g/L -> {b10:.2f} bar bei 10 degC, {b20:.2f} bar bei 20 degC")

    def zeile(text, p20, p10):
        print(f"   {text:52s} {p20 - b20:+5.2f} bar @20  {p10 - b10:+5.2f} bar @10")

    CASES.update({"s60": (0.6, 0.4), "s100": (1.0, 0.4), "s120": (1.2, 0.4), "co2": (0.8, 0.0), "luft": (0.8, 0.79)})
    for case, text in (("s60", "geloestes CO2 beim Abfuellen 60 % statt 80 %"), ("s100", "geloestes CO2 100 %"),
                       ("s120", "geloestes CO2 120 % (uebersaettigt)"), ("co2", "Kopfraum CO2 statt teils Luft"),
                       ("luft", "Kopfraum Luft")):
        zeile(text, pet_nat_gauge(s, 20, case=case), pet_nat_gauge(s, 10, case=case))
    for ds in (1, 2, 3):
        zeile(f"Restzucker {ds} g/L hoeher als gemessen", pet_nat_gauge(s + ds, 20), pet_nat_gauge(s + ds, 10))
    zeile("1,5 g/L unvergaerbarer Zucker mitgezaehlt", pet_nat_gauge(s - 1.5, 20), pet_nat_gauge(s - 1.5, 10))
    zeile("Malo in der Flasche, 2 g/L Aepfelsaeure", pet_nat_gauge(s, 20, malic_g_l=2), pet_nat_gauge(s, 10, malic_g_l=2))
    zeile("Abfuelltemperatur 15 statt 12 degC", pet_nat_gauge(s, 20, t_bottling_c=15), pet_nat_gauge(s, 10, t_bottling_c=15))
    k0, y0 = K298, Y
    for f in (0.93, 1.07):
        K298 = k0 * f
        zeile(f"Henry-Konstante {f - 1:+.0%}", pet_nat_gauge(s, 20), pet_nat_gauge(s, 10))
    K298 = k0
    for y in (0.45, 0.489):
        Y = y
        zeile(f"CO2-Ausbeute {y} g/g", pet_nat_gauge(s, 20), pet_nat_gauge(s, 10))
    Y = y0
    for key in ("s60", "s100", "s120", "co2", "luft"):
        del CASES[key]
    print(f"   Gegenprobe: 8,4 g/L CO2 / kH(20 degC) = {8.4 / k_h(20):.2f} bar (Literatur: 5,9 bar)")


if __name__ == "__main__":
    print("Henry-Konstante g/(L bar):", ", ".join(f"{t} degC {k_h(t):.2f}" for t in (8, 10, 12, 15, 18, 20, 25)))

    print("\n1) Oeffnungsdruck nach vollstaendiger Vergaerung, 750 ml, abgefuellt bei 12 degC")
    print("   Restzucker | 10 degC unguenstig (mittel) | 20 degC unguenstig (mittel) | Add-on 1.1 bei 20 degC")
    for s in (4, 6, 8, 10, 12, 15):
        u10, m10 = pet_nat_gauge(s, 10, case="unguenstig"), pet_nat_gauge(s, 10)
        u20, m20 = pet_nat_gauge(s, 20, case="unguenstig"), pet_nat_gauge(s, 20)
        print(f"   {s:4d} g/L   | {u10:4.1f} ({m10:3.1f}) bar             | {u20:4.1f} ({m20:3.1f}) bar             | {s / 4.08:4.1f} bar")

    print("\n2) Restzucker beim Abfuellen fuer einen Ziel-Oeffnungsdruck bei 20 degC (750 ml)")
    print("   Ziel 20 degC | mittel | Spanne unguenstig-guenstig | Oeffnen bei 10 degC (mittel)")
    for p in (1.5, 2.0, 2.5, 3.0, 3.5, 4.0):
        s_mid = sugar_for(p)
        print(f"   {p:3.1f} bar      | {s_mid:4.1f} g/L | {sugar_for(p, case='unguenstig'):4.1f}-{sugar_for(p, case='guenstig'):4.1f} g/L"
              f"              | {pet_nat_gauge(s_mid, 10):3.1f} bar")

    print("\n3) Grenzpruefung bei 20 degC, unguenstiger Fall, abgefuellt beim mittleren Zielzucker")
    for name, (_, _, limit) in BOTTLES.items():
        for p in (2.0, 2.5, 3.0, 3.5, 4.0):
            worst = pet_nat_gauge(sugar_for(p, bottle=name), 20, bottle=name, case="unguenstig")
            print(f"   {name}  Ziel {p:3.1f} bar -> bis {worst:3.1f} bar  (Grenze {limit:.1f})  {'ok' if worst <= limit else 'ZU HOCH'}")

    print("\n3b) Malo in der Flasche: Mehrdruck beim Oeffnen, 750 ml, mittlerer Fall, Zielzucker fuer 2,5 bar")
    s25 = sugar_for(2.5)
    for malic in (1.0, 2.0, 3.0):
        d10 = pet_nat_gauge(s25, 10, malic_g_l=malic) - pet_nat_gauge(s25, 10)
        d20 = pet_nat_gauge(s25, 20, malic_g_l=malic) - pet_nat_gauge(s25, 20)
        print(f"   {malic:.0f} g/L Aepfelsaeure -> +{d10:.2f} bar bei 10 degC, +{d20:.2f} bar bei 20 degC;"
              f" ausgleichen mit {Y_MALIC * malic / Y:.1f} g/L weniger Restzucker")

    print("\n4) Charmat: Tank-Sollwert (bar) fuer den Ziel-Oeffnungsdruck bei 20 degC, 8 % Abfuellverlust")
    temps = (8, 10, 12, 15, 18)
    print("   Ziel 20 degC | " + " | ".join(f"Tank {t:2d} degC" for t in temps))
    for p in (2.0, 2.5, 3.0, 4.0, 5.0):
        print(f"   {p:3.1f} bar      | " + " | ".join(f"{charmat_setpoint(p, t):9.2f}  " for t in temps))

    print("\n5) Empfindlichkeit: Ziel 2,5 bar bei 20 degC, was verschiebt den Oeffnungsdruck?")
    empfindlichkeit()
