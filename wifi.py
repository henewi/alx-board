"""
Wi-Fi setup for ALX Departures (Raspberry Pi OS, which uses NetworkManager).

How it behaves:
  * Connected and working: does nothing.
  * Not connected: the board says so straight away ("LOOKING FOR WI-FI") with a
    countdown, and never shows an empty departures board.
      - No saved network is in range (first start-up, or taken somewhere new):
        setup opens after about 40 seconds.
      - A saved network is in range but not working yet (router restarting):
        it gives it a couple of minutes, then opens setup.
  * Setup: its own Wi-Fi network, "ALX-Setup". The board shows a QR code to join it;
    a setup page opens on the phone; pick the Wi-Fi, type the password and postcode.
    While in setup it retries the saved networks every few minutes (but never while
    someone is using the setup page), so it reconnects by itself if the router returns.
  * Networks with a sign-in page (work or hotel guest Wi-Fi) can't work, because the
    board has no way to fill that page in. It says so in plain words, rather than
    blaming the password, and asks for a different network or a phone hotspot.
NetworkManager remembers the network, so setup never appears again until needed.

Every new network needs a postcode as well, so the radar is centred on the right place.
The setup page won't connect without one, and it's remembered per network.

Standard library only. Needs to run as root on the Pi (to control Wi-Fi and serve
the setup page on port 80).
"""

import html
import http.client
import json
import os
import random
import re
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import postcode

AP_NAME = "ALX-Setup"
AP_ADDR = "10.42.0.1"                      # NetworkManager's address for a shared hotspot
# Plain-http addresses that answer with a fixed reply when the internet really works. A network with a
# sign-in page answers them with its own page instead, which is how that's spotted. (Phones do the same.)
PROBES = [("http://connectivitycheck.gstatic.com/generate_204", 204, ""),
          ("http://captive.apple.com/hotspot-detect.html", 200, "Success")]
CAPTIVE_CONF = "/etc/NetworkManager/dnsmasq-shared.d/alx-captive.conf"


def split_terse(line):
    """nmcli -t output: fields separated by ':', with ':' inside values escaped as '\\:'."""
    return [p.replace("\\:", ":").replace("\\\\", "\\") for p in re.split(r"(?<!\\):", line)]


