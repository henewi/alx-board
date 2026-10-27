"""
Postcodes for ALX Departures.

Every Wi-Fi network the board joins gets a postcode, so the radar is centred on the
right place (internet-based location can be 20-40 miles out). UK postcodes are checked
on the spot, before joining; anything else is accepted as an overseas postcode or ZIP.

Lookups, cached forever per postcode:
  * UK full postcode   -> postcodes.io             (free, no key)
  * UK district (SG5)  -> postcodes.io outcodes
  * anywhere else      -> OpenStreetMap Nominatim  (free, one lookup per postcode, as their policy asks)
  * the town name      -> postcodes.io's built-up area or parish (UK), else a Nominatim reverse lookup,
                          else the district
"""

import re
import urllib.error
import urllib.parse

UK_FULL = re.compile(r"^([A-Z]{1,2}[0-9][A-Z0-9]?)([0-9][A-Z]{2})$")
UK_DISTRICT = re.compile(r"^[A-Z]{1,2}[0-9][A-Z0-9]?$")
UK_ISH = re.compile(r"^[A-Z]{1,2}[0-9]")
OTHER = re.compile(r"^(?=.*[0-9])[A-Z0-9][A-Z0-9 -]{1,9}$")


class NotFound(Exception):
    """The postcode doesn't exist (as opposed to the lookup service being unreachable)."""


def normalise(text):
    """Returns (postcode, kind, error). kind is 'gb', 'gb-district' or 'other'."""
    t = re.sub(r"\s+", " ", (text or "").upper()).strip()
    squashed = t.replace(" ", "")
    if not t:
        return None, None, "Please enter the postcode where the board lives."
    m = UK_FULL.match(squashed)
    if m:
        return f"{m.group(1)} {m.group(2)}", "gb", ""
    if UK_DISTRICT.match(squashed) and len(squashed) <= 4:
        return squashed, "gb-district", ""
    if UK_ISH.match(squashed) and len(squashed) <= 8:
        return None, None, f"{t} doesn't look like a UK postcode. It should look like SG5 1AA."
    if OTHER.match(t):
        return t, "other", ""
    return None, None, "That doesn't look like a postcode. It should look like SG5 1AA."


PLACE_KEYS = ("town", "city", "village", "hamlet", "suburb")


def _town(addr, broad=True):
    for k in PLACE_KEYS + (("municipality", "county") if broad else ()):
        if addr.get(k):
            return addr[k]
    return ""


def geocode(pc, kind, fetch_json, cfg, country=None):
    """Returns {"lat", "lon", "city"}. Raises NotFound, or another exception if the service is unreachable."""
    q = urllib.parse.quote(pc)
    city = ""
    if kind in ("gb", "gb-district"):
        url = cfg["postcode_url" if kind == "gb" else "outcode_url"].format(pc=q)
        try:
            r = fetch_json(url, 8).get("result") or {}
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise NotFound(pc)
            raise
        if r.get("latitude") is None:
            raise NotFound(pc)
        lat, lon = float(r["latitude"]), float(r["longitude"])
        district = r.get("admin_district")
        district = (district[0] if isinstance(district, list) and district else district) or ""
        parish = r.get("parish") if isinstance(r.get("parish"), str) else ""
        if parish and "unparished" in parish.lower():
            parish = ""
        bua = r.get("bua") if isinstance(r.get("bua"), str) else ""   # built-up area, e.g. "Hitchin"
        city = bua or parish
        if city:
            return {"lat": round(lat, 4), "lon": round(lon, 4), "city": city, "v": 2}
        city = district
    else:
        params = {"postalcode": pc, "format": "jsonv2", "limit": 1, "addressdetails": 1}
        if country:
            params["countrycodes"] = country.lower()
        hits = fetch_json(cfg["nominatim_url"] + "/search?" + urllib.parse.urlencode(params), 10)
        if not hits:
            raise NotFound(pc)
        lat, lon = float(hits[0]["lat"]), float(hits[0]["lon"])
        city = _town(hits[0].get("address") or {})
    try:   # nicer town name ("Hitchin" rather than "North Hertfordshire")
        rev = fetch_json(cfg["nominatim_url"] + "/reverse?" + urllib.parse.urlencode(
            {"lat": lat, "lon": lon, "zoom": 18, "format": "jsonv2", "addressdetails": 1}), 10)   # street level: names the actual town
        city = _town(rev.get("address") or {}, broad=False) or city
    except Exception:
        pass
    return {"lat": round(lat, 4), "lon": round(lon, 4), "city": city or pc, "v": 2}
