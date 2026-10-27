# ALX Departures

A desk flight board for Alex: a Solari-style departure board of the aircraft overhead, plus a radar map of everything nearby (10, 15 or 25 miles, chosen on her phone).

```
alx/
  server.py            flight data service (Python standard library only)
  selftest.py          checks every free service the board uses, with a plain report
  wifi.py              Wi-Fi setup hotspot and phone setup page (Pi only)
  postcode.py          postcode checks and lookups (the board's location)
  settings_page.py     the phone page: postcode and board style
  config.example.json  optional settings, copy to config.json
  web/index.html       the 1024x600 board + radar page (fonts built in)
  STYLES.md            the saved board styles and how to add more
  UPDATES.md           sending updates to the board remotely
  VERSION              this version's number
  pi/install.sh        one-time Pi setup (kiosk screen, services, watchdogs, quiet boot)
  pi/alxctl.py         looks after the Pi: watchdog, nightly restart, updates, rollback
  pi/systemd/          the services and timers install.sh sets up
```

## Check the free services first

```
python3 selftest.py SG5 1AA
```

This tries every service the board uses, through the board's own code: location, your postcode, both flight feeds, routes, aircraft details, photos, weather, ISS and map. It prints PASS or FAIL for each, with what came back. One working service of each kind is enough.

**Windows: "certificate has expired" errors?** Windows' copy of Python often has an out-of-date list of trusted certificates, so sites using Let's Encrypt fail. Fix it once with `py -m pip install truststore certifi`. The board uses them automatically if they're there. The Pi doesn't need this.

## Try it on your laptop now

You need Python 3.8 or newer. Nothing else to install.

```
cd alx
python3 server.py
```

Then open **http://localhost:8080** in a browser. It finds your location from your internet connection, then shows real aircraft overhead, with routes and airlines filling in within a few seconds.

The terminal prints a line whenever something fails, such as a flight source being down or a location lookup failing. Press Ctrl+C to stop.

To preview the design without the server, open `web/index.html` directly. It runs on demo data over Hitchin.

## Settings (optional)

Copy `config.example.json` to `config.json` and edit:

- **`lat` / `lon` / `place`:** pin the location for good, overriding the postcode. Normally leave these out and use the postcode.
- **`carto_key`:** a free key from https://carto.com/basemaps/apikey/ switches the map to CARTO's darker style. Without one it uses OpenStreetMap tiles, tinted green.
- **`theme`:** board style: `solari`, `terminal`, `ivory`, `cockpit`, `crt`, `racing`, `jetage`, `paper`, `wavepunk`, `graphite` or `sunflower`. See `STYLES.md`.
- **`radius_mi`, `poll_s`, `port`:** starting radar range in miles (default 10; she can switch between 10, 15 and 25 on the phone page), update interval, web port.
- **`birthday`** (`"MM-DD"`) and **`name`:** for the greeting and the birthday surprise.
- **`contact`:** a website or email sent with requests so the free services know who's asking. Planespotters requires it.
- **`cache_dir`:** where it saves location, routes and map tiles.

## How it works

1. **Location:** the postcode saved for the Wi-Fi network it's on (looked up once on postcodes.io, or OpenStreetMap Nominatim outside the UK, and remembered). If there's no postcode yet, it uses free IP geolocation (ipwho.is, then ipapi.co, then ip-api.com), which can be 20–40 miles out, then the last saved location. A `lat`/`lon` in `config.json` overrides everything.
2. **Aircraft:** every 8 seconds from adsb.lol, falling back to adsb.fi, then airplanes.live. A feed that refuses or says "slow down" is left alone for a while. The feed in use is credited under the radar, as adsb.fi asks. Planes on the ground or outside the radar range are dropped.
3. **Routes and airlines:** looked up by callsign on adsbdb, then hexdb.io (a different database) if adsbdb doesn't know it, nearest planes first, cached for a day. A route that doesn't fit where the plane actually is (airlines reuse callsigns) is ignored. If no database knows a flight but it's low and clearly climbing out of, or descending into, a nearby airport, that end is filled in ("DEPARTED LUTON", "ARRIVING LUTON") from the OurAirports list in `airports.json`. Private flights show as PRIVATE.
4. **Photos:** the nearest aircraft's photo comes from Planespotters.net by its transponder code. Their free API requires the photographer's credit beside the photo, a QR code to the photo page on screens nobody can click, images loaded straight from their URLs (never saved or re-hosted), and a contact address in the request (`contact` in `config.json`). All of that is built in. With no photo available, a silhouette shows instead.
5. **Map:** the few tiles around the location are downloaded once and cached, then reused, so the map still shows after a reboot with no internet.
6. **Page:** polls `/api/state` every 5 seconds and moves the planes smoothly in between using each one's speed and heading.

