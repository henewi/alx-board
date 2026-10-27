#!/usr/bin/env python3
"""
alxctl - looks after ALX Departures on the Pi. Standard library only.

    alxctl watchdog        every minute (timer): restarts the screen if it has frozen
    alxctl nightly         03:30 every night (timer): installs any update, then quietly restarts
    alxctl update          check GitHub for a new release and install it (rolls back if it misbehaves)
    alxctl rollback        go back to the previous version
    alxctl status          what's running, version, health
    alxctl wait-server     wait (up to a minute) for the data service; used before the screen opens

Nothing here touches Alex's data (logbook, stats, settings, postcodes). That lives in
/opt/alx/data and is never replaced by an update or a restart.

Layout:
    /opt/alx/releases/<version>/   the code of each installed version
    /opt/alx/current               -> the version in use
    /opt/alx/data/config.json      settings (update_repo, update_token, ...)
    /opt/alx/data/cache/           logbook, stats, settings, map tiles
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request

ROOT = os.environ.get("ALX_ROOT", "/opt/alx")
SYSTEMCTL = os.environ.get("ALX_SYSTEMCTL", "systemctl")
PYTHON = sys.executable or "/usr/bin/python3"
SERVER, KIOSK = "alx", "alx-kiosk"
DATA = os.path.join(ROOT, "data")
RELEASES = os.path.join(ROOT, "releases")
CURRENT = os.path.join(ROOT, "current")
STATE_FILE = os.path.join(DATA, "alxctl.json")
REQUIRED = ["server.py", "wifi.py", "settings_page.py", "postcode.py", "web/index.html"]
DEFAULT_REPO = "henewi/alx-board"                     # where updates come from (GitHub releases)
SCALE = float(os.environ.get("ALX_TIME_SCALE", "1"))   # tests only: shortens the waits
GRACE = float(os.environ.get("ALX_WD_GRACE", "240"))  # after a start or restart, give the screen this long
STALE = float(os.environ.get("ALX_WD_STALE", "180"))  # no fresh drawing for this long = frozen


def log(msg):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), msg, flush=True)


def wait(seconds):
    time.sleep(seconds * SCALE)


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def config():
    return load(os.path.join(DATA, "config.json"), {})


def port():
    return int(config().get("port", 8080))


def systemctl(*args):
    log("systemctl " + " ".join(args))
    return subprocess.run([SYSTEMCTL, *args], capture_output=True, text=True, timeout=120).returncode


def health(p=None, timeout=5):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{p or port()}/api/health", timeout=timeout) as r:
            return json.load(r)
    except Exception:
        return None


def current_version():
    try:
        with open(os.path.join(CURRENT, "VERSION")) as f:
            return f.read().strip()
    except OSError:
        return os.path.basename(os.path.realpath(CURRENT))


# ---------- waiting for things to come back ----------

def server_back(version=None, seconds=90):
    end = time.time() + seconds * SCALE
    while time.time() < end:
        h = health()
        if h and h.get("poller_age_s", 999) < 60 and (version is None or h.get("version") == version):
            return True
        wait(3)
    return False


def screen_back(seconds=150):
    """The new screen is fine when its count of drawn updates keeps going up (it checks in every 5 s).
    A fresh page counts from 0, so a drop means the new page has started; a page whose script is
    broken never manages to count up, and a frozen one stops."""
    wait(5)
    end, seen = time.time() + seconds * SCALE, []
    while time.time() < end:
        r = (health() or {}).get("kiosk_draws")
        if r is not None:
            if seen and r < seen[-1]:
                seen = [r]
            elif not seen or r > seen[-1]:
                seen.append(r)
        if len(seen) >= 4:
            return True
        wait(5)
    return False


def restart_all(reason):
    """Server first (so the screen has data the moment it opens), then the screen. A few seconds of blank screen."""
    log(f"restarting ({reason})")
    systemctl("restart", SERVER)
    server_back(seconds=60)
    systemctl("restart", KIOSK)


# ---------- watchdog ----------

def cmd_watchdog():
    st = load(STATE_FILE, {})
    h = health()
    if h is None:
        return   # the server itself is looked after by systemd (Restart=always + WatchdogSec)
    now = time.time()
    if h.get("uptime_s", 0) < GRACE or now - st.get("kiosk_restart", 0) < GRACE:
        return   # still starting up
    age = h.get("kiosk_drawn_age_s")
    if age is not None and age < STALE:
        return
    recent = [t for t in st.get("kiosk_restarts", []) if now - t < 3600]
    if len(recent) >= 3 and now - st.get("reboot", 0) > 6 * 3600:
        log("watchdog: screen keeps freezing, rebooting")
        st["reboot"] = now
        save(STATE_FILE, st)
        systemctl("reboot")
        return
    log(f"watchdog: screen hasn't drawn anything for {age if age is not None else 'ever'} s, restarting it")
    st["kiosk_restart"] = now
    st["kiosk_restarts"] = recent + [now]
    save(STATE_FILE, st)
    systemctl("restart", KIOSK)


# ---------- updates ----------

def github(url, token, binary=False, limit=60 * 1024 * 1024):
    headers = {"User-Agent": "ALX-Departures-updater", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
        data = r.read(limit + 1)
    if len(data) > limit:
        raise ValueError("download too large")
    return data if binary else json.loads(data.decode("utf-8"))


def safe_extract(tar_bytes, dest):
    """Unpack, refusing anything that could write outside the folder (links, absolute paths, '..')."""
    with tempfile.TemporaryFile() as f:
        f.write(tar_bytes)
        f.seek(0)
        with tarfile.open(fileobj=f, mode="r:gz") as tar:
            for m in tar.getmembers():
                name = m.name.lstrip("./")
                if m.issym() or m.islnk() or m.isdev() or m.name.startswith("/") or ".." in m.name.split("/"):
                    raise ValueError(f"unsafe file in download: {m.name}")
                if not (m.isfile() or m.isdir()):
                    continue
                target = os.path.join(dest, name)
                if m.isdir():
                    os.makedirs(target, exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with tar.extractfile(m) as src, open(target, "wb") as out:
                        shutil.copyfileobj(src, out)
                    os.chmod(target, 0o755 if m.mode & 0o111 else 0o644)


def find_app(folder):
    """The release can have the app at its root or in an 'alx' folder."""
    for dirpath, dirs, files in os.walk(folder):
        if "server.py" in files and os.path.isdir(os.path.join(dirpath, "web")):
            return dirpath
        if dirpath[len(folder):].count(os.sep) >= 3:
            dirs[:] = []
    return None


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def check_release(app):
    """Before switching: every file present, every Python file compiles, and it starts and serves pages."""
    for rel in REQUIRED:
        if not os.path.isfile(os.path.join(app, rel)):
            raise ValueError(f"missing {rel}")
    for dirpath, _, files in os.walk(app):
        for fn in files:
            if fn.endswith(".py"):
                path = os.path.join(dirpath, fn)
                with open(path, encoding="utf-8") as f:
                    compile(f.read(), path, "exec")
    with tempfile.TemporaryDirectory() as tmp:
        cfg = dict(config())
        p = free_port()
        cfg.update(port=p, host="127.0.0.1", wifi_manage=False, cache_dir=os.path.join(tmp, "cache"),
                   flight_urls=[], geo_urls=[], lat=51.5, lon=-0.1)
        with open(os.path.join(tmp, "config.json"), "w") as f:
            json.dump(cfg, f)
        env = {k: v for k, v in os.environ.items() if k != "NOTIFY_SOCKET"}
        env["ALX_CONFIG"] = os.path.join(tmp, "config.json")
        proc = subprocess.Popen([PYTHON, os.path.join(app, "server.py")], cwd=app, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            ok = False
            for _ in range(40):
                time.sleep(0.5)
                if proc.poll() is not None:
                    break
                if health(p, 2):
                    with urllib.request.urlopen(f"http://127.0.0.1:{p}/", timeout=5) as r:
                        page = r.read().decode("utf-8", "replace")
                    with urllib.request.urlopen(f"http://127.0.0.1:{p}/api/state", timeout=5) as r:
                        state = json.load(r)
                    ok = "<html" in page.lower() and "aircraft" in state
                    break
        finally:
            proc.terminate()
            try:
                out = proc.communicate(timeout=10)[0].decode("utf-8", "replace")
            except Exception:
                proc.kill()
                out = ""
        if not ok:
            raise ValueError("test start failed: " + out.strip()[-400:])


def switch_to(target):
    tmp = CURRENT + ".new"
    if os.path.lexists(tmp):
        os.remove(tmp)
    os.symlink(target, tmp)
    os.replace(tmp, CURRENT)


def install_tools(app):
    """A version that has proved itself also brings its own copy of this tool."""
    src = os.path.join(app, "pi", "alxctl.py")
    if os.path.isfile(src):
        dst = os.path.join(ROOT, "bin", "alxctl")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst + ".new")
        os.chmod(dst + ".new", 0o755)
        os.replace(dst + ".new", dst)


def prune(keep):
    for name in os.listdir(RELEASES):
        path = os.path.join(RELEASES, name)
        if os.path.realpath(path) not in keep and os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)


def cmd_update():
    cfg, st = config(), load(STATE_FILE, {})
    repo = cfg.get("update_repo", DEFAULT_REPO)       # set "update_repo": "" in config.json to turn updates off
    if not repo:
        log("remote updates not set up (add update_repo to config.json)")
        return False
    api = cfg.get("update_api", "https://api.github.com").rstrip("/")
    token = cfg.get("update_token") or ""
    try:
        rel = github(f"{api}/repos/{repo}/releases/latest", token)
    except urllib.error.HTTPError as e:
        log(f"update check: GitHub said {e.code} ({'no releases yet, or the token can' + chr(39) + 't see the repo' if e.code == 404 else e.reason})")
        return False
    except Exception as e:
        log(f"update check failed (offline?): {e}")
        return False
    tag = str(rel.get("tag_name") or "").strip()
    if not tag or "/" in tag or tag.startswith("."):
        log("update check: release has no usable tag")
        return False
    if tag == current_version():
        log(f"up to date ({tag})")
        return False
    if tag in st.get("bad", []):
        log(f"{tag} failed before, skipping it. Publish a new release to try again.")
        return False
    log(f"new version {tag} (running {current_version()})")

    os.makedirs(RELEASES, exist_ok=True)
    incoming = tempfile.mkdtemp(prefix=".incoming-", dir=RELEASES)
    try:
        safe_extract(github(rel["tarball_url"], token, binary=True), incoming)
        app = find_app(incoming)
        if not app:
            raise ValueError("no server.py and web/ folder in the release")
        check_release(app)
        dest = os.path.join(RELEASES, tag)
        if os.path.exists(dest):
            shutil.rmtree(dest)
        os.replace(app, dest)
        with open(os.path.join(dest, "VERSION"), "w") as f:
            f.write(tag + "\n")
    except Exception as e:
        log(f"{tag} rejected before installing: {e}")
        st.setdefault("bad", []).append(tag)
        save(STATE_FILE, st)
        return False
    finally:
        shutil.rmtree(incoming, ignore_errors=True)

    previous = os.path.realpath(CURRENT)
    switch_to(dest)
    log(f"switched to {tag}, restarting")
    systemctl("restart", SERVER)
    ok = server_back(tag)
    if ok:
        systemctl("restart", KIOSK)
        ok = screen_back()
    if not ok:
        log(f"{tag} didn't come up properly, going back to {os.path.basename(previous)}")
        switch_to(previous)
        st.setdefault("bad", []).append(tag)
        save(STATE_FILE, st)
        restart_all("rollback")
        shutil.rmtree(dest, ignore_errors=True)
        return False
    st.update(previous=previous, updated=time.strftime("%Y-%m-%d %H:%M"), version=tag)
    save(STATE_FILE, st)
    install_tools(dest)
    prune({os.path.realpath(dest), previous})
    log(f"now running {tag}")
    return True


def cmd_rollback():
    st = load(STATE_FILE, {})
    prev = st.get("previous")
    if not prev or not os.path.isdir(prev):
        log("no previous version to go back to")
        return
    bad = current_version()
    switch_to(prev)
    st.setdefault("bad", []).append(bad)
    st["previous"] = None
    save(STATE_FILE, st)
    restart_all(f"rolled back from {bad}")


def cmd_nightly():
    if not cmd_update():
        restart_all("nightly")


def cmd_status():
    print(json.dumps({"version": current_version(), "health": health(), "state": load(STATE_FILE, {})}, indent=1))


def main(argv):
    os.makedirs(DATA, exist_ok=True)
    cmd = argv[1] if len(argv) > 1 else "status"
    if cmd == "watchdog":
        cmd_watchdog()
    elif cmd == "nightly":
        cmd_nightly()
    elif cmd == "update":
        cmd_update()
    elif cmd == "wait-server":       # used before opening the screen at start-up
        server_back(seconds=60)
    elif cmd == "rollback":
        cmd_rollback()
    else:
        cmd_status()


if __name__ == "__main__":
    main(sys.argv)
