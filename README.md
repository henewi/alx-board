# ALX Departures

A desk flight board for Alex: a Solari-style departure board of the aircraft flying overhead, plus a radar map of everything nearby, in a hand-made wooden case.

<img src="docs/build/25-finished-at-night.jpg" width="800" alt="The finished board at night, showing live flights and the radar">

Happy birthday Al!

---

## The build

### Design

The Pi and the screen were 3D scanned first, so everything could be designed around the real parts.

#### Mounting the unit

A custom mount was designed after 3D scanning the Pi and the screen.

<img width="1150" height="808" alt="{4CFEB168-694B-4A32-A76C-45281FDCC25A}" src="https://github.com/user-attachments/assets/c01639ab-a3b0-4b92-9a1e-86aba4c52713" />

#### The 3D scans inside the wooden body

The Pi and screen, 3D scanned and placed inside the wooden body in CAD. The body is then cut out with a mill, using the printed template.

<img src="docs/build/1-scans-in-the-wooden-body.jpg" width="700" alt="3D scans of the Pi and screen inside the wooden body, in CAD">

#### Rear view in CAD, with the carbon plate

<img src="docs/build/2-cad-rear-view-carbon-plate.jpg" width="700" alt="Rear view of the body in CAD with the carbon fibre plate">

#### The printed mount for the Pi and screen

> This is the bit I mentioned when we were on the phone and I said "I'll include it in the repo!" This was my view!

<img src="docs/build/3-printed-pi-and-screen-mount.jpg" width="500" alt="The 3D printed mount holding the Raspberry Pi">

#### Printing the cutting template for the wood

<img src="docs/build/4-printing-the-wood-template.jpg" width="700" alt="The cutting template for the wood being 3D printed">

#### The cutting template and the mount

<img src="docs/build/5-template-and-mount.jpg" width="500" alt="The printed cutting template with the mount inside it">

#### Designing the faceplate to look like separate screens

<img width="1920" height="1080" alt="{BF3C49DF-6404-49BC-BA1B-FCB3F411231A}" src="https://github.com/user-attachments/assets/98aed5e2-f491-4f03-9c6e-a81e46241af1" />

<img width="1920" height="1080" alt="{173E54D9-A880-4AE3-A92A-569D5BF94B29}" src="https://github.com/user-attachments/assets/cc6dce34-bcaf-4a2f-9460-12baa2dd00dd" />

### The wooden body

I collected the wood from a nearby farm after seeing the listing on Facebook Marketplace, then machined the body out of a single block.

#### Milling the pocket

<img src="docs/build/07-milling-the-body.jpg" width="700" alt="Milling the pocket into the wooden block on a manual mill">

#### Cut through, still clamped to the mill

<img src="docs/build/08-pocket-cut-through.jpg" width="700" alt="The pocket cut right through the block, still clamped to the mill bed">

#### The frame freed from the block

<img src="docs/build/09-frame-freed-from-the-block.jpg" width="700" alt="The wooden frame lifted out of the block it was cut from">

### The mount

#### The Pi on the printed mount

<img src="docs/build/10-pi-on-the-mount.jpg" width="500" alt="The Raspberry Pi fitted to the black 3D printed mount">

#### The mount on the back of the screen

<img src="docs/build/11-mount-on-the-screen-side.jpg" width="500" alt="Side view of the mount and Pi fitted to the back of the screen">

<img src="docs/build/12-mount-on-the-screen-top.jpg" width="700" alt="Top view of the mount and Pi on the back of the screen">

### Finishing the body

#### Sanding the corners on the disc sander

<img src="docs/build/13-sanding-the-corners.jpg" width="700" alt="Sanding an outside corner of the frame on a disc sander">

#### Sanded, with the mounting holes drilled

<img src="docs/build/14-holes-drilled.jpg" width="700" alt="The sanded frame with mounting holes drilled in the top face">

#### Lacquering in the spray booth

