# Remote updates

Once the board is at Alex's, you can still fix things or add features. You publish a release on GitHub. The board checks at 03:30 every night, tests the new version, switches to it, and switches back by itself if anything goes wrong.

## Set up (once, before installing on the Pi)

1. **Make a GitHub repo** for the code, e.g. `alx-board`, with the *contents* of the `alx` folder at its root. `.gitignore` already keeps `cache/` and `config.json` out.
   - **Public repo (simplest, recommended).** No token needed, so nothing can expire. There's nothing secret in the code; Alex's settings, postcode and the CARTO key stay on the Pi in `config.json`, which is never in the repo.
   - **Private repo.** Make a fine-grained personal access token: *Repository access: only `alx-board`*, *Permissions → Contents: Read-only*. Note its expiry date: when it expires, updates stop (the board keeps working normally) until you put a new token on it.
2. **The board already knows where to look:** `henewi/alx-board` is built into `pi/alxctl.py`. To use a different repo, or turn updates off, set `"update_repo"` in `/opt/alx/data/config.json` on the Pi.
3. **Turn on two-factor sign-in for your GitHub account.** Whoever controls the repo controls what runs on the board.

## Sending an update

1. Change the code, test it on your laptop (`python3 server.py`), commit and push.
2. On GitHub: **Releases → Draft a new release → Choose a tag**. Type a new tag, e.g. `v1.1`, then **Publish release**. Only published releases are installed, not every push.
3. That night at 03:30 the board installs it. To install straight away when you have SSH access to the Pi: `sudo alxctl update`.

Tags must be new each time. A tag that failed once is never retried, so fix the problem and publish `v1.2`.

## What the board does with a new release

1. **Downloads** the release and unpacks it into its own folder. Anything that tries to write outside that folder is refused.
2. **Checks it before touching anything:** all the main files are there, every Python file compiles, and a test copy starts on a spare port and serves the board page and data. If any check fails, the release is skipped and the board carries on with the version it has.
3. **Switches** to the new version and restarts the data service. It waits for the service to report the new version.
4. **Restarts the screen** and watches it. The new page must keep drawing fresh updates. A page with a broken script or a frozen screen fails this.
5. **If step 3 or 4 fails,** it switches straight back to the previous version and restarts. The screen is back within a minute, and that release is marked bad.
6. **If it passes,** it keeps the previous version for `sudo alxctl rollback`, tidies older ones away, and updates its own copy of `alxctl`.

Alex's data in `/opt/alx/data` (logbook, stats, style, postcodes, `config.json`) is never touched by any of this.

## What can't be changed remotely

- **The service files** in `pi/systemd/`. Changes there need `sudo bash pi/install.sh` run on the Pi again.
- **Anything in `config.json`** on the Pi.

Both need SSH, so keep these changes rare.