class WifiManager:
    @staticmethod
    def enabled(cfg):
        mode = cfg.get("wifi_manage", "auto")
        if mode is True or mode is False:
            return mode
        if not sys.platform.startswith("linux") or not shutil.which("nmcli"):
            return False
        try:
            if os.geteuid() != 0:
                return False
            with open("/proc/device-tree/model") as f:
                return "Raspberry Pi" in f.read()
        except Exception:
            return False

    def __init__(self, cfg, cache_dir, log, on_joined=None):
        self.cfg, self.log = cfg, log
        self.on_joined = on_joined            # called with (ssid, postcode) after joining a network from the setup page
        self._active = {"ssid": None, "t": 0.0}
        self.nmcli = cfg.get("nmcli") or shutil.which("nmcli") or "nmcli"
        self.iface = cfg.get("wifi_iface", "wlan0")
        self.grace_new = cfg.get("wifi_grace_new_s", 40)       # no saved network in range: open setup after this
        self.grace_known = cfg.get("wifi_grace_known_s", 150)  # a saved network is in range: give it this long
        self.grace_signin = cfg.get("wifi_grace_signin_s", 60) # joined, but it wants a sign-in page / has no internet
        self.retry_s = cfg.get("wifi_retry_s", 300)            # in setup: retry saved networks this often
        self.busy_s = cfg.get("wifi_portal_busy_s", 150)       # ...but not within this long of someone using the setup page
        self.portal_port = cfg.get("wifi_portal_port", 80)
        self.probes = cfg.get("wifi_probes", PROBES)
        self.lock = threading.Lock()
        self.radio = threading.RLock()        # one thing at a time touches the Wi-Fi radio
        self.portal = None
        self.portal_hit = 0.0                 # last time a phone used the setup page
        self._probe = {"ok": False, "t": 0.0}
        pw_file = os.path.join(cache_dir, "wifi_setup.json")
        try:
            with open(pw_file) as f:
                pw = json.load(f)["password"]
        except Exception:
            pw = "".join(random.choice("23456789") for _ in range(8))   # 8 digits, easy to type
            try:
                with open(pw_file, "w") as f:
                    json.dump({"password": pw}, f)
            except Exception:
                pass
        self.state = {"mode": "checking", "ap_ssid": AP_NAME, "ap_password": pw,
                      "portal": f"http://{AP_ADDR}", "target": "", "error": "", "networks": [], "postcode": "",
                      "setup_at": None, "looking_for": [], "joined": "", "problem": ""}

    # ---------- small helpers ----------
    def run(self, *args, timeout=30):
        try:
            p = subprocess.run([self.nmcli, *args], capture_output=True, text=True, timeout=timeout)
            return p.returncode, p.stdout.strip(), p.stderr.strip()
        except Exception as e:
            return 1, "", str(e)

    def set(self, **kw):
        with self.lock:
            self.state.update(kw)

    def public_state(self):
        with self.lock:
            st = {k: v for k, v in self.state.items() if k not in ("networks", "postcode", "setup_at")}
            at = self.state["setup_at"]
        st["setup_in_s"] = max(0, round(at - time.time())) if at and st["mode"] in ("checking", "offline") else None
        return st

    def active_ssid(self):
        """Name of the Wi-Fi network in use, or None (checked at most every 20 s)."""
        if time.time() - self._active["t"] > 20:
            code, out, _ = self.run("-t", "-f", "ACTIVE,SSID", "device", "wifi", timeout=10)
            ssid = None
            for line in out.splitlines() if code == 0 else []:
                parts = split_terse(line)
                if len(parts) >= 2 and parts[0] == "yes" and parts[1] and parts[1] != AP_NAME:
                    ssid = parts[1]
            self._active = {"ssid": ssid, "t": time.time()}
        return self._active["ssid"]

    def probe(self):
        """'full' if a check address gives its exact answer, 'portal' if something else answered
        instead (a sign-in page), 'none' if nothing answered."""
        answered = False
        for url, want_code, want_text in self.probes:
            try:
                u = urlsplit(url)
                conn = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=5)
                conn.request("GET", u.path or "/", headers={"User-Agent": "ALX-Departures", "Cache-Control": "no-cache"})
                r = conn.getresponse()
                body = r.read(2048).decode("utf-8", "replace")
                conn.close()
                answered = True
                if r.status == want_code and (not want_text or want_text in body):
                    return "full"
            except Exception:
                continue
        return "portal" if answered else "none"

    def connectivity(self):
        """'full', 'portal' (wants a sign-in page), 'limited' (joined, no internet) or 'none' (not joined)."""
        code, out, _ = self.run("networking", "connectivity", "check", timeout=15)
        nm = out.strip() if code == 0 else ""
        if nm == "portal":
            return "portal"
        if nm == "none":
            return "none"
        # NetworkManager on the Pi may not check properly by itself, so confirm with our own check.
        # A good answer is trusted for a minute, so this is one tiny request a minute when all is well.
        if self._probe["ok"] and time.time() - self._probe["t"] < 60:
            return "full"
        got = self.probe()
        self._probe = {"ok": got == "full", "t": time.time()}
        if got == "none" and nm in ("limited", "full", "unknown"):
            return "limited"
        return got

    def online(self):
        return self.connectivity() == "full"

    def joined_ssid(self):
        """The network the radio is joined to right now (fresh, not cached), or ''."""
        code, out, _ = self.run("-t", "-f", "ACTIVE,SSID", "device", "wifi", timeout=10)
        for line in out.splitlines() if code == 0 else []:
            parts = split_terse(line)
            if len(parts) >= 2 and parts[0] == "yes" and parts[1] and parts[1] != AP_NAME:
                return parts[1]
        return ""

    def saved_networks(self):
        code, out, _ = self.run("-t", "-f", "NAME,TYPE", "connection", "show")
        if code:
            return []
        nets = []
        for line in out.splitlines():
            parts = split_terse(line)
            if len(parts) >= 2 and parts[1] == "802-11-wireless" and parts[0] != AP_NAME:
                nets.append(parts[0])
        return nets

    def saved_ssids(self):
        """The network names (not just profile names) of the saved networks."""
        names = []
        for name in self.saved_networks():
            code, out, _ = self.run("-g", "802-11-wireless.ssid", "connection", "show", "id", name, timeout=10)
            names.append(out.strip() if code == 0 and out.strip() else name)
        return names

    def saved_in_range(self):
        """Saved networks that can be seen right now; None if the radio couldn't look."""
        saved = self.saved_ssids()
        if not saved:
            return []
        found = self.scan(rescan="auto")
        if found is None:
            return None
        here = {n["ssid"] for n in found}
        return [n for n in saved if n in here]

    def scan(self, rescan="yes"):
        code, out, _ = self.run("-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list", "--rescan", rescan, timeout=30)
        if code:
            return None
        best = {}
        for line in out.splitlines():
            parts = split_terse(line)
            if len(parts) < 3 or not parts[0] or parts[0] == AP_NAME:
                continue
            ssid, sig, sec = parts[0], int(parts[1] or 0), parts[2]
            if ssid not in best or sig > best[ssid]["signal"]:
                best[ssid] = {"ssid": ssid, "signal": sig, "secure": bool(sec and sec != "--")}
        return sorted(best.values(), key=lambda n: -n["signal"])

    # ---------- hotspot ----------
    def start_hotspot(self):
        try:                                     # make every web address lead to the setup page
            if os.path.isdir(os.path.dirname(CAPTIVE_CONF)) and not os.path.exists(CAPTIVE_CONF):
                with open(CAPTIVE_CONF, "w") as f:
                    f.write(f"address=/#/{AP_ADDR}\n")
        except Exception:
            pass
        self.run("connection", "delete", AP_NAME)
        code, _, err = self.run("device", "wifi", "hotspot", "ifname", self.iface, "con-name", AP_NAME,
                                "ssid", AP_NAME, "password", self.state["ap_password"])
        if code:
            self.log(f"wifi: could not start hotspot: {err}")
        return code == 0

    def hotspot_up(self):
        code, out, _ = self.run("-t", "-f", "NAME", "connection", "show", "--active", timeout=10)
        return code == 0 and AP_NAME in [split_terse(l)[0] for l in out.splitlines()]

    def stop_hotspot(self):
        self.run("connection", "down", AP_NAME)
        self.run("connection", "delete", AP_NAME)

    def enter_setup(self, error=""):
        with self.radio:
            self.log("wifi: no working connection, opening setup network " + AP_NAME)
            nets = self.scan() or self.scan(rescan="no") or []   # scan first: the radio can't scan while it's a hotspot
            self.start_hotspot()
            self.start_portal()
            self.set(networks=nets, mode="setup", target="", error=error, setup_at=None, problem="", joined="")

    def leave_setup(self):
        self.stop_hotspot()
        self.stop_portal()
        self.set(mode="online", error="", target="", setup_at=None, problem="", joined="", looking_for=[])
        self.log("wifi: connected")

    # ---------- joining networks ----------
    def wait_online(self, seconds):
        """Wait for working internet. Returns 'full', or how it fell short ('portal', 'limited', 'none')."""
        end, got = time.time() + seconds, "none"
        while time.time() < end:
            got = self.connectivity()
            if got == "full":
                return got
            time.sleep(2)
        return got

    @staticmethod
    def why_not(ssid, got, nm_error=""):
        name = ssid.upper()
        if got == "portal":
            return (f"{name} WANTS A SIGN-IN PAGE (LIKE WORK OR HOTEL GUEST WI-FI), WHICH THE BOARD CAN'T OPEN. "
                    "PLEASE PICK ANOTHER NETWORK, OR USE A PHONE HOTSPOT.")
        if got == "limited":
            return f"JOINED {name}, BUT IT HAS NO INTERNET. PLEASE PICK ANOTHER NETWORK."
        if "no network with ssid" in nm_error.lower() or "not found" in nm_error.lower():
            return f"COULDN'T FIND {name}. CHECK THE NAME, AND THAT IT'S IN RANGE."
        return f"COULDN'T JOIN {name}. CHECK THE PASSWORD AND TRY AGAIN."

    def connect(self, ssid, password, pc=""):
        """Called from the setup page. Runs in its own thread."""
        with self.radio:
            self.set(mode="connecting", target=ssid, error="", postcode=pc)
            self.log(f"wifi: trying {ssid}")
            self.stop_hotspot()
            args = ["device", "wifi", "connect", ssid] + (["password", password] if password else []) + ["ifname", self.iface]
            code, _, err = self.run(*args, timeout=60)
            got = self.wait_online(30) if code == 0 else "none"
            if got == "full":
                self._active = {"ssid": ssid, "t": time.time()}
                if self.on_joined and pc:
                    try:
                        self.on_joined(ssid, pc)
                    except Exception as e:
                        self.log(f"wifi: could not save postcode: {e}")
                return self.leave_setup()
            self.log(f"wifi: joining {ssid} failed ({got}): {err}")
            self.run("connection", "delete", "id", ssid)   # don't keep a profile that doesn't work
            nets = self.scan()
            self.set(networks=nets or self.state["networks"], mode="setup", error=self.why_not(ssid, got, err))
            self.start_hotspot()

    def retry_saved(self):
        with self.radio:
            saved = self.saved_networks()
            if not saved:
                return
            self.log("wifi: retrying saved networks")
            self.stop_hotspot()
            for name in saved:
                code, _, _ = self.run("connection", "up", "id", name, timeout=40)
                if code == 0 and self.wait_online(20) == "full":
                    return self.leave_setup()
            self.set(networks=self.scan() or self.state["networks"])
            self.start_hotspot()

    # ---------- main loop ----------
    def check_offline(self, since, got, look):
        """Not online: decide how long to wait before opening setup. Returns (when setup opens, message for it)."""
        joined = self.joined_ssid() if got in ("portal", "limited") else ""
        if joined:                         # on a network, but it wants a sign-in page or has no internet
            self.set(joined=joined, problem="signin" if got == "portal" else "nointernet", looking_for=[joined])
            return since + self.grace_signin, self.why_not(joined, got)
        self.set(joined="", problem="")
        if look is None:                   # couldn't look: assume the saved network may be about to appear
            return since + self.grace_known, ""
        self.set(looking_for=look)
        return since + (self.grace_known if look else self.grace_new), ""

    def loop(self):
        offline_since, last_retry, misses = None, time.time(), 0
        look, looked = None, 0.0
        while True:
            try:
                mode = self.state["mode"]
                if mode in ("checking", "online", "offline"):
                    got = self.connectivity()
                    if got == "full":
                        offline_since, misses, looked = None, 0, 0.0
                        if mode != "online":
                            self.set(mode="online", error="", setup_at=None, problem="", joined="", looking_for=[])
                            self.log("wifi: online")
                    else:
                        misses += 1
                        # One missed check while online is ignored (a blip); two in a row means offline
                        if mode == "online" and misses < 2:
                            pass
                        else:
                            offline_since = offline_since or time.time()
                            if time.time() - looked > 30:          # look for the saved networks every 30 s
                                look, looked = self.saved_in_range(), time.time()
                            at, why = self.check_offline(offline_since, got, look)
                            if mode != "offline":
                                self.set(mode="offline")
                            self.set(setup_at=at)
                            if time.time() >= at:
                                self.enter_setup(why)
                                last_retry, offline_since, misses = time.time(), None, 0
                elif mode == "setup":
                    busy = time.time() - self.portal_hit < self.busy_s
                    # Don't pull the setup network from under someone using it; but a phone that just sits
                    # on ALX-Setup can only delay the retry by 10 minutes, so home Wi-Fi is always found again.
                    overdue = time.time() - last_retry > self.retry_s + 600
                    if time.time() - last_retry > self.retry_s and (not busy or overdue):
                        last_retry = time.time()
                        self.retry_saved()
                    elif not busy and not self.hotspot_up():
                        with self.radio:                   # the setup network dropped: bring it back
                            if self.state["mode"] == "setup":
                                self.log("wifi: setup network wasn't up, restarting it")
                                self.start_hotspot()
                                self.start_portal()
            except Exception as e:
                self.log(f"wifi: {e}")
            time.sleep(5)

    def start(self):
        threading.Thread(target=self.loop, daemon=True).start()

    # ---------- setup page for the phone ----------
    def start_portal(self):
        if self.portal:
            return
        mgr = self

        class Portal(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def page(self, body, code=200):
                data = body.encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                mgr.portal_hit = time.time()
                if self.path.startswith("/status"):
                    data = json.dumps(mgr.public_state()).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    return self.wfile.write(data)
                # Any other address (including phones' captive-portal checks) gets the setup page
                self.page(mgr.portal_html())

            def do_POST(self):
                mgr.portal_hit = time.time()
                n = int(self.headers.get("Content-Length") or 0)
                form = parse_qs(self.rfile.read(n).decode("utf-8", "replace"))
                ssid = ((form.get("other") or [""])[0].strip() or (form.get("ssid") or [""])[0]).strip()
                pw = (form.get("password") or [""])[0]
                raw_pc = (form.get("postcode") or [""])[0]
                if not ssid:
                    return self.page(mgr.portal_html("Pick a network first.", raw_pc))
                pc, _, pc_err = postcode.normalise(raw_pc)
                if pc_err:   # no postcode, no connecting
                    return self.page(mgr.portal_html(pc_err, raw_pc))
                threading.Thread(target=mgr.connect, args=(ssid, pw, pc), daemon=True).start()
                self.page(mgr.done_html(ssid))

        try:
            self.portal = ThreadingHTTPServer(("", self.portal_port), Portal)
            threading.Thread(target=self.portal.serve_forever, daemon=True).start()
        except Exception as e:
            self.log(f"wifi: setup page could not start on port {self.portal_port}: {e}")
            self.portal = None

    def stop_portal(self):
        if self.portal:
            srv, self.portal = self.portal, None
            threading.Thread(target=srv.shutdown, daemon=True).start()

    STYLE = """<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{margin:0;background:#0b0b0b;color:#e9e4d8;font:16px/1.4 system-ui,sans-serif;padding:24px}
h1{font-size:15px;letter-spacing:.25em;color:#ffc53d;margin:0 0 4px;font-weight:600}
h2{font-size:24px;margin:0 0 18px;font-weight:600}
label{display:flex;align-items:center;gap:10px;padding:12px 14px;margin:0 0 8px;background:#1a1a1a;border-radius:10px;font-size:17px}
input[type=radio]{width:20px;height:20px;accent-color:#ffc53d}
input[type=text],input[type=password]{width:100%;box-sizing:border-box;padding:14px;font-size:17px;border-radius:10px;border:1px solid #333;background:#141414;color:#fff;margin:6px 0 14px}
button{width:100%;padding:15px;font-size:17px;font-weight:600;border:0;border-radius:10px;background:#ffc53d;color:#111}
.sig{margin-left:auto;color:#8f8f8f;font-size:13px}.err{background:#3a1410;color:#ffb3a8;padding:12px 14px;border-radius:10px;margin:0 0 16px}
small{color:#8f8f8f}.why{margin:-6px 0 16px}</style>"""

    def portal_html(self, err="", pc=None):
        with self.lock:
            nets, error = list(self.state["networks"]), err or self.state["error"]
            pc = self.state["postcode"] if pc is None else pc
        rows = "".join(
            f'<label><input type="radio" name="ssid" value="{html.escape(n["ssid"], True)}"{" checked" if i == 0 else ""}>'
            f'{html.escape(n["ssid"])}<span class="sig">{"🔒 " if n["secure"] else ""}{n["signal"]}%</span></label>'
            for i, n in enumerate(nets[:15]))
        return f"""<!doctype html><html><head><meta charset="utf-8"><title>ALX Wi-Fi setup</title>{self.STYLE}</head><body>
<h1>HOWE INTERNATIONAL</h1><h2>Connect to Wi-Fi</h2>
{f'<div class="err">{html.escape(error.capitalize() if error.isupper() else error)}</div>' if error else ''}
<form method="post" action="/connect">
{rows or '<p><small>No networks found. Type the name below.</small></p>'}
<small>Not listed? Type the network name:</small>
<input type="text" name="other" autocomplete="off" autocapitalize="none" placeholder="Network name (optional)">
<small>Wi-Fi password</small>
<input type="password" name="password" autocomplete="current-password" placeholder="Password">
<small>Postcode where the board lives</small>
<input type="text" name="postcode" required maxlength="10" autocomplete="postal-code" autocapitalize="characters"
 placeholder="e.g. SG5 1AA" value="{html.escape(pc or '', True)}">
<p class="why"><small>Needed for every new Wi-Fi, so the radar is centred on home. Only used to find the planes overhead.</small></p>
<button type="submit">Connect</button></form></body></html>"""

    def done_html(self, ssid):
        return f"""<!doctype html><html><head><meta charset="utf-8"><title>Connecting…</title>{self.STYLE}</head><body>
<h1>HOWE INTERNATIONAL</h1><h2>Connecting to {html.escape(ssid)}…</h2>
<p>Your phone will now disconnect from ALX-Setup. That's expected.</p>
<p>Watch the board: within a minute it will switch to live flights. If the password was wrong,
the setup screen comes back and you can try again.</p></body></html>"""