<img src="docs/build/15-lacquering-the-frame.jpg" width="700" alt="The frame hanging in a spray booth being lacquered">

### Putting it together

#### Test fit in the frame

Heat-set inserts in the wood take the screws.

<img src="docs/build/16-mount-in-the-frame.jpg" width="700" alt="The mount and Pi test-fitted inside the wooden frame, with brass inserts in the wood">

#### Printing the back plate

<img src="docs/build/17-printing-the-back-plate.jpg" width="700" alt="The textured black back plate being 3D printed">

#### The back plate fitted

The back carries a message for Alex, plus the address of this repo and of the settings page.

<img src="docs/build/18-back-plate-fitted.jpg" width="700" alt="The back plate screwed on, with a window showing the Pi and an embossed birthday message">

#### First boot, behind the first printed faceplate

<img src="docs/build/19-first-boot-green-faceplate.jpg" width="700" alt="The board running for the first time behind a green printed faceplate">

#### Test fit in the frame with a black faceplate

<img src="docs/build/20-test-fit-in-the-frame.jpg" width="500" alt="The board running inside the wooden frame with a black faceplate">

#### Painting the final faceplate

<img src="docs/build/21-painting-the-faceplate.jpg" width="700" alt="The printed faceplate hanging in a spray booth after painting">

#### The layers

Faceplate, screen, the Pi and its cables, then the back plate, all held on printed standoffs.

<img src="docs/build/22-the-layers-side-view.jpg" width="700" alt="Side view of the assembled stack showing the faceplate, screen, Pi, cables and back plate">

#### Ready to go in

<img src="docs/build/23-ready-to-go-in.jpg" width="700" alt="The assembled unit with the painted faceplate, next to the empty wooden frame">

### Finished

<img src="docs/build/24-finished-on-the-desk.jpg" width="700" alt="The finished board on a desk in the navy and amber style">

---

## Features

### The departure board

