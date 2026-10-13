# DataWein-Feed: echte Zahlen auf der Website

Die Seite „TIPSYLAB · DataWein, Fermentation read live“ zeigt die Gärung eines Ansatzes. Home
Assistant schickt alle 15 Minuten eine kleine Datei an den Webserver, die Seite liest sie. Home
Assistant bleibt dabei vom Internet aus unerreichbar, und veröffentlicht wird nur, was im Feed
steht: Name, Tag, Blasen pro Minute, Temperatur, Restzucker, Alkohol, Dichte, Zeit bis zum Abfüllen
und der Dichteverlauf. Keine Geräte-IDs, keine Adressen.

```
Home Assistant ──POST alle 15 min──► feed.php ──► feed.json ◄──liest── tipsylab.js (Seite)
  Dienst tipsylab.website_feed        prüft Schlüssel und Felder
```

## Dateien

| Datei | Wohin |
|---|---|
| [`feed.php`](feed.php) | in den Ordner der Seite auf dem Webserver (braucht PHP ab 7.4) |
| [`tipsylab.js`](tipsylab.js) | ersetzt die Demo-Datei `tipsylab.js` der Seite |
| `tipsylab-feed-key.txt` | eine Ebene **über** dem öffentlichen Ordner, nur der Schlüssel |

Ohne Feed läuft die Seite weiter mit der Simulation und schreibt „DEMO · SIMULATED“ statt des
Ansatzes.

## Einrichten

1. Schlüssel erzeugen, etwa mit `openssl rand -hex 24`, und als einzige Zeile in
   `tipsylab-feed-key.txt` außerhalb des öffentlichen Ordners speichern (oder `KEY_FILE` in
   `feed.php` anpassen).
2. In Home Assistant den Schlüssel in `secrets.yaml` eintragen und den `rest_command` anlegen
   (`configuration.yaml`):

   ```yaml
   # secrets.yaml
   tipsylab_feed_key: "…derselbe Schlüssel…"

   # configuration.yaml
   rest_command:
     tipsylab_feed:
       url: https://tipsy.pt/datawein/feed.php
       method: POST
       headers:
         X-Tipsylab-Key: !secret tipsylab_feed_key
       content_type: application/json
       payload: "{{ payload | tojson }}"
   ```

3. Im Ansatz unter Einstellungen „Auf der Website zeigen (DataWein-Feed)“ einschalten. Die Seite
   zeigt den ersten Ansatz im Feed.
4. Blueprint importieren: `blueprints/automation/tipsylab/website_feed.yaml` (bei privatem Repo
   von Hand nach `/config/blueprints/automation/tipsylab/` kopieren), Automation daraus anlegen.

Prüfen: In Home Assistant unter Entwicklerwerkzeuge → Aktionen `tipsylab.website_feed` mit
„Antwort“ ausführen; das ist genau der Inhalt, der hinausgeht.

## Was `feed.php` prüft

- nur `POST` mit dem richtigen Schlüssel (Kopfzeile `X-Tipsylab-Key`, Vergleich mit `hash_equals`)
- höchstens 64 KB, höchstens sechs Ansätze, je 60 Punkte Verlauf
- nur bekannte Felder; Zahlen nur in plausiblen Grenzen, Namen ohne Steuerzeichen und HTML
- schreibt `feed.json` über eine Zwischendatei, damit die Seite nie eine halbe Datei liest
