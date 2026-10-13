<?php
// TIPSYLAB · DataWein-Feed: nimmt die Datei von Home Assistant an und legt sie als feed.json ab.
//
// Home Assistant schickt alle 15 min per POST (rest_command, Kopfzeile X-Tipsylab-Key). Der
// Schlüssel liegt in einer Datei außerhalb des öffentlichen Ordners (KEY_FILE). Gespeichert werden
// nur bekannte Felder mit Zahlen in plausiblen Grenzen und kurzen Texten; alles andere fällt weg.
// Läuft ab PHP 7.4.

declare(strict_types=1);

const KEY_FILE = __DIR__ . '/../tipsylab-feed-key.txt';
const OUT_FILE = __DIR__ . '/feed.json';
const MAX_BYTES = 65536;
const MAX_BATCHES = 6;
const MAX_HISTORY = 60;
const MODES = ['petnat', 'still'];
const STATUSES = ['waiting', 'fermenting', 'approaching', 'window', 'past', 'dry', 'stuck', 'bottled'];

function fail(int $code): void
{
    http_response_code($code);
    exit;
}

function num($v, float $min, float $max): ?float
{
    if (!is_int($v) && !is_float($v)) {
        return null;
    }
    $f = (float) $v;
    return ($f >= $min && $f <= $max) ? $f : null;
}

function text($v, int $max): ?string
{
    if (!is_string($v)) {
        return null;
    }
    $s = trim((string) preg_replace('/[\x00-\x1F\x7F<>&"]/u', '', $v));
    return $s === '' ? null : mb_substr($s, 0, $max);
}

function stamp($v): ?string
{
    if (!is_string($v) || strlen($v) > 40) {
        return null;
    }
    $t = strtotime($v);
    return $t === false ? null : gmdate('c', $t);
}

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    fail(405);
}
$key = is_readable(KEY_FILE) ? trim((string) file_get_contents(KEY_FILE)) : '';
$sent = $_SERVER['HTTP_X_TIPSYLAB_KEY'] ?? '';
if (strlen($key) < 24 || !is_string($sent) || !hash_equals($key, $sent)) {
    fail(403);
}

$body = file_get_contents('php://input', false, null, 0, MAX_BYTES + 1);
if ($body === false || strlen($body) > MAX_BYTES) {
    fail(413);
}
$data = json_decode($body, true);
if (!is_array($data) || !is_array($data['batches'] ?? null)) {
    fail(400);
}

$batches = [];
foreach (array_slice($data['batches'], 0, MAX_BATCHES) as $b) {
    if (!is_array($b)) {
        continue;
    }
    $name = text($b['name'] ?? null, 60);
    $mode = in_array($b['mode'] ?? null, MODES, true) ? $b['mode'] : null;
    if ($name === null || $mode === null) {
        continue;
    }
    $history = [];
    $points = is_array($b['history'] ?? null) ? $b['history'] : [];
    foreach (array_slice($points, -MAX_HISTORY) as $p) {
        if (!is_array($p) || count($p) !== 2) {
            continue;
        }
        $t = stamp($p[0]);
        $sg = num($p[1], 0.95, 1.2);
        if ($t !== null && $sg !== null) {
            $history[] = [$t, $sg];
        }
    }
    $window = null;
    if (is_array($b['window'] ?? null) && count($b['window']) === 2) {
        $w0 = stamp($b['window'][0]);
        $w1 = stamp($b['window'][1]);
        if ($w0 !== null && $w1 !== null) {
            $window = [$w0, $w1];
        }
    }
    $batches[] = [
        'name' => $name,
        'mode' => $mode,
        'day' => num($b['day'] ?? null, 0, 400),
        'status' => in_array($b['status'] ?? null, STATUSES, true) ? $b['status'] : 'waiting',
        'bpm' => num($b['bpm'] ?? null, 0, 10000),
        'temp' => num($b['temp'] ?? null, -10, 50),
        'sugar' => num($b['sugar'] ?? null, 0, 400),
        'abv' => num($b['abv'] ?? null, 0, 25),
        'abv_end' => num($b['abv_end'] ?? null, 0, 25),
        'sg' => num($b['sg'] ?? null, 0.95, 1.2),
        'dub_h' => num($b['dub_h'] ?? null, 0, 2000),
        'window' => $window,
        'history' => $history,
    ];
}

$out = json_encode(['version' => 1, 'updated' => gmdate('c'), 'batches' => $batches], JSON_UNESCAPED_UNICODE);
$tmp = OUT_FILE . '.tmp';
if ($out === false || file_put_contents($tmp, $out, LOCK_EX) === false || !rename($tmp, OUT_FILE)) {
    fail(500);
}
http_response_code(204);