- **Overhead Now:** the nearest aircraft, with its photo, route, flight number, airline, aircraft type and registration, altitude (and whether it's climbing or descending), distance, speed, and which way to look to see it.
- **Board rows:** every flight in range, then the ones that have just left, dimmed under "EARLIER TODAY" with the time they passed.
- **Greeting:** good morning, afternoon or evening, with the name of the place.
- **Boarding-pass splash** while it starts up.

### The radar

- Every aircraft within 10, 15 or 25 miles, chosen on her phone, on a map of the area.
- Fading trails behind each plane, and labels that move out of each other's way.
- Different silhouettes for airliners, wide-bodies, light aircraft and helicopters.

### For a plane spotter

- **Alerts for rare aircraft:** A380s, 747s, the Beluga, An-124s, C-17s, A400Ms, vintage warbirds and more, plus military aircraft and emergency squawks. They pulse on the radar and are starred on the board.
- **Spotter's logbook:** every aircraft and every type is remembered with the day it was first seen. A new one gets "FIRST SIGHTING" or "★ NEW TYPE FOR THE LOGBOOK".
- **Footer stats:** today's count, busiest hour, highest, fastest, furthest origin, types seen and the latest rare sighting, rotating every few seconds.
- **Spotting conditions:** visibility, cloud and rain rated EXCELLENT to POOR, with sunrise, sunset and golden hour.
- **ISS passes:** the next visible pass, a countdown, and which way to look while it's overhead.

### Make it yours

- **Twenty board styles,** picked by tapping the screen or from her phone: from the classic Solari split flaps and an Airbus cockpit to Sunflower (her favourite colour), Blueprint, Renaissance, Cosmos, Grand Prix and a bowl of pho. The layout is identical in every style, so the faceplate always lines up. See `STYLES.md` for all of them.
- **Phone settings page:** board location and style, reached by scanning a QR code.
- **Birthday surprise:** on the day, the greeting changes and the board flips to a birthday message every 15 minutes.

### Looks after itself

- **Easy Wi-Fi setup:** on first start-up, scan the QR code, pick the network on your phone, type the password and postcode, and you're done. Whenever it's offline, the board says what it's trying rather than going blank.
- **Moves house with you:** each Wi-Fi network remembers its own postcode, so the radar follows the board between homes.
- **Recovers by itself** from crashes, frozen screens and dropped Wi-Fi, and installs updates quietly overnight.
- **Never loses her logbook:** everything is saved every 2 minutes and survives restarts and power cuts.

---

## Technical

### Files

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

### Check the free services first

```
python3 selftest.py SG5 1AA
```

This tries every service the board uses, through the board's own code: location, your postcode, both flight feeds, routes, aircraft details, photos, weather, ISS and map. It prints PASS or FAIL for each, with what came back. One working service of each kind is enough.

**Windows: "certificate has expired" errors?** Windows' copy of Python often has an out-of-date list of trusted certificates, so sites using Let's Encrypt fail. Fix it once with `py -m pip install truststore certifi`. The board uses them automatically if they're there. The Pi doesn't need this.

### Try it on your laptop

You need Python 3.8 or newer. Nothing else to install.

```
cd alx
python3 server.py
```

Then open **http://localhost:8080** in a browser. It finds your location from your internet connection, then shows real aircraft overhead, with routes and airlines filling in within a few seconds.

The terminal prints a line whenever something fails, such as a flight source being down or a location lookup failing. Press Ctrl+C to stop.

To preview the design without the server, open `web/index.html` directly. It runs on demo data over Hitchin.

### Settings (optional)

Copy `config.example.json` to `config.json` and edit:

- **`lat` / `lon` / `place`:** pin the location for good, overriding the postcode. Normally leave these out and use the postcode.
- **`carto_key`:** a free key from https://carto.com/basemaps/apikey/ switches the map to CARTO's darker style. Without one it uses OpenStreetMap tiles, tinted green.
- **`theme`:** board style: `solari`, `terminal`, `cockpit`, `crt`, `sage`, `dusk`, `sandstone`, `paper`, `renaissance`, `wavepunk`, `blueprint`, `bosnia`, `sunflower`, `disco`, `popart`, `groovy`, `candy`, `cosmos`, `grandprix` or `pho`. See `STYLES.md`.
- **`radius_mi`, `poll_s`, `port`:** starting radar range in miles (default 10; she can switch between 10, 15 and 25 on the phone page), update interval, web port.
- **`birthday`** (`"MM-DD"`) and **`name`:** for the greeting and the birthday surprise.
- **`contact`:** a website or email sent with requests so the free services know who's asking. Planespotters requires it.
- **`cache_dir`:** where it saves location, routes and map tiles.

### How it works

1. **Location:** the postcode saved for the Wi-Fi network it's on (looked up once on postcodes.io, or OpenStreetMap Nominatim outside the UK, and remembered). If there's no postcode yet, it uses free IP geolocation (ipwho.is, then ipapi.co, then ip-api.com), which can be 20–40 miles out, then the last saved location. A `lat`/`lon` in `config.json` overrides everything.
2. **Aircraft:** every 8 seconds from adsb.fi, falling back to adsb.lol, then airplanes.live. A feed that refuses or says "slow down" is left alone for a while. Planes on the ground or outside the radar range are dropped.
3. **Routes and airlines:** looked up by callsign on adsbdb, then hexdb.io (a different database) if adsbdb doesn't know it, nearest planes first, cached for a day. A route that doesn't fit where the plane actually is (airlines reuse callsigns) is ignored. If no database knows a flight but it's low and clearly climbing out of, or descending into, a nearby airport, that end is filled in ("DEPARTED LUTON", "ARRIVING LUTON") from the OurAirports list in `airports.json`. Private flights show as PRIVATE.
4. **Photos:** the nearest aircraft's photo comes from Planespotters.net by its transponder code. Their free API requires the photographer's credit beside the photo, a QR code to the photo page on screens nobody can click, images loaded straight from their URLs (never saved or re-hosted), and a contact address in the request (`contact` in `config.json`). All of that is built in. With no photo available, a silhouette shows instead.
5. **Map:** the few tiles around the location are downloaded once and cached, then reused, so the map still shows after a reboot with no internet.
6. **Page:** polls `/api/state` every 5 seconds and moves the planes smoothly in between using each one's speed and heading.

If the data stops arriving, the board shows DELAYED, and planes are cleared after 5 minutes.

### Feature details

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

### The postcode

IP location can be miles out, so every Wi-Fi network the board uses gets a postcode:

- **On the Wi-Fi setup page,** the postcode box is required. It won't connect without a valid one. UK postcodes are checked on the spot (`SG5 1AA`, or just the district, `SG5`). Anything else is taken as an overseas postcode or ZIP and looked up in that country.
- **Each network remembers its own postcode.** If she takes the board between two homes, it moves the radar by itself when it changes Wi-Fi.
- **If the board has no postcode for its network** (say one set up another way, or when running on a laptop), the board shows "ONE MORE THING" with a QR code to the phone page until a postcode is entered. The same happens if a postcode isn't found. On a laptop, open http://localhost:8080/settings.
- **To change it,** use the Board location box at the top of the phone page.

Preview the board prompt with `?place` or `?place=error`.

### Previewing the special screens

Add these to the board's address (they work on the live board and on the file):

- `?wifi`: Wi-Fi setup screen; also `?wifi=connecting` and `?wifi=error`
- `?wifi=looking`, `?wifi=new`, `?wifi=signin`: the "looking for Wi-Fi" countdown screen (saved network nearby / none nearby / a network that wants a sign-in page)
- `?place`: postcode prompt; also `?place=error`
- `?iss`: an ISS pass overhead
- `?birthday`: the birthday surprise (flips in after about 8 seconds)
- `?theme=sunflower`: force a style, for testing only

### Changing the style

Alex can change the board style two ways, and the choice is saved on the device:

- **On the board:** tap the board window to open the style picker, then use ‹ › and DONE. It closes by itself after 25 seconds.
- **On her phone:** the picker shows a QR code for `http://<board's address>:8080/settings`, a page with a preview card for every style. This works while her phone is on the same Wi-Fi.

Every style uses exactly the same layout, checked pixel by pixel in a browser, so the faceplate always lines up. A style only changes colours and fonts. The screen draws no frame of its own: everything outside the board window and the radar porthole is one flat colour per style, sitting behind the physical faceplate. `theme` in `config.json` is just the starting style until she picks one.

### Wi-Fi setup (on the Pi)

`wifi.py` handles getting online, using Raspberry Pi OS's built-in NetworkManager:

- **Never an empty board.** Whenever it isn't online, the board says so: "LOOKING FOR WI-FI", what it's trying, and a countdown to Wi-Fi setup.
- **Somewhere new** (first start-up, or no saved network in range): setup opens after about 40 seconds. The board shows "LET'S GET ONLINE" with two QR codes. The first joins the phone to the device's own network, **ALX-Setup**; the password is on screen and is generated once per device. A setup page then opens on the phone listing nearby networks. Pick one, type the password and the postcode, tap Connect.
- **A saved network is in range but not working yet** (router restarting): it gives it 2½ minutes before opening setup.
- **Wrong password:** the setup screen comes back and says so.
- **Networks with a sign-in page** (work or hotel guest Wi-Fi) can't work: the board has no way to fill that page in. It says exactly that, instead of blaming the password, and asks for another network or a phone hotspot.
- **After that it never appears again.** NetworkManager remembers the network.
- **While in setup** it retries the saved networks every 5 minutes and reconnects by itself when one is back. It waits while someone is using the setup page (up to 10 extra minutes), so it never pulls the network from under them. If the setup network itself drops, it restarts it.

It only runs on a Raspberry Pi running as root (`"wifi_manage": "auto"`), so it does nothing on your laptop. Preview the screens with `?wifi`, `?wifi=connecting`, `?wifi=error`, `?wifi=looking`, `?wifi=new` or `?wifi=signin` on the address.

### On the Pi

#### Install (once)

1. Flash **Raspberry Pi OS Lite (64-bit)** with Raspberry Pi Imager. In its settings, turn on SSH, set a username and password, and add **your** Wi-Fi so you can reach it.
2. Copy the `alx` folder to the Pi (`scp -r alx pi@<address>:`), or unzip `alx-departures.zip` there.
3. If you're using remote updates, put `update_repo` (and `update_token` for a private repo) in `alx/config.json` first. See `UPDATES.md`.
4. `cd alx && sudo bash pi/install.sh`, then `sudo reboot`.

The install script:

- sets up the screen as a bare Chromium kiosk (cage), with the mouse pointer hidden and no screen blanking;
- adds the data service, the watchdogs and the nightly timer;
- sets the Wi-Fi country to GB and the time zone to Europe/London;
- makes the boot silent: no rainbow, Pi logo or scrolling text;
- turns off the Pi's red and green lights, which would glow through the faceplate. (The board service also does this every time it starts, so updates bring it to boards installed earlier. Set `"leds_off": false` in `config.json` to keep them.)

It's safe to run again: it never touches `/opt/alx/data`.

#### Where things live

| | |
|---|---|
| `/opt/alx/current` | the version in use (each version in `/opt/alx/releases/`) |
| `/opt/alx/data/config.json` | settings. Updates never overwrite it |
| `/opt/alx/data/cache/` | Alex's logbook, today's stats, recent flights, style, postcodes and map tiles |

#### Staying up by itself

- **Data service hangs or crashes:** it checks in with the system every 15 seconds, but only while it's actually working. If it misses 90 seconds, it's restarted.
- **Screen freezes:** the page checks in every 5 seconds with a count of updates it has drawn. If that stops for 3 minutes, the screen is restarted. If that happens 3 times in an hour, the Pi reboots (at most once every 6 hours).
- **Whole Pi locks up:** the Pi's hardware watchdog reboots it.
- **Nightly at 03:30:** it installs any update, then quietly restarts the service and the screen. The screen goes blank for a few seconds, with no text and no boarding pass. This clears any slow memory build-up.

#### Restarts never lose her data

The logbook, stats, recent flights, style and postcodes are saved to `/opt/alx/data` every 2 minutes and on every clean stop: nightly restart, update, `sudo reboot`. Each save goes to a new file first, then swaps in, keeping the previous copy as a `.bak`. If the power is pulled mid-save, the next start uses the backup. A sudden power cut can lose at most the last 2 minutes. The only thing that resets is "today's" count, which is meant to start fresh at midnight.

#### Handy commands (over SSH)

```
alxctl status                 version, health, last update
sudo alxctl update            check for an update now
sudo alxctl rollback          go back to the previous version
journalctl -u alx -f          live log of the data service
journalctl -u alx-nightly     what the last nightly run did
```

#### Before wrapping it

Make it forget **your** Wi-Fi, so she gets the proper first start-up: `sudo nmcli connection delete preconfigured` (`nmcli connection show` lists the names). Then switch it off at the wall.

#### If the picture is wrong

These 7" screens usually report 1024×600 themselves. If the image is cropped or blurry, add `video=HDMI-A-1:1024x600@60` to the end of `/boot/firmware/cmdline.txt` and reboot.

### Credits

Map data © OpenStreetMap contributors (and © CARTO if a key is set). The on-screen map credit is hidden because the board is a private display in one home; the credits are kept here. Flight data from adsb.fi, adsb.lol and airplanes.live; routes from adsbdb and hexdb.io; aircraft photos from Planespotters.net; airport list from OurAirports (public domain); weather from Open-Meteo; ISS orbit data from CelesTrak (orbit maths by satellite.js, MIT licence). These are free community services, so keep the polling interval sensible.