If the data stops arriving, the board shows DELAYED, and planes are cleared after 5 minutes.

## What's on the board

- **Boarding-pass splash** while it starts up, with a time-of-day greeting.
- **Header greeting:** good morning (05:00–11:59), afternoon (12:00–16:59) or evening, plus the place.
- **Overhead Now card:** photo with credit and a QR code coloured to match the style, route, flight, airline, aircraft name and registration, altitude with climbing/descending, distance and bearing, speed, and which way to look.
- **Board rows:** live flights first, then the most recent ones to leave range, dimmed under "EARLIER TODAY" with the time they passed. Airline names come from a built-in list when a route lookup fails, and unknown routes show blank rather than dashes.
- **Radar:** fading trails behind each plane, labels that move to avoid overlapping (or hide if there's no room), and pulsing highlights for rare aircraft and emergencies.
- **Alerts:** rare types (A380, 747, Beluga, An-124, C-17, A400M, vintage warbirds and more), military aircraft, and emergency squawks (7500/7600/7700). The aircraft is starred in the card or footer with which way to look.
- **Footer stats:** rotates every 7 seconds between today's count, busiest hour, highest, fastest, furthest origin, aircraft types seen and the latest rare sighting. Saved through restarts and reset at midnight.
- **Aircraft icons:** airliners, wide-bodies, light aircraft and helicopters each get their own radar silhouette.
- **Spotter's logbook:** every aircraft (by registration) and every type is remembered with the day first seen. From day two, the card shows "FIRST SIGHTING" for a new aircraft and "★ NEW TYPE FOR THE LOGBOOK" for a new type, and the footer shows the running totals. Kept in `logbook.json` in the cache folder, which needs to be on writable storage on the Pi.
- **Spotting conditions:** from Open-Meteo every 15 minutes. Rated EXCELLENT / GOOD / FAIR / POOR from visibility, cloud and rain, with sunrise/sunset and a golden-hour flag.
- **ISS passes:** CelesTrak orbit data is downloaded twice a day, and the board works out visible passes itself (at least 10° up, sunlit, while it's dark where Alex is). The footer shows the next pass, a countdown when one is within 20 minutes, and "ISS OVERHEAD NOW · LOOK SE · 47° UP" during the pass, with a marker on the radar edge. Preview with `?iss`.
- **Birthday:** set `"birthday": "MM-DD"` in `config.json`. On the day the greeting changes, and every 15 minutes the board flips to a birthday message for 20 seconds. Preview it with `?birthday` on the address.

## The postcode

IP location can be miles out, so every Wi-Fi network the board uses gets a postcode:

- **On the Wi-Fi setup page,** the postcode box is required. It won't connect without a valid one. UK postcodes are checked on the spot (`SG5 1AA`, or just the district, `SG5`). Anything else is taken as an overseas postcode or ZIP and looked up in that country.
- **Each network remembers its own postcode.** If she takes the board between two homes, it moves the radar by itself when it changes Wi-Fi.
- **If the board has no postcode for its network** (say one set up another way, or when running on a laptop), the board shows "ONE MORE THING" with a QR code to the phone page until a postcode is entered. The same happens if a postcode isn't found. On a laptop, open http://localhost:8080/settings.
- **To change it,** use the Board location box at the top of the phone page.

Preview the board prompt with `?place` or `?place=error`.

## Previewing the special screens

Add these to the board's address (they work on the live board and on the file):

- `?wifi`: Wi-Fi setup screen; also `?wifi=connecting` and `?wifi=error`
- `?place`: postcode prompt; also `?place=error`
- `?iss`: an ISS pass overhead
- `?birthday`: the birthday surprise (flips in after about 8 seconds)
- `?theme=sunflower`: force a style, for testing only

## Changing the style

Alex can change the board style two ways, and the choice is saved on the device:

- **On the board:** tap the board window to open the style picker, then use ‹ › and DONE. It closes by itself after 25 seconds.
- **On her phone:** the picker shows a QR code for `http://<board's address>:8080/settings`, a page with a preview card for every style. This works while her phone is on the same Wi-Fi.

Every style uses exactly the same layout, checked pixel by pixel in a browser, so the faceplate always lines up. A style only changes colours and fonts. The screen draws no frame of its own: everything outside the board window and the radar porthole is one flat colour per style, sitting behind the physical faceplate. `theme` in `config.json` is just the starting style until she picks one.

## Wi-Fi setup (on the Pi)

`wifi.py` handles getting online, using Raspberry Pi OS's built-in NetworkManager:

- **First start-up:** with no Wi-Fi saved, after about 45 seconds the board shows "LET'S GET ONLINE" with two QR codes. The first joins the phone to the device's own network, **ALX-Setup**; the password is on screen and is generated once per device. A setup page then opens on the phone listing nearby networks. Pick one, type the password and the postcode, tap Connect.
- **Wrong password:** the setup screen comes back with a message and you can try again.
- **After that it never appears again.** NetworkManager remembers the network.
- **If the Wi-Fi drops** (router restart, moving house), it waits 3 minutes first. If setup does open, it keeps retrying the saved network every 5 minutes and reconnects by itself when it's back.

It only runs on a Raspberry Pi running as root (`"wifi_manage": "auto"`), so it does nothing on your laptop. Preview the screens with `?wifi`, `?wifi=connecting` or `?wifi=error` on the address.

## On the Pi

### Install (once)

1. Flash **Raspberry Pi OS Lite (64-bit)** with Raspberry Pi Imager. In its settings, turn on SSH, set a username and password, and add **your** Wi-Fi so you can reach it.
2. Copy the `alx` folder to the Pi (`scp -r alx pi@<address>:`), or unzip `alx-departures.zip` there.
3. If you're using remote updates, put `update_repo` (and `update_token` for a private repo) in `alx/config.json` first. See `UPDATES.md`.
4. `cd alx && sudo bash pi/install.sh`, then `sudo reboot`.

The install script:

- sets up the screen as a bare Chromium kiosk (cage), with the mouse pointer hidden and no screen blanking;
- adds the data service, the watchdogs and the nightly timer;
- sets the Wi-Fi country to GB and the time zone to Europe/London;
- makes the boot silent: no rainbow, Pi logo or scrolling text.

It's safe to run again: it never touches `/opt/alx/data`.

### Where things live

| | |
|---|---|
| `/opt/alx/current` | the version in use (each version in `/opt/alx/releases/`) |
| `/opt/alx/data/config.json` | settings. Updates never overwrite it |
| `/opt/alx/data/cache/` | Alex's logbook, today's stats, recent flights, style, postcodes and map tiles |

### Staying up by itself

- **Data service hangs or crashes:** it checks in with the system every 15 seconds, but only while it's actually working. If it misses 90 seconds, it's restarted.
- **Screen freezes:** the page checks in every 5 seconds with a count of updates it has drawn. If that stops for 3 minutes, the screen is restarted. If that happens 3 times in an hour, the Pi reboots (at most once every 6 hours).
- **Whole Pi locks up:** the Pi's hardware watchdog reboots it.
- **Nightly at 03:30:** it installs any update, then quietly restarts the service and the screen. The screen goes blank for a few seconds, with no text and no boarding pass. This clears any slow memory build-up.

### Restarts never lose her data

The logbook, stats, recent flights, style and postcodes are saved to `/opt/alx/data` every 2 minutes and on every clean stop: nightly restart, update, `sudo reboot`. Each save goes to a new file first, then swaps in, keeping the previous copy as a `.bak`. If the power is pulled mid-save, the next start uses the backup. A sudden power cut can lose at most the last 2 minutes. The only thing that resets is "today's" count, which is meant to start fresh at midnight.

### Handy commands (over SSH)

```
alxctl status                 version, health, last update
sudo alxctl update            check for an update now
sudo alxctl rollback          go back to the previous version
journalctl -u alx -f          live log of the data service
journalctl -u alx-nightly     what the last nightly run did
```

### Before wrapping it

Make it forget **your** Wi-Fi, so she gets the proper first start-up: `sudo nmcli connection delete preconfigured` (`nmcli connection show` lists the names). Then switch it off at the wall.

### If the picture is wrong

These 7" screens usually report 1024×600 themselves. If the image is cropped or blurry, add `video=HDMI-A-1:1024x600@60` to the end of `/boot/firmware/cmdline.txt` and reboot.

### Still to do

Making the SD card read-only would make sudden power cuts completely safe. Everything she keeps already lives under `/opt/alx/data`, so that can move to its own writable partition.

Chromium is launched with `--incognito` so aircraft photos are held in memory only. Planespotters' rules don't allow photos to be written to disk.

## Credits

Map data © OpenStreetMap contributors (and © CARTO if a key is set). This credit must stay on screen. Flight data from adsb.lol and airplanes.live; routes from adsbdb and hexdb.io; airport list from OurAirports (public domain); weather from Open-Meteo; ISS orbit data from CelesTrak (orbit maths by satellite.js, MIT licence). These are free community services, so keep the polling interval sensible.
