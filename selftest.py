#!/usr/bin/env python3
"""
ALX Departures self-test: tries every free service the board relies on, using the
board's own code, and prints a plain report. Nothing is changed or saved except the
usual caches.

    python3 selftest.py              (or:  python3 selftest.py SG5 1AA  to test your postcode)

Copy everything it prints and send it back.
"""

import json
import os
import platform
import sys
import time
import traceback
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import server as S          # the board's own code, so this tests exactly what the board does
import postcode

RESULTS = []
DETAILS = []


def check(name, fn):
    t = time.time()
    try:
        detail = fn()
        ok = True
    except Exception as e:
        ok, detail = False, f"{type(e).__name__}: {e}"
        if not isinstance(e, (urllib.error.URLError, OSError, ValueError)):
            detail += "\n      " + traceback.format_exc().strip().splitlines()[-2].strip()
    ms = round((time.time() - t) * 1000)
    RESULTS.append((ok, name))
    DETAILS.append(detail)
    print(f"{'PASS' if ok else 'FAIL'}  {name:<26} {ms:>5} ms  {detail}", flush=True)
    return detail if ok else None


def main():
    pc_arg = " ".join(sys.argv[1:]).strip() or "SG5"
    print(f"ALX Departures self-test · version {S.VERSION} · Python {platform.python_version()} · {platform.system()}")
    print(f"Contact sent to services: {S.CFG['contact']} · certificates: {S.SSL_SOURCE}\n")

    # Location
    for url in S.CFG["geo_urls"]:
        def ip(url=url):
            d = S.fetch_json(url, 6)
            lat = d.get("latitude", d.get("lat")); lon = d.get("longitude", d.get("lon"))
            if lat is None:
                raise ValueError(f"no position in reply: {str(d)[:120]}")
            return f"{d.get('city')} {lat},{lon} country={d.get('country_code') or d.get('countryCode')}"
        check(f"IP location {url.split('/')[2]}", ip)

    pc, kind, err = postcode.normalise(pc_arg)
    def lookup():
        if err:
            raise ValueError(err)
        return postcode.geocode(pc, kind, S.fetch_json, S.CFG, "GB")
    place = check(f"Postcode {pc_arg}", lookup)
    loc = ({"lat": place["lat"], "lon": place["lon"], "city": place["city"]} if isinstance(place, dict)
           else {"lat": 51.9496, "lon": -0.2797, "city": "Hitchin (fallback)"})
    print(f"      using {loc['city']} {loc['lat']},{loc['lon']} for the rest")

    def town():
        import urllib.parse
        d = S.fetch_json(S.CFG["nominatim_url"] + "/reverse?" + urllib.parse.urlencode(
            {"lat": loc["lat"], "lon": loc["lon"], "zoom": 18, "format": "jsonv2", "addressdetails": 1}), 10)
        return postcode._town(d.get("address") or {}) or f"no town in reply: {str(d)[:100]}"
    check("Town name Nominatim", town)
    print()

    # Flights: each source on its own
    planes = []
    nm = int(S.radius() / 1.15078) + 1
    for url in S.CFG["flight_urls"]:
        def flights(url=url):
            d = S.fetch_json(url.format(lat=loc["lat"], lon=loc["lon"], nm=nm), 8)
            raw = d.get("ac") or d.get("aircraft") or []
            built = S.build(raw, loc)
            if not planes:
                planes.extend(built)
            near = built[0] if built else None
            return (f"{len(raw)} raw, {len(built)} airborne in {S.radius():g} mi"
                    + (f" · nearest {near['callsign'] or near['hex']} {near['type']} {near['alt']} ft {near['dist']:.1f} mi" if near else ""))
        check(f"Flights {url.split('/')[2]}", flights)

    # Routes, aircraft details and photos for the nearest few
    airline = next((a for a in planes if a["callsign"] and S.AIRLINE_CALLSIGN.match(a["callsign"])), None)
    airlines = [a for a in planes if a["callsign"] and S.AIRLINE_CALLSIGN.match(a["callsign"])][:6]
    if airlines:
        def hexdb():
            d = S.fetch_json(S.CFG["route2_url"].format(cs=airlines[0]["callsign"]), 6)
            r = S.parse_hexdb(d)
            return f"{airlines[0]['callsign']}: {r['from']['city']} → {r['to']['city']}" if r else f"reply: {str(d)[:80]}"
        def routes():
            found = []
            for a in airlines:
                r = S.lookup_route(a["callsign"], a) or S.infer_route(a)
                found.append(f"{a['callsign']} " + (f"{r['from']['city'] or '…'}→{r['to']['city'] or '…'}" if r else "unknown"))
            known = sum(1 for f in found if not f.endswith("unknown"))
            return f"{known} of {len(found)} routes found: " + ", ".join(found)
        check("Route hexdb", hexdb)
        check("Routes (all sources)", routes)
    else:
        print("SKIP  Route adsbdb              no airline flight overhead right now")
    if planes:
        h = planes[0]["hex"]
        check("Aircraft adsbdb", lambda: S.get_aircraft(h) or f"{h}: not in database (fine)")
        def photo():
            p = S.get_photo(h)
            return f"{h}: © {p['photographer']} · {p['src'][:60]}…" if p else f"{h}: no photo (silhouette shows instead)"
        check("Photo Planespotters", photo)

    # Weather, ISS, map, town names
    check("Weather Open-Meteo", lambda: S.parse_weather(S.fetch_json(
        S.CFG["weather_url"].format(lat=loc["lat"], lon=loc["lon"]), 8)))

    def iss():
        S.refresh_iss()            # respects CelesTrak's twice-a-day limit (uses the saved copy if recent)
        if not S.ISS["tle"]:
            raise ValueError("no orbit data")
        return f"orbit epoch {S.ISS['tle'][0][18:32]}"
    check("ISS CelesTrak", iss)

    def tile():
        data = S.fetch(S.tile_url(10, 511, 340), 10)
        if data[:4] != b"\x89PNG":
            raise ValueError(f"not a map image ({len(data)} bytes)")
        return f"{S.map_provider()} tile {len(data)} bytes"
    check("Map tiles", tile)

    print()
    bad = [n for ok, n in RESULTS if not ok]
    print(f"{len(RESULTS) - len(bad)} of {len(RESULTS)} passed." + (f" Failed: {', '.join(bad)}" if bad else " Everything the board needs is reachable."))
    print("Some failures are fine as long as one of each kind works (e.g. one IP location service, one flight source).")
    if any("CERTIFICATE_VERIFY_FAILED" in str(d) for d in DETAILS):
        print("\nCertificate errors: this computer's Python has an out-of-date list of trusted certificates.")
        print("Fix:  py -m pip install certifi      (Mac/Linux: python3 -m pip install certifi)   then run this again.")


if __name__ == "__main__":
    main()
