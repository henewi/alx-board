"""
Wi-Fi setup for ALX Departures (Raspberry Pi OS, which uses NetworkManager).

How it behaves:
  * Connected and working: does nothing.
  * No Wi-Fi saved yet (first ever start-up): after a short wait it opens its own
    Wi-Fi network, "ALX-Setup". The board shows a QR code to join it; a setup page
    opens on the phone; pick the home Wi-Fi, type the password, done.
  * Saved Wi-Fi stops working (router off, moved house): it waits a few minutes in
    case it comes back, then opens setup. While in setup it keeps retrying the saved
    networks every few minutes, so it reconnects by itself if the router returns.
NetworkManager remembers the network, so setup never appears again until needed.

Every new network needs a postcode as well, so the radar is centred on the right place.
The setup page won't connect without one, and it's remembered per network.

Standard library only. Needs to run as root on the Pi (to control Wi-Fi and serve
the setup page on port 80).
"""

import html
import json
import os
import random
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

import postcode

AP_NAME = "ALX-Setup"
AP_ADDR = "10.42.0.1"                      # NetworkManager's address for a shared hotspot
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
        self.grace_new = cfg.get("wifi_grace_new_s", 45)       # nothing saved yet: wait this long
        self.grace_known = cfg.get("wifi_grace_known_s", 180)  # saved network down: wait this long
        self.retry_s = cfg.get("wifi_retry_s", 300)            # in setup: retry saved networks this often
        self.portal_port = cfg.get("wifi_portal_port", 80)
        self.lock = threading.Lock()
        self.portal = None
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
                      "portal": f"http://{AP_ADDR}", "target": "", "error": "", "networks": [], "postcode": ""}

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
            return {k: v for k, v in self.state.items() if k not in ("networks", "postcode")}

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

    def online(self):
        code, out, _ = self.run("networking", "connectivity", "check", timeout=15)
        if code == 0 and out:
            return out.strip() == "full"
        try:                                    # fallback if NetworkManager can't say
            socket.create_connection(("1.1.1.1", 53), timeout=3).close()
            return True
        except OSError:
            return False

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

    def scan(self):
        code, out, _ = self.run("-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list", "--rescan", "yes", timeout=30)
        best = {}
        for line in out.splitlines() if code == 0 else []:
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

    def stop_hotspot(self):
        self.run("connection", "down", AP_NAME)
        self.run("connection", "delete", AP_NAME)

    def enter_setup(self):
        self.log("wifi: no working connection, opening setup network " + AP_NAME)
        nets = self.scan()                       # scan first: the radio can't scan while it's a hotspot
        self.set(networks=nets, mode="setup", target="")
        self.start_hotspot()
        self.start_portal()

    def leave_setup(self):
        self.stop_hotspot()
        self.stop_portal()
        self.set(mode="online", error="", target="")
        self.log("wifi: connected")

    # ---------- joining networks ----------
    def wait_online(self, seconds):
        end = time.time() + seconds
        while time.time() < end:
            if self.online():
                return True
            time.sleep(2)
        return False

    def connect(self, ssid, password, pc=""):
        """Called from the setup page. Runs in its own thread."""
        self.set(mode="connecting", target=ssid, error="", postcode=pc)
        self.log(f"wifi: trying {ssid}")
        self.stop_hotspot()
        args = ["device", "wifi", "connect", ssid] + (["password", password] if password else []) + ["ifname", self.iface]
        code, _, err = self.run(*args, timeout=60)
        if code == 0 and self.wait_online(30):
            self._active = {"ssid": ssid, "t": time.time()}
            if self.on_joined and pc:
                try:
                    self.on_joined(ssid, pc)
                except Exception as e:
                    self.log(f"wifi: could not save postcode: {e}")
            return self.leave_setup()
        self.log(f"wifi: joining {ssid} failed: {err}")
        self.run("connection", "delete", "id", ssid)   # don't keep a profile with a wrong password
        nets = self.scan()
        self.set(networks=nets or self.state["networks"], mode="setup",
                 error=f"COULDN'T JOIN {ssid.upper()}. CHECK THE PASSWORD AND TRY AGAIN.")
        self.start_hotspot()

    def retry_saved(self):
        saved = self.saved_networks()
        if not saved:
            return
        self.log("wifi: retrying saved networks")
        self.stop_hotspot()
        for name in saved:
            code, _, _ = self.run("connection", "up", "id", name, timeout=40)
            if code == 0 and self.wait_online(20):
                return self.leave_setup()
        self.set(networks=self.scan() or self.state["networks"])
        self.start_hotspot()

    # ---------- main loop ----------
    def loop(self):
        offline_since, last_retry = None, time.time()
        while True:
            try:
                mode = self.state["mode"]
                if mode in ("checking", "online", "offline"):
                    if self.online():
                        offline_since = None
                        if mode != "online":
                            self.set(mode="online", error="")
                    else:
                        offline_since = offline_since or time.time()
                        grace = self.grace_known if self.saved_networks() else self.grace_new
                        if mode == "online":
                            self.set(mode="offline")
                        if time.time() - offline_since > grace:
                            self.enter_setup()
                            last_retry = time.time()
                elif mode == "setup" and time.time() - last_retry > self.retry_s:
                    last_retry = time.time()
                    self.retry_saved()
                    if self.state["mode"] == "online":
                        offline_since = None
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
                if self.path.startswith("/status"):
                    data = json.dumps(mgr.public_state()).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    return self.wfile.write(data)
                # Any other address (including phones' captive-portal checks) gets the setup page
                self.page(mgr.portal_html())

            def do_POST(self):
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
<h1>ALEX INTERNATIONAL</h1><h2>Connect to Wi-Fi</h2>
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
<h1>ALEX INTERNATIONAL</h1><h2>Connecting to {html.escape(ssid)}…</h2>
<p>Your phone will now disconnect from ALX-Setup. That's expected.</p>
<p>Watch the board: within a minute it will switch to live flights. If the password was wrong,
the setup screen comes back and you can try again.</p></body></html>"""
