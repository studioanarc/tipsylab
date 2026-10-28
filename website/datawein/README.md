# DataWein feed: real numbers on the website

The page "TIPSYLAB · DataWein, Fermentation read live" shows the fermentation of one batch. Home
Assistant sends a small file to the web server every 15 minutes, and the page reads it. Home
Assistant stays unreachable from the internet, and only what is in the feed is published: name,
day, bubbles per minute, temperature, residual sugar, alcohol, density, time until bottling and
the density curve. No device IDs, no addresses.

```
Home Assistant ──POST every 15 min──► feed.php ──► feed.json ◄──reads── tipsylab.js (page)
  service tipsylab.website_feed        checks key and fields
```

## Files

| File | Where it goes |
|---|---|
| [`feed.php`](feed.php) | into the folder of the page on the web server (needs PHP 7.4 or newer) |
| [`tipsylab.js`](tipsylab.js) | replaces the demo file `tipsylab.js` of the page |
| `tipsylab-feed-key.txt` | one level **above** the public folder, only the key |

Without a feed the page keeps running on its simulation and shows "DEMO · SIMULATED" instead of
the batch.

## Setup

1. Generate a key, for example with `openssl rand -hex 24`, and save it as the only line of
   `tipsylab-feed-key.txt` outside the public folder (or adjust `KEY_FILE` in `feed.php`).
2. In Home Assistant, put the key into `secrets.yaml` and add the `rest_command`
   (`configuration.yaml`):

   ```yaml
   # secrets.yaml
   tipsylab_feed_key: "…the same key…"

   # configuration.yaml
   rest_command:
     tipsylab_feed:
       url: https://tipsy.pt/datawein/feed.php   # your own page
       method: POST
       headers:
         X-Tipsylab-Key: !secret tipsylab_feed_key
       content_type: application/json
       payload: "{{ payload | tojson }}"
   ```

3. In the settings of the batch, switch on "Show on the website (DataWein feed)". The page shows
   the first batch in the feed.
4. Import the blueprint `blueprints/automation/tipsylab/website_feed.yaml` (or copy it by hand to
   `/config/blueprints/automation/tipsylab/`) and create an automation from it.

To check: in Home Assistant under Developer tools → Actions, run `tipsylab.website_feed` with
"Response"; that is exactly the content that goes out.

## What `feed.php` checks

- only `POST` with the right key (header `X-Tipsylab-Key`, compared with `hash_equals`)
- at most 64 KB, at most six batches, 60 history points each
- only known fields; numbers only within plausible limits, names without control characters and
  HTML
- writes `feed.json` via a temporary file, so the page never reads half a file
