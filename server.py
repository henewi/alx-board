#!/usr/bin/env python3
"""
ALX Departures - local flight data service.

Standard library only, so it runs on Raspberry Pi OS Lite or any laptop
with Python 3.8+ and nothing to install.

    python3 server.py        then open  http://localhost:8080

It does four jobs:
  * works out where it is (config.json override, else the postcode given for
    the current Wi-Fi network, else free IP geolocation, else the last location)
  * polls a free ADS-B feed for aircraft within the radius (adsb.lol, with
    airplanes.live as a fallback)
  * looks up each flight's route and airline on adsbdb, caching the answers
  * serves the board page, /api/state, and cached map tiles at /tiles/z/x/y.png
"""

import datetime as dt
import json
import math
import os
import re
import signal
import socket
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import postcode
import settings_page
from wifi import WifiManager

HERE = os.path.dirname(os.path.realpath(__file__))   # the real release folder, even via /opt/alx/current
WEB_DIR = os.path.join(HERE, "web")
try:
    with open(os.path.join(HERE, "VERSION")) as _f:
        VERSION = _f.read().strip() or "dev"
except OSError:
    VERSION = "dev"
STARTED = time.time()

DEFAULTS = {
    # 0.0.0.0 so Alex's phone can reach the style page on the home Wi-Fi
    "host": "0.0.0.0",
    "port": 8080,
    "radius_mi": 10,          # starting range; Alex can change it on the phone page (10, 15 or 25)
    "poll_s": 8,
    "relocate_s": 6 * 3600,
    "route_lookups_per_cycle": 8,
    # Fixed location (leave null to find it automatically)
    "lat": None,
    "lon": None,
    "place": None,
    # Where cache files go. On the Pi, point this at a writable folder
    # once the SD card is made read-only.
    "cache_dir": None,
    # Free ADS-B feeds, tried in order. adsb.fi asks for credit on screen (shown under the radar).
    "flight_urls": [
        "https://opendata.adsb.fi/api/v2/lat/{lat}/lon/{lon}/dist/{nm}",
        "https://api.adsb.lol/v2/point/{lat}/{lon}/{nm}",
        "https://api.airplanes.live/v2/point/{lat}/{lon}/{nm}",
    ],
    "route_url": "https://api.adsbdb.com/v0/callsign/{cs}",
    # Second route database (a different source: PlaneBase/PlanePlotter), tried when adsbdb doesn't know a flight
    "route2_url": "https://hexdb.io/api/v2/routes/{cs}",
    "geo_urls": [
        "https://ipwho.is/",
        "https://ipapi.co/json/",
        "http://ip-api.com/json/",
    ],
    # Postcode lookups (free, no key). UK: postcodes.io; elsewhere and town names: OpenStreetMap Nominatim.
    "postcode_url": "https://api.postcodes.io/postcodes/{pc}",
    "outcode_url": "https://api.postcodes.io/outcodes/{pc}",
    "nominatim_url": "https://nominatim.openstreetmap.org",
    # How often the logbook and stats are saved (also saved on every clean shutdown)
    "save_s": 120,
    # Map: OpenStreetMap by default (no key). Add a free CARTO key for the
    # nicer dark style: https://carto.com/basemaps/apikey/
    "carto_key": "",
    "carto_style": "dark_nolabels",
    "osm_tile_url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    "carto_tile_url": "https://basemaps.cartocdn.com/rastertiles/{style}/{z}/{x}/{y}.png?key={key}",
    # Sent with every request. Planespotters requires a contact URL or email here.
    "contact": "https://yheaero.com",
    "user_agent": "ALX-Departures/1.0 (desk flight display; {contact})",
    # Aircraft photos (free; credit + QR code shown on screen as their rules require)
    "photo_url": "https://api.planespotters.net/pub/photos/hex/{hex}",
    # Board style: solari, terminal, ivory, cockpit or crt
    "theme": "solari",
    # Alex's birthday as "MM-DD" (e.g. "11-14") for the birthday surprise; null to turn off
    "birthday": "11-22",
    # Name used in greetings
    "name": "Alex",
    "aircraft_url": "https://api.adsbdb.com/v0/aircraft/{hex}",
    # Spotting conditions (Open-Meteo, free, no key) and ISS orbit data (CelesTrak, free; at most once per 2 h)
    "weather_url": "https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                   "&current=visibility,cloud_cover,weather_code,precipitation,is_day"
                   "&hourly=visibility,cloud_cover&daily=sunrise,sunset&timezone=auto&forecast_days=1",
    "iss_tle_url": "https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=TLE",
    # Wi-Fi setup hotspot when there's no working connection. "auto" = only on a Raspberry Pi running as root.
    "wifi_manage": "auto",
}


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def load_config():
    cfg = dict(DEFAULTS)
    path = os.environ.get("ALX_CONFIG", os.path.join(HERE, "config.json"))
    try:
        with open(path) as f:
            user = json.load(f)
        cfg.update({k: v for k, v in user.items() if not k.startswith("_")})
        log(f"loaded {path}")
    except FileNotFoundError:
        pass
    except Exception as e:  # a broken config should never stop the display
        log(f"config ignored ({e})")
    return cfg


CFG = load_config()
CACHE_DIR = os.path.expanduser(CFG["cache_dir"] or os.path.join(HERE, "cache"))
os.makedirs(CACHE_DIR, exist_ok=True)


# ---------- small helpers ----------

def _ssl_context():
    """Which list of trusted certificates to use. Windows' built-in list for Python is often missing
    Let's Encrypt's root, which shows up as 'certificate has expired'. If certifi (or truststore) is
    installed, use that instead. The Pi's own list is fine either way."""
    try:
        import truststore                      # uses the operating system's own checker, which updates itself
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT), "system (truststore)"
    except Exception:
        pass
    try:
        import certifi                         # Mozilla's up-to-date list
        return ssl.create_default_context(cafile=certifi.where()), "certifi"
    except Exception:
        return ssl.create_default_context(), "built-in"


SSL_CTX, SSL_SOURCE = _ssl_context()


