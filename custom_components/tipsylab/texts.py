"""Texte, die Home Assistant selbst verschickt (Handlungen für Benachrichtigungen).

Sie folgen der Sprache des Servers, wie die Namen der Entitäten. Das Panel übersetzt selbst;
Entitäten, Einrichtung und Fehlermeldungen kommen aus tools/make_translations.py.
Reihenfolge wie dort: Deutsch, Englisch, Französisch.
"""

from __future__ import annotations

LANGS = ("de", "en", "fr")

TEXTS: dict[str, tuple[str, str, str]] = {
    "bottle_high": (
        "Flaschen auf 0–2 °C kühlen und die Messflasche täglich ablesen.",
        "Cool the bottles to 0–2 °C and read the measurement bottle daily.",
        "Refroidir les bouteilles à 0–2 °C et relever la bouteille témoin chaque jour.",
    ),
    "bottle_danger": (
        "Sofort auf 0–2 °C kühlen. Flaschen nur mit Schutzbrille und Handschuhen anfassen.",
        "Cool to 0–2 °C at once. Handle the bottles only with safety glasses and gloves.",
        "Refroidir tout de suite à 0–2 °C. Manipuler les bouteilles uniquement avec lunettes et gants.",
    ),
    "silent": (
        "Seit über {hours} h keine Werte: {sources}. Strom, WLAN oder Bluetooth-Reichweite prüfen.",
        "No readings for over {hours} h: {sources}. Check power, Wi-Fi or Bluetooth range.",
        "Aucune valeur depuis plus de {hours} h : {sources}. Vérifier l'alimentation, le Wi-Fi ou la portée Bluetooth.",
    ),
    "battery": (
        "Akku von {device} bei {pct} %: bald laden oder tauschen.",
        "Battery of {device} at {pct} %: charge or replace it soon.",
        "Batterie de {device} à {pct} % : la recharger ou la remplacer bientôt.",
    ),
    "source_gravity": ("Spindel", "hydrometer", "densimètre"),
    "source_temperature": ("Temperatur", "temperature", "température"),
    "source_weight": ("Waage", "scale", "balance"),
    "source_pressure": ("Tankdruck", "tank pressure", "pression de cuve"),
    "source_bubbles": ("Blasenzähler", "bubble counter", "compteur de bulles"),
    "source_bottle_pressure": ("Messflasche", "measurement bottle", "bouteille témoin"),
    "source_bottle_temperature": ("Flaschentemperatur", "bottle temperature", "température de la bouteille"),
}


def lang_of(language: str | None) -> str:
    """Sprache des Servers auf de, en oder fr abbilden; alles andere wird Englisch."""
    code = (language or "en").split("-")[0].lower()
    return code if code in LANGS else "en"


def say(key: str, lang: str, **values: object) -> str:
    text = TEXTS[key][LANGS.index(lang) if lang in LANGS else 1]
    return text.format(**values) if values else text