def fetch(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": CFG["user_agent"].format(contact=CFG["contact"])})
    with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as r:
        return r.read()


def fetch_json(url, timeout=8):
    return json.loads(fetch(url, timeout).decode("utf-8"))


def read_json(name):
    """Reads a saved file. If it's missing or damaged (e.g. power cut mid-save), uses the previous copy."""
    path = os.path.join(CACHE_DIR, name)
    for p in (path, path + ".bak"):
        try:
            with open(p) as f:
                data = json.load(f)
            if p != path:
                log(f"{name} was damaged or missing, restored the previous copy")
            return data
        except FileNotFoundError:
            continue
        except Exception as e:
            log(f"{p} unreadable ({e})")
    return None


def write_json(name, data):
    """Saves safely: write a temp file, flush it to the card, keep the old copy as .bak, then swap in."""
    path = os.path.join(CACHE_DIR, name)
    try:
        with open(path + ".tmp", "w") as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        if os.path.exists(path):
            os.replace(path, path + ".bak")
        os.replace(path + ".tmp", path)
    except Exception as e:
        log(f"could not save {name}: {e}")


# ---------- location ----------

GEO = read_json("postcodes.json") or {}     # postcode -> {"lat", "lon", "city"} or {"missing": True}
GEO_FAIL = {"t": 0.0}                       # last time a postcode lookup couldn't reach the service


def lookup_postcode(pc):
    """Cached lookup. Returns the place, {"missing": True} if it doesn't exist, or None if offline."""
    if pc in GEO and (GEO[pc].get("missing") or GEO[pc].get("v") == 2):
        return GEO[pc]                       # (older saved lookups without "v" are redone once, for a better town name)
    _, kind, err = postcode.normalise(pc)
    if err:
        GEO[pc] = {"missing": True}
        return GEO[pc]
    ip = read_json("location.json") or {}
    try:
        GEO[pc] = postcode.geocode(pc, kind, fetch_json, CFG, ip.get("country"))
        log(f"postcode {pc}: {GEO[pc]['city']} {GEO[pc]['lat']},{GEO[pc]['lon']}")
    except postcode.NotFound:
        log(f"postcode {pc} not found")
        GEO[pc] = {"missing": True}
    except Exception as e:
        log(f"postcode lookup failed {pc}: {e}")
        GEO_FAIL["t"] = time.time()
        return None
    write_json("postcodes.json", GEO)
    return GEO[pc]


def network_key():
    """Postcodes are saved per Wi-Fi network. Off the Pi (or on a cable) there's just one: '*'."""
    return (WIFI.active_ssid() if WIFI else None) or "*"


def wanted_postcode():
    key = network_key()
    return key, (SETTINGS.get("postcodes") or {}).get(key)


def set_postcode(key, pc):
    SETTINGS.setdefault("postcodes", {})[key] = pc
    write_json("settings.json", SETTINGS)
    log(f"postcode for {'this board' if key == '*' else key}: {pc}")


def locate(pc=None):
    if CFG["lat"] is not None and CFG["lon"] is not None:
        return {"lat": float(CFG["lat"]), "lon": float(CFG["lon"]),
                "city": CFG["place"] or "", "source": "config"}
    if pc:
        g = lookup_postcode(pc)
        if g and not g.get("missing"):
            loc = {"lat": g["lat"], "lon": g["lon"], "city": g["city"], "source": "postcode", "postcode": pc}
            write_json("location.json", {**(read_json("location.json") or {}), **loc})
            return loc
    for url in CFG["geo_urls"]:
        try:
            d = fetch_json(url, 6)
            if d.get("success") is False or d.get("status") == "fail" or d.get("error"):
                continue
            lat = float(d.get("latitude", d.get("lat")))
            lon = float(d.get("longitude", d.get("lon")))
            country = d.get("country_code") or d.get("countryCode") or ""
            loc = {"lat": round(lat, 4), "lon": round(lon, 4),
                   "city": d.get("city") or "", "source": "ip", "country": country}
            write_json("location.json", loc)
            log(f"located: {loc['city']} {loc['lat']},{loc['lon']} via {url}")
            return loc
        except Exception as e:
            log(f"geolocation failed at {url}: {e}")
    loc = read_json("location.json")
    if loc:
        if not (pc and loc.get("postcode") == pc):
            loc.pop("postcode", None)
        loc["source"] = "cached"
        return loc
    return None


# ---------- routes (adsbdb) ----------

ROUTES = read_json("routes.json") or {}   # callsign -> {"t": time, "r": route or None}
AIRLINE_CALLSIGN = re.compile(r"^[A-Z]{3}[0-9][0-9A-Z]{0,4}$")


def parse_route(d):
    resp = d.get("response")
    fr = resp.get("flightroute") if isinstance(resp, dict) else None
    if not fr:
        return None

    def airport(a):
        a = a or {}
        return {"code": a.get("iata_code") or a.get("icao_code") or "",
                "city": a.get("municipality") or a.get("name") or "",
                "name": a.get("name") or "",
                "lat": a.get("latitude"), "lon": a.get("longitude")}

    airline = fr.get("airline") or {}
    return {"airline": airline.get("name") or "",
            "airline_icao": airline.get("icao") or "",
            "flight_iata": fr.get("callsign_iata") or "",
            "from": airport(fr.get("origin")),
            "to": airport(fr.get("destination"))}


# ---------- airports (OurAirports, public domain): for checking routes and filling gaps ----------

try:
    with open(os.path.join(HERE, "airports.json"), encoding="utf-8") as _f:
        AIRPORTS = [{"code": iata or icao, "icao": icao, "name": name, "city": (city or name).split(",")[0].strip(),
                     "lat": lat, "lon": lon} for iata, icao, name, city, lat, lon in json.load(_f)]
except Exception:
    AIRPORTS = []
AIRPORT_BY_ICAO = {ap["icao"]: ap for ap in AIRPORTS}


def miles(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(min(1, h)))


def bearing(lat1, lon1, lat2, lon2):
    p1, p2, dl = math.radians(lat1), math.radians(lat2), math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def parse_hexdb(d):
    def airport(a):
        a = a or {}
        known = AIRPORT_BY_ICAO.get(a.get("icao") or "")
        return {"code": a.get("iata") or a.get("icao") or "",
                "city": known["city"] if known else (a.get("name") or ""),
                "name": a.get("name") or "", "lat": a.get("latitude"), "lon": a.get("longitude")}
    if not d or not d.get("origin") or not d.get("destination"):
        return None
    return {"airline": "", "airline_icao": "", "flight_iata": "",
            "from": airport(d["origin"]), "to": airport(d["destination"])}


def plausible(r, a):
    """A route database can be out of date (airlines reuse callsigns). Only trust a route if the plane
    is roughly on the way from one airport to the other, or near one of them."""
    try:
        f, t = r["from"], r["to"]
        if None in (f["lat"], f["lon"], t["lat"], t["lon"], a.get("lat"), a.get("lon")):
            return True
        d_from = miles(a["lat"], a["lon"], f["lat"], f["lon"])
        d_to = miles(a["lat"], a["lon"], t["lat"], t["lon"])
        if min(d_from, d_to) < 40:
            return True
        return d_from + d_to <= miles(f["lat"], f["lon"], t["lat"], t["lon"]) * 1.25 + 80
    except Exception:
        return True


def infer_route(a):
    """No route known: if the plane is low and clearly climbing away from, or descending into, a
    nearby airport, that end of the route is certain enough to show."""
    alt, vs, trk = a.get("alt"), a.get("vs"), a.get("track")
    if alt is None or vs is None or trk is None or alt > 7000 or abs(vs) < 300 or a.get("lat") is None:
        return None
    best = None
    for ap in AIRPORTS:
        if abs(ap["lat"] - a["lat"]) > 0.4 or abs(ap["lon"] - a["lon"]) > 0.7:
            continue
        d = miles(a["lat"], a["lon"], ap["lat"], ap["lon"])
        if d <= (15 if vs > 0 else 22) and (best is None or d < best[0]):
            best = (d, ap)
    if not best:
        return None
    d, ap = best
    end = {k: ap[k] for k in ("code", "city", "name", "lat", "lon")}
    blank = {"code": "", "city": "", "name": "", "lat": None, "lon": None}
    away = bearing(ap["lat"], ap["lon"], a["lat"], a["lon"])           # direction from the airport to the plane
    turn = lambda x, y: abs((x - y + 180) % 360 - 180)
    if vs > 0 and (d < 3 or turn(trk, away) < 70):
        return {"airline": "", "airline_icao": "", "flight_iata": "", "from": end, "to": blank, "inferred": True}
    if vs < 0 and (d < 3 or turn(trk, (away + 180) % 360) < 60):
        return {"airline": "", "airline_icao": "", "flight_iata": "", "from": blank, "to": end, "inferred": True}
    return None


def cached_route(cs):
    hit = ROUTES.get(cs)
    if not hit:
        return False, None
    max_age = 86400 if hit["r"] else 6 * 3600
    return (time.time() - hit["t"] < max_age), hit["r"]


def lookup_route(cs, a=None):
    """Network lookup: adsbdb, then hexdb, keeping only a route that fits where the plane is.
    Unknown callsigns are cached as None so we don't ask again for a while."""
    if not AIRLINE_CALLSIGN.match(cs):   # private, military, registration-style
        ROUTES[cs] = {"t": time.time(), "r": None}
        return None
    r, airline, failed = None, None, None
    for key, parse in (("route_url", parse_route), ("route2_url", parse_hexdb)):
        if not CFG.get(key):
            continue
        try:
            got = parse(fetch_json(CFG[key].format(cs=urllib.parse.quote(cs)), 6))
        except urllib.error.HTTPError as e:
            if e.code != 404:
                failed = e
            continue
        except Exception as e:
            failed = e
            continue
        if got and got.get("airline"):
            airline = got                       # adsbdb names the airline even when its route is out of date
        if got and (a is None or plausible(got, a)):
            r = got
            break
    if r and not r.get("airline") and airline:
        r.update(airline=airline["airline"], airline_icao=airline["airline_icao"], flight_iata=airline["flight_iata"])
    if r is None and failed is not None:
        raise failed                            # couldn't ask: try again next time rather than caching "unknown"
    ROUTES[cs] = {"t": time.time(), "r": r}
    return r


# ---------- aircraft (adsb.lol / airplanes.live) ----------

SOURCE = {"name": None}          # the feed that answered last (credited on screen)
SOURCE_REST = {}                 # feed -> time it may be asked again
SOURCE_STRIKES = {}              # feed -> failures in a row (each one doubles the rest)


def rest_source(tmpl, host, why, base, cap):
    """Be polite: a feed that refuses, rate-limits or times out is left alone, for longer each time
    it happens in a row (1, 2, 4, 8 … minutes). The board meanwhile uses the other feeds."""
    n = SOURCE_STRIKES.get(tmpl, 0)
    SOURCE_STRIKES[tmpl] = n + 1
    wait = min(cap, base * (2 ** n))
    SOURCE_REST[tmpl] = time.time() + wait
    log(f"flight source {host} {why}; leaving it alone for {wait // 60 if wait >= 60 else wait}{' min' if wait >= 60 else ' s'}")


def fetch_aircraft(loc):
    nm = math.ceil(radius() / 1.15078) + 1   # feeds take nautical miles
    last = None
    for tmpl in CFG["flight_urls"]:
        host = urllib.parse.urlsplit(tmpl).hostname or tmpl
        if time.time() < SOURCE_REST.get(tmpl, 0):
            continue
        url = tmpl.format(lat=loc["lat"], lon=loc["lon"], nm=nm)
        try:
            d = fetch_json(url, 6)
            if SOURCE_STRIKES.pop(tmpl, 0) or SOURCE["name"] != host:
                log(f"flights now from {host}")
            SOURCE["name"] = host
            return d.get("ac") or d.get("aircraft") or []
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429:
                try:
                    asked = int(e.headers.get("Retry-After") or 60)
                except ValueError:
                    asked = 60
                rest_source(tmpl, host, "said slow down (429)", max(60, asked), 1800)
            elif e.code in (401, 403):
                rest_source(tmpl, host, f"refused us ({e.code})", 3600, 6 * 3600)
            else:
                rest_source(tmpl, host, f"said {e.code}", 30, 600)
        except Exception as e:
            last = e
            rest_source(tmpl, host, f"failed ({e})", 30, 600)
    raise RuntimeError(f"all flight sources failed ({last})" if last else "all flight sources resting")


CREDIT = {"api.adsb.lol": "adsb.lol", "opendata.adsb.fi": "adsb.fi", "api.airplanes.live": "airplanes.live"}


# ---------- special aircraft ----------
RARE_TYPES = {
    "A388": "AIRBUS A380", "A124": "ANTONOV AN-124", "A225": "ANTONOV AN-225",
    "B741": "BOEING 747", "B742": "BOEING 747", "B743": "BOEING 747", "B744": "BOEING 747-400",
    "B748": "BOEING 747-8", "B74S": "BOEING 747SP", "BLCF": "747 DREAMLIFTER",
    "A3ST": "AIRBUS BELUGA", "A337": "AIRBUS BELUGA XL", "C17": "C-17 GLOBEMASTER",
    "C5M": "C-5 GALAXY", "A400": "A400M ATLAS", "C130": "C-130 HERCULES", "C30J": "C-130J HERCULES",
    "V22": "V-22 OSPREY", "B52": "B-52 STRATOFORTRESS", "E3TF": "E-3 SENTRY", "E3CF": "E-3 SENTRY",
    "K35R": "KC-135 TANKER", "IL76": "ILYUSHIN IL-76", "MD11": "MD-11", "DC10": "DC-10",
    "DC3": "DOUGLAS DC-3", "SPIT": "SPITFIRE", "HURI": "HURRICANE", "LANC": "LANCASTER",
    "B17": "B-17 FLYING FORTRESS", "CONC": "CONCORDE", "H47": "CHINOOK", "EUFI": "TYPHOON",
    "F35": "F-35 LIGHTNING", "P8": "P-8 POSEIDON", "R135": "RC-135",
}
MIL_CALLSIGNS = ("RRR", "RCH", "ASCOT", "NATO", "CFC", "GAF", "FAF", "BAF", "NAVY", "TARTN", "KITTY", "COMET")
SQUAWKS = {"7700": "EMERGENCY · SQUAWK 7700", "7600": "RADIO FAILURE · SQUAWK 7600", "7500": "SQUAWK 7500"}


def alert_for(a, cs, typ):
    sq = str(a.get("squawk") or "")
    if sq in SQUAWKS or (a.get("emergency") not in (None, "none")):
        return {"kind": "emergency", "label": SQUAWKS.get(sq, "EMERGENCY")}
    if typ in RARE_TYPES:
        return {"kind": "rare", "label": RARE_TYPES[typ]}
    if (a.get("dbFlags") or 0) & 1 or cs.startswith(MIL_CALLSIGNS):
        return {"kind": "military", "label": "MILITARY"}
    return None


def build(raw, loc):
    out = []
    cos0 = math.cos(math.radians(loc["lat"]))
    for a in raw:
        lat, lon = a.get("lat"), a.get("lon")
        if lat is None or lon is None:
            continue
        alt = a.get("alt_baro", a.get("alt_geom"))
        if alt == "ground":
            continue
        x = (lon - loc["lon"]) * 69.172 * cos0      # miles east
        y = (lat - loc["lat"]) * 69.0               # miles north
        dist = math.hypot(x, y)
        if dist > radius():
            continue
        cs = (a.get("flight") or "").strip().upper()
        typ = (a.get("t") or "").upper()
        out.append({
            "hex": a.get("hex") or "",
            "callsign": cs,
            "reg": a.get("r") or "",
            "type": typ,
            "alert": alert_for(a, cs, typ),
            "cat": a.get("category") or "",
            "alt": int(alt) if isinstance(alt, (int, float)) else None,
            "gs": a.get("gs"),
            "track": a.get("track", a.get("true_heading")),
            "vs": a.get("baro_rate", a.get("geom_rate")),       # ft/min, + climbing
            "x": round(x, 3), "y": round(y, 3), "dist": round(dist, 2),
            "lat": round(lat, 4), "lon": round(lon, 4),
            "route": None,
        })
    out.sort(key=lambda a: a["dist"])
    return out


# ---------- daily tally ----------

def _load_today():
    t = read_json("today.json") or {}
    return {"date": t.get("date"), "hexes": set(t.get("hexes", [])),
            "hours": {int(k): set(v) for k, v in (t.get("hours") or {}).items()},
            "types": set(t.get("types", [])), "rare": t.get("rare", []),
            "highest": t.get("highest"), "fastest": t.get("fastest"), "furthest": t.get("furthest")}


TODAY = _load_today()


def miles_between(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


def update_today(aircraft, loc):
    """Running totals for the day: count, busiest hour, highest, fastest, furthest origin, types, rare sightings."""
    now = dt.datetime.now()
    d = now.date().isoformat()
    if TODAY["date"] != d:
        TODAY.update(date=d, hexes=set(), hours={}, types=set(), rare=[], highest=None, fastest=None, furthest=None)
    rare_seen = {r["hex"] for r in TODAY["rare"]}
    for a in aircraft:
        h = a["hex"]
        if not h:
            continue
        name = a["callsign"] or a["reg"] or h.upper()
        TODAY["hexes"].add(h)
        TODAY["hours"].setdefault(now.hour, set()).add(h)
        if a["type"]:
            TODAY["types"].add(a["type"])
        if a["alt"] is not None and (not TODAY["highest"] or a["alt"] > TODAY["highest"]["v"]):
            TODAY["highest"] = {"v": a["alt"], "cs": name}
        if a["gs"] is not None and (not TODAY["fastest"] or a["gs"] > TODAY["fastest"]["v"]):
            TODAY["fastest"] = {"v": round(a["gs"]), "cs": name}
        r = a.get("route")
        if r and r["from"].get("lat") is not None:
            mi = miles_between(loc["lat"], loc["lon"], r["from"]["lat"], r["from"]["lon"])
            if not TODAY["furthest"] or mi > TODAY["furthest"]["v"]:
                TODAY["furthest"] = {"v": round(mi), "city": r["from"]["city"] or r["from"]["code"], "cs": name}
        if a["alert"] and a["alert"]["kind"] != "emergency" and h not in rare_seen:
            TODAY["rare"].append({"hex": h, "cs": name, "label": a["alert"]["label"], "t": now.strftime("%H:%M")})
            rare_seen.add(h)


def today_summary():
    busiest = max(TODAY["hours"].items(), key=lambda kv: len(kv[1]), default=None)
    return {"count": len(TODAY["hexes"]),
            "busiest": {"hour": busiest[0], "n": len(busiest[1])} if busiest else None,
            "highest": TODAY["highest"], "fastest": TODAY["fastest"], "furthest": TODAY["furthest"],
            "types": len(TODAY["types"]), "rare": TODAY["rare"][-5:], "rare_count": len(TODAY["rare"])}


def save_today():
    write_json("today.json", {"date": TODAY["date"], "hexes": sorted(TODAY["hexes"]),
                              "hours": {str(k): sorted(v) for k, v in TODAY["hours"].items()},
                              "types": sorted(TODAY["types"]), "rare": TODAY["rare"],
                              "highest": TODAY["highest"], "fastest": TODAY["fastest"], "furthest": TODAY["furthest"]})


# ---------- recently passed (fills empty board rows) ----------

RECENT = read_json("recent.json") or []   # newest first
LAST_SEEN = {}                            # hex -> aircraft dict from the previous update


def update_recent(aircraft):
    global LAST_SEEN
    now_hexes = {a["hex"] for a in aircraft}
    for h, a in LAST_SEEN.items():
        if h not in now_hexes and a["hex"]:
            RECENT[:] = [r for r in RECENT if r["hex"] != h]
            RECENT.insert(0, {"hex": h, "callsign": a["callsign"], "reg": a["reg"], "type": a["type"],
                              "route": a["route"], "t": dt.datetime.now().strftime("%H:%M")})
    del RECENT[12:]
    LAST_SEEN = {a["hex"]: a for a in aircraft}


# ---------- spotter's logbook (kept forever) ----------
# Every aircraft by registration (or transponder code), and every type, with the day first seen.
# Badges only start once the logbook is more than a day old, otherwise everything is "new".

LOGBOOK = read_json("logbook.json") or {}
LOGBOOK.setdefault("started", dt.date.today().isoformat())
LOGBOOK.setdefault("aircraft", {})
LOGBOOK.setdefault("types", {})
PASS_FLAGS = {}   # hex -> {"first": bool, "new_type": bool} for the aircraft's current pass


def update_logbook(aircraft):
    today = dt.date.today().isoformat()
    badges = LOGBOOK["started"] < today
    now_hexes = set()
    for a in aircraft:
        h = a["hex"]
        if not h:
            continue
        now_hexes.add(h)
        if h not in PASS_FLAGS:                       # a new pass overhead
            key = (a["reg"] or h).upper()
            entry = LOGBOOK["aircraft"].get(key)
            new_type = bool(a["type"]) and a["type"] not in LOGBOOK["types"]
            PASS_FLAGS[h] = {"first": badges and entry is None, "new_type": badges and new_type}
            if entry is None:
                LOGBOOK["aircraft"][key] = {"first": today, "seen": 1, "type": a["type"]}
            else:
                entry["seen"] = entry.get("seen", 0) + 1
                entry["type"] = a["type"] or entry.get("type", "")
            if new_type:
                LOGBOOK["types"][a["type"]] = today
        a.update(PASS_FLAGS[h])
    for h in list(PASS_FLAGS):
        if h not in now_hexes:
            del PASS_FLAGS[h]


def logbook_summary():
    today = dt.date.today().isoformat()
    return {"aircraft": len(LOGBOOK["aircraft"]), "types": len(LOGBOOK["types"]), "since": LOGBOOK["started"],
            "new_types_today": sorted(t for t, d in LOGBOOK["types"].items() if d == today and LOGBOOK["started"] < today)}


# ---------- spotting conditions (Open-Meteo) ----------

WEATHER = {"data": None, "t": 0.0}
SKY = [(0, "CLEAR"), (1, "MOSTLY CLEAR"), (2, "PARTLY CLOUDY"), (3, "OVERCAST"), (45, "FOG"), (48, "FOG"),
       (51, "DRIZZLE"), (56, "FREEZING DRIZZLE"), (61, "RAIN"), (66, "FREEZING RAIN"), (71, "SNOW"),
       (77, "SNOW"), (80, "SHOWERS"), (85, "SNOW SHOWERS"), (95, "THUNDER")]


def parse_weather(d):
    cur, hourly = d.get("current") or {}, d.get("hourly") or {}
    vis, cloud = cur.get("visibility"), cur.get("cloud_cover")
    if (vis is None or cloud is None) and hourly.get("time") and cur.get("time"):
        hour = cur["time"][:13]
        idx = next((i for i, t in enumerate(hourly["time"]) if t.startswith(hour)), None)
        if idx is not None:
            vis = vis if vis is not None else (hourly.get("visibility") or [None] * 99)[idx]
            cloud = cloud if cloud is not None else (hourly.get("cloud_cover") or [None] * 99)[idx]
    code = cur.get("weather_code") or 0
    sky = [name for c, name in SKY if code >= c][-1]
    wet = (cur.get("precipitation") or 0) > 0.1 or code >= 51
    vis_km = round(vis / 1000) if vis is not None else None
    if wet or code in (45, 48) or (vis_km is not None and vis_km < 5):
        rating = "POOR"
    elif (vis_km or 0) >= 20 and (cloud if cloud is not None else 100) <= 40:
        rating = "EXCELLENT"
    elif (vis_km or 0) >= 10 and (cloud if cloud is not None else 100) <= 75:
        rating = "GOOD"
    else:
        rating = "FAIR"
    daily = d.get("daily") or {}
    sunrise = (daily.get("sunrise") or [""])[0]
    sunset = (daily.get("sunset") or [""])[0]
    golden = False
    try:
        now = dt.datetime.fromisoformat(cur["time"])
        for edge, sign in ((sunset, 1), (sunrise, -1)):
            mins = (dt.datetime.fromisoformat(edge) - now).total_seconds() / 60 * sign
            golden = golden or 0 <= mins <= 60
    except Exception:
        pass
    return {"rating": rating, "sky": sky, "vis_km": vis_km, "cloud": cloud, "is_day": bool(cur.get("is_day", 1)),
            "sunrise": sunrise[11:16], "sunset": sunset[11:16], "golden": golden}


def refresh_weather(loc):
    if time.time() - WEATHER["t"] < 900:
        return
    WEATHER["t"] = time.time()
    try:
        WEATHER["data"] = parse_weather(fetch_json(CFG["weather_url"].format(lat=loc["lat"], lon=loc["lon"]), 8))
    except Exception as e:
        log(f"weather failed: {e}")


# ---------- ISS orbit (CelesTrak) ----------
# Passes are worked out on the board itself. CelesTrak asks for at most one download per 2 hours,
# and for software to back off on any error, so this fetches twice a day and waits 12 h after a failure.

ISS = {"tle": read_json("iss_tle.json"), "t": 0.0}
try:   # a restart soon after the last download shouldn't download again
    ISS["t"] = os.path.getmtime(os.path.join(CACHE_DIR, "iss_tle.json"))
except OSError:
    pass


def refresh_iss():
    if time.time() - ISS["t"] < 12 * 3600:
        return
    ISS["t"] = time.time()
    try:
        lines = [l.strip() for l in fetch(CFG["iss_tle_url"], 10).decode("utf-8", "replace").splitlines() if l.strip()]
        l1 = next(l for l in lines if l.startswith("1 "))
        l2 = next(l for l in lines if l.startswith("2 "))
        ISS["tle"] = [l1, l2]
        write_json("iss_tle.json", ISS["tle"])
    except Exception as e:
        log(f"ISS orbit data failed (next try in 12 h): {e}")


# ---------- polling loop ----------

# ---------- settings Alex can change (saved on the device) ----------

SETTINGS = read_json("settings.json") or {}


RANGES = (10, 15, 25)


def radius():
    r = SETTINGS.get("radius_mi") or CFG["radius_mi"]
    try:
        return max(2, min(50, float(r)))
    except (TypeError, ValueError):
        return 10


def current_theme():
    t = SETTINGS.get("theme") or CFG["theme"]
    t = {"sunset": "wavepunk"}.get(t, t)          # Sunset became Wavepunk
    return t if t in settings_page.THEME_IDS else "solari"


_LAN = {"ip": None, "t": 0.0}


def lan_ip():
    """This device's address on the home network, for the QR code to the phone page."""
    if time.time() - _LAN["t"] > 60:
        _LAN["t"] = time.time()
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("10.255.255.255", 1))          # picks the right interface; nothing is sent
            _LAN["ip"] = s.getsockname()[0]
            s.close()
        except OSError:
            _LAN["ip"] = None
    return _LAN["ip"]


WIFI = None   # set in main() on the Pi
STATE = {"location": None, "aircraft": [], "today": 0, "stats": None, "recent": [],
         "ok": False, "last_ok": 0.0, "error": "starting", "place": None}
LOCK = threading.Lock()
BEAT = {"poller": time.time()}                     # watchdog: the poller ticks this every loop
KIOSK = {"t": 0.0, "r": -1, "rt": 0.0}             # watchdog: when the board screen last drew new data


def place_status(key, pc):
    """Whether the board must ask for a postcode (on the Pi, for a network without one, or one that wasn't found)."""
    if CFG["lat"] is not None and CFG["lon"] is not None:
        return None
    g = GEO.get(pc) if pc else None
    if pc and g and g.get("missing"):
        return {"needed": True, "error": f"{pc} WASN'T FOUND", "network": key}
    if not pc and (WIFI is None or WIFI.state["mode"] == "online"):
        return {"needed": True, "error": "", "network": key}
    return None


def save_all():
    write_json("routes.json", ROUTES)
    save_today()
    write_json("recent.json", RECENT)
    write_json("logbook.json", LOGBOOK)


def poller():
    loc, loc_t, saved_t, loc_want = None, 0.0, time.time(), None
    while True:
        BEAT["poller"] = time.time()
        try:
            key, pc = wanted_postcode()
            pending = (pc and (loc is None or loc.get("postcode") != pc) and not (GEO.get(pc) or {}).get("missing")
                       and time.time() - GEO_FAIL["t"] > 120)
            if loc is None or time.time() - loc_t > CFG["relocate_s"] or (key, pc) != loc_want or pending:
                new = locate(pc)
                if new:
                    if loc and (new["lat"], new["lon"]) != (loc["lat"], loc["lon"]):
                        WEATHER["t"] = 0.0             # new place: fresh weather
                    loc, loc_t = new, time.time()
                loc_want = (key, pc)
            with LOCK:
                STATE["location"] = loc
                STATE["place"] = place_status(key, pc)
            if loc is None:
                raise RuntimeError("no location yet")

            aircraft = build(fetch_aircraft(loc), loc)

            lookups = 0
            for a in aircraft:                        # nearest first
                cs = a["callsign"]
                if not cs:
                    a["route"] = infer_route(a)
                    continue
                fresh, r = cached_route(cs)
                if not fresh and lookups < CFG["route_lookups_per_cycle"]:
                    lookups += 1
                    try:
                        r = lookup_route(cs, a)
                    except Exception as e:
                        log(f"route lookup failed {cs}: {e}")
                a["route"] = r or infer_route(a)

            update_logbook(aircraft)
            update_today(aircraft, loc)
            update_recent(aircraft)
            refresh_weather(loc)
            refresh_iss()
            with LOCK:
                STATE.update(aircraft=aircraft, today=len(TODAY["hexes"]), stats=today_summary(),
                             recent=list(RECENT), ok=True, last_ok=time.time(), error="")

            if time.time() - saved_t > CFG["save_s"]:
                cutoff = time.time() - 7 * 86400
                for k in [k for k, v in ROUTES.items() if v["t"] < cutoff]:
                    del ROUTES[k]
                save_all()
                saved_t = time.time()
        except Exception as e:
            log(f"update failed: {e}")
            with LOCK:
                STATE.update(ok=False, error=str(e))
                # Don't keep showing planes from more than 5 minutes ago
                if time.time() - STATE["last_ok"] > 300:
                    STATE["aircraft"] = []
        time.sleep(CFG["poll_s"])


# ---------- aircraft photos (Planespotters.net) ----------
# Only the photo's details are cached (in memory, 24 h max, as their terms allow).
# The image itself is loaded by the browser straight from Planespotters and never stored here.

PHOTOS = {}   # hex -> {"t": time, "p": photo dict or {}}
HEX = re.compile(r"^[0-9a-f]{6}$")


AIRCRAFT = {}   # hex -> {"t": time, "a": details or {}}


def get_aircraft(hex_code):
    """Manufacturer and model from adsbdb, for types the board doesn't already know."""
    hit = AIRCRAFT.get(hex_code)
    if hit and time.time() - hit["t"] < 7 * 86400:
        return hit["a"]
    info = {}
    try:
        ac = fetch_json(CFG["aircraft_url"].format(hex=hex_code), 6).get("response")
        ac = ac.get("aircraft") if isinstance(ac, dict) else None
        if ac:
            maker = re.sub(r"\b(SAS|S\.A\.S\.|INC|CO|COMPANY|CORPORATION|LTD|GMBH|AG|S\.P\.A\.)\b\.?", "",
                           ac.get("manufacturer") or "", flags=re.I).strip(" ,.")
            info = {"manufacturer": maker, "model": ac.get("type") or "", "icao_type": ac.get("icao_type") or ""}
    except urllib.error.HTTPError as e:
        if e.code != 404:
            log(f"aircraft lookup failed {hex_code}: {e}")
    except Exception as e:
        log(f"aircraft lookup failed {hex_code}: {e}")
    AIRCRAFT[hex_code] = {"t": time.time(), "a": info}
    return info


def get_photo(hex_code):
    hex_code = (hex_code or "").lower()
    if not HEX.match(hex_code):
        return {}
    hit = PHOTOS.get(hex_code)
    if hit and time.time() - hit["t"] < (86400 if hit["p"] else 3600):
        return hit["p"]
    photo = {}
    try:
        d = fetch_json(CFG["photo_url"].format(hex=hex_code), 6)
        ph = (d.get("photos") or [None])[0]
        if ph:
            big = ph.get("thumbnail_large") or {}
            small = ph.get("thumbnail") or {}
            src = big.get("src") or small.get("src")
            if src and ph.get("link"):
                photo = {"src": src, "link": ph["link"], "photographer": ph.get("photographer") or ""}
    except Exception as e:
        log(f"photo lookup failed {hex_code}: {e}")
    PHOTOS[hex_code] = {"t": time.time(), "p": photo}
    return photo


# ---------- web server ----------

TILE_PATH = re.compile(r"^/tiles/(\d{1,2})/(\d+)/(\d+)\.png$")


def map_provider():
    return "carto" if CFG["carto_key"] else "osm"


def tile_url(z, x, y):
    if map_provider() == "carto":
        return CFG["carto_tile_url"].format(style=CFG["carto_style"], key=CFG["carto_key"],
                                            z=z, x=x, y=y)
    return CFG["osm_tile_url"].format(z=z, x=x, y=y)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def log_message(self, *args):
        pass

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/state":
            self.note_kiosk()
            return self.send_state()
        if path == "/api/health":
            return self.send_body(json.dumps(health()).encode(), "application/json")
        if path == "/settings":
            body = settings_page.page(current_theme(), CFG["name"], place_info(), VERSION, radius()).encode("utf-8")
            return self.send_body(body, "text/html; charset=utf-8")
        if path == "/api/settings":
            return self.send_body(json.dumps({"theme": current_theme(), "themes": settings_page.THEME_IDS}).encode(), "application/json")
        if path == "/api/extra":
            q = urllib.parse.parse_qs(self.path.split("?", 1)[1] if "?" in self.path else "")
            h = (q.get("hex") or [""])[0].lower()
            extra = {"photo": get_photo(h), "aircraft": get_aircraft(h) if HEX.match(h) else {}}
            return self.send_body(json.dumps(extra).encode("utf-8"), "application/json")
        m = TILE_PATH.match(path)
        if m:
            return self.send_tile(*map(int, m.groups()))
        if path in ("/", "/index.html"):
            return self.send_board()
        return super().do_GET()

    def send_board(self):
        """The board page, opening straight in Alex's saved style (no flash of the default after a restart)."""
        with open(os.path.join(WEB_DIR, "index.html"), encoding="utf-8") as f:
            page = f.read()
        page = page.replace('<body data-theme="solari">', f'<body data-theme="{current_theme()}">', 1)
        self.send_body(page.encode("utf-8"), "text/html; charset=utf-8")

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/api/settings":
            return self.send_body(b"", "text/plain", 404)
        try:
            n = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(min(n, 10000)).decode("utf-8") or "{}")
        except Exception:
            return self.send_body(b'{"error":"bad request"}', "application/json", 400)
        if "postcode" in data:
            return self.post_postcode(str(data.get("postcode") or ""))
        if "radius_mi" in data:
            try:
                r = int(data["radius_mi"])
            except (TypeError, ValueError):
                r = 0
            if r not in RANGES:
                return self.send_body(b'{"error":"unknown range"}', "application/json", 400)
            SETTINGS["radius_mi"] = r
            write_json("settings.json", SETTINGS)
            log(f"range changed to {r} miles")
            return self.send_body(json.dumps({"radius_mi": r}).encode(), "application/json")
        theme = data.get("theme")
        if theme not in settings_page.THEME_IDS:
            return self.send_body(b'{"error":"unknown style"}', "application/json", 400)
        SETTINGS["theme"] = theme
        write_json("settings.json", SETTINGS)
        log(f"style changed to {theme}")
        return self.send_body(json.dumps({"theme": theme}).encode(), "application/json")

    def post_postcode(self, raw):
        pc, _, err = postcode.normalise(raw)
        if err:
            return self.send_body(json.dumps({"error": err}).encode(), "application/json", 400)
        if (GEO.get(pc) or {}).get("missing"):   # typed again: look it up again
            GEO.pop(pc)
        g = lookup_postcode(pc)
        if g and g.get("missing"):
            return self.send_body(json.dumps({"error": f"{pc} wasn't found. Please check it."}).encode(), "application/json", 400)
        set_postcode(network_key(), pc)
        msg = f"Board moved to {g['city']}." if g else "Saved. The board will look it up as soon as it's online."
        return self.send_body(json.dumps({"postcode": pc, "place": g["city"] if g else "", "message": msg}).encode(),
                              "application/json")

    def note_kiosk(self):
        """The board screen asks for data every 5 s with k=1 and how many times it has drawn it (r)."""
        q = urllib.parse.parse_qs(self.path.split("?", 1)[1] if "?" in self.path else "")
        if (q.get("k") or [""])[0] != "1":
            return
        try:
            r = int((q.get("r") or ["-1"])[0])
        except ValueError:
            r = -1
        now = time.time()
        if r != KIOSK["r"]:
            KIOSK["rt"] = now
        KIOSK.update(t=now, r=r)

    def send_body(self, body, ctype, code=200, cache="no-store"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(body)

    def send_state(self):
        with LOCK:
            s = dict(STATE)
        attribution = "© OpenStreetMap" + (" · © CARTO" if map_provider() == "carto" else "")
        if SOURCE["name"]:
            attribution += " · " + CREDIT.get(SOURCE["name"], SOURCE["name"])
        body = json.dumps({
            "ok": s["ok"],
            "error": s["error"],
            "stale_s": round(time.time() - s["last_ok"]) if s["last_ok"] else None,
            "location": s["location"],
            "radius_mi": radius(),
            "theme": current_theme(),
            "place": s["place"],
            "version": VERSION,
            "settings_url": f"http://{lan_ip()}:{CFG['port']}/settings" if lan_ip() else None,
            "birthday": CFG["birthday"],
            "wifi": WIFI.public_state() if WIFI else None,
            "name": CFG["name"],
            "stats": s["stats"],
            "recent": s["recent"],
            "logbook": logbook_summary(),
            "weather": WEATHER["data"],
            "iss_tle": ISS["tle"],
            "today": s["today"],
            "map": {"provider": map_provider(), "attribution": attribution},
            "aircraft": s["aircraft"],
        }).encode("utf-8")
        self.send_body(body, "application/json")

    def send_tile(self, z, x, y):
        if z > 14 or x >= 2 ** z or y >= 2 ** z:
            return self.send_body(b"", "text/plain", 404)
        path = os.path.join(CACHE_DIR, "tiles", map_provider(), str(z), str(x), f"{y}.png")
        if not os.path.exists(path):
            try:
                data = fetch(tile_url(z, x, y), 10)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as f:
                    f.write(data)
            except Exception as e:
                log(f"tile {z}/{x}/{y} failed: {e}")
                return self.send_body(b"", "text/plain", 502)
        with open(path, "rb") as f:
            self.send_body(f.read(), "image/png", cache="max-age=86400")


def place_info():
    key, pc = wanted_postcode()
    with LOCK:
        loc = STATE["location"] or {}
    g = GEO.get(pc) if pc else None
    return {"postcode": pc or "", "city": loc.get("city", ""), "source": loc.get("source", ""),
            "missing": bool(g and g.get("missing")), "network": "" if key == "*" else key}


def health():
    now = time.time()
    with LOCK:
        ok, last_ok = STATE["ok"], STATE["last_ok"]
    return {"version": VERSION, "uptime_s": round(now - STARTED),
            "poller_age_s": round(now - BEAT["poller"]),
            "data_ok": ok, "data_age_s": round(now - last_ok) if last_ok else None,
            "kiosk_age_s": round(now - KIOSK["t"]) if KIOSK["t"] else None,
            "kiosk_drawn_age_s": round(now - KIOSK["rt"]) if KIOSK["rt"] else None,
            "kiosk_draws": KIOSK["r"] if KIOSK["t"] else None,
            "wifi": WIFI.state["mode"] if WIFI else None}


# ---------- systemd watchdog ----------
# Under systemd (on the Pi) the service must check in regularly, or systemd restarts it.
# It only checks in when the data loop is alive and the web server answers, so a hang anywhere gets a restart.

def sd_notify(msg):
    addr = os.environ.get("NOTIFY_SOCKET")
    if not addr:
        return
    if addr.startswith("@"):
        addr = "\0" + addr[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as s:
            s.connect(addr)
            s.sendall(msg.encode())
    except OSError:
        pass


def watchdog_loop():
    while True:
        time.sleep(15)
        try:
            if time.time() - BEAT["poller"] > 120:
                log("watchdog: data loop stuck")
                continue
            with urllib.request.urlopen(f"http://127.0.0.1:{CFG['port']}/api/health", timeout=10) as r:
                if r.status == 200:
                    sd_notify("WATCHDOG=1")
        except Exception as e:
            log(f"watchdog: web server not answering ({e})")


def shutdown(*_):
    """Clean stop (nightly restart, update, power-off): save everything first."""
    log("stopping: saving logbook and stats")
    sd_notify("STOPPING=1")
    save_all()
    sys.exit(0)


def on_joined(ssid, pc):
    set_postcode(ssid, pc)


def main():
    global WIFI
    signal.signal(signal.SIGTERM, shutdown)
    if WifiManager.enabled(CFG):
        WIFI = WifiManager(CFG, CACHE_DIR, log, on_joined=on_joined)
        WIFI.start()
        log("wifi setup manager running")
    threading.Thread(target=poller, daemon=True).start()
    server = ThreadingHTTPServer((CFG["host"], CFG["port"]), Handler)
    log(f"ALX Departures {VERSION} running at http://localhost:{CFG['port']} (certificates: {SSL_SOURCE})")
    sd_notify("READY=1")
    threading.Thread(target=watchdog_loop, daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
