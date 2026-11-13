"""
Phone settings page for ALX Departures: the board's postcode, and the board style.

Every style uses exactly the same layout, so the physical faceplate always lines up.
A style only changes colours and fonts.
"""

import html
import json

# id, name, one-line description, preview colours (board, flap, letters, accent, radar, radar lines)
THEMES = [
    ("solari", "Solari", "Classic amber split-flaps, green radar", ("#090909", "#272727", "#ffc53d", "#ffc53d", "#0f2a1d", "#7dffb0")),
    ("terminal", "Terminal", "Modern UK airport screens: navy bands, white and yellow", ("#081a35", "#0f2c58", "#ffffff", "#ffd400", "#0d2a52", "#6fb6ff")),
    ("cockpit", "Cockpit", "Airbus glass cockpit: green, cyan and magenta on black", ("#03060a", "#05090d", "#3dff6a", "#3ee8ff", "#02070b", "#e8f0f6")),
    ("crt", "CRT", "Green phosphor terminal with scanlines", ("#010d04", "#03200b", "#7dff9b", "#7dff9b", "#0f2a1d", "#7dffb0")),
    ("sage", "Sage", "Calm: soft green and oat, rounded tiles, a peach accent", ("#2d3830", "#3d4c41", "#f1ead8", "#e5ab88", "#3f4f43", "#cfe0c4")),
    ("dusk", "Dusk", "Twilight lavender, an apricot sunset and the first stars", ("#2a2648", "#322e52", "#f6eef8", "#f6b38e", "#3b3160", "#cbbcf2")),
    ("sandstone", "Sandstone", "Warm sand, terracotta tiles and olive", ("#e8d8bf", "#ad4e30", "#fbf3e4", "#a8492c", "#f2e6d0", "#7a4b2c")),
    ("paper", "Paper", "Printed timetable: typewriter letters and red ink", ("#ece8de", "#fdfcf8", "#151515", "#c8102e", "#f7f4ec", "#5a564d")),
    ("renaissance", "Renaissance", "Illuminated manuscript: vellum, red and gold, an astrolabe radar", ("#efe2c4", "#e4d3ae", "#3a2414", "#9e2a1a", "#f5ebd3", "#8a6a34")),
    ("wavepunk", "Wavepunk", "Synthwave neon, chrome and a grid horizon", ("#1a0436", "#16022f", "#5ff8ff", "#ff2fd6", "#3a0d5c", "#ff2fd6")),
    ("blueprint", "Blueprint", "An engineering drawing: white line-work on blue", ("#0f4277", "#0f4277", "#ffffff", "#bfe6ff", "#104680", "#ffffff")),
    ("bosnia", "Bosnia", "The flag: royal blue, yellow and a ring of white stars", ("#00268f", "#0b2d93", "#ffffff", "#fecb00", "#0b2f9c", "#fecb00")),
    ("sunflower", "Sunflower", "Her favourite: yellow, with a sunflower radar", ("#f3bd12", "#221d14", "#ffd23f", "#f3bd12", "#2b2412", "#ffd23f")),
    ("disco", "Disco", "A mirrorball radar, a lit dance floor and glitter gold", ("#1a0a2c", "#3a2a58", "#ffe7a1", "#ff4fd8", "#8d86a8", "#ffcf4a")),
    ("popart", "Pop Art", "A comic strip: halftone dots, black outlines and a POW radar", ("#33c3f0", "#ffffff", "#111111", "#e8132b", "#ffe14a", "#e8132b")),
    ("groovy", "Groovy", "The 1970s: orange, mustard and brown, rainbow stripes", ("#f6e7c6", "#f08a24", "#fff4dc", "#d1452e", "#fbecd0", "#d1452e")),
    ("candy", "Candy", "A sweet shop: pink, sprinkles and a doughnut radar", ("#ffd3e6", "#ffffff", "#ff4f9a", "#ff4f9a", "#ff9cc8", "#e9b277")),
    ("cosmos", "Cosmos", "Deep space: a nebula, stars and an orrery radar with planets", ("#0a0d24", "#1b2042", "#eef3ff", "#7fd4ff", "#151b3d", "#9fc4ff")),
    ("grandprix", "Grand Prix", "The pit wall: timing colours, kerbs, a chequered flag and a soft-tyre radar", ("#16171a", "#f2f2f2", "#111111", "#e8002d", "#2c2e34", "#e8002d")),
    ("pho", "Pho", "A noodle shop: red lacquer, gold signs, lanterns and a bowl of pho", ("#941c13", "#fff6de", "#a3170f", "#ffd54a", "#e39a3b", "#1f5fa8")),
]
THEME_IDS = [t[0] for t in THEMES]


def place_card(place):
    place = place or {}
    pc, city = place.get("postcode", ""), place.get("city", "")
    if place.get("missing"):
        now = f'<span class="bad">{html.escape(pc)} wasn\'t found. Please check it.</span>'
    elif pc:
        now = f'Centred on <b>{html.escape(city.title() or pc)}</b> ({html.escape(pc)})'
    elif city:
        now = f'Roughly <b>{html.escape(city.title())}</b>, from the internet connection. Add the postcode to centre it exactly.'
    else:
        now = "Not set yet."
    net = f' for the <b>{html.escape(place["network"])}</b> Wi-Fi' if place.get("network") else ""
    return f"""
<section class="loc" id="place">
  <h3>Board location</h3>
  <p class="now" id="placeNow">{now}</p>
  <form id="pcForm" autocomplete="off">
    <input id="pc" name="postcode" required maxlength="10" autocapitalize="characters" autocomplete="postal-code"
      placeholder="Postcode, e.g. SG5 1AA" value="{html.escape(pc, True)}">
    <button type="submit">Save</button>
  </form>
  <p class="hint">Saved{net}. Joining a different Wi-Fi asks for a new one.</p>
</section>"""


RANGES = (10, 15, 25)
RANGE_NOTES = {10: "Planes you can see and hear", 15: "A bit more traffic", 25: "Everything nearby, including high cruisers"}


def range_card(radius):
    btns = "".join(f'<button type="button" class="rg{" on" if int(radius) == r else ""}" data-r="{r}">{r}<small>miles</small></button>'
                   for r in RANGES)
    note = RANGE_NOTES.get(int(radius), "")
    return f"""
<h3>Radar range</h3>
<div class="ranges">{btns}</div>
<p class="hint" id="rgNote">{html.escape(note)}</p>"""


def page(current, name="Alex", place=None, version="", radius=10):
    cards = []
    for tid, label, desc, (bg, flap, ink, acc, rbg, rline) in THEMES:
        flaps = "".join(f'<i style="background:{flap};color:{ink}">{c}</i>' for c in "ALX")
        cards.append(f"""
<button class="card{' on' if tid == current else ''}" data-id="{tid}" style="--acc:{acc}">
  <span class="prev" style="background:{bg}">
    <span class="flaps">{flaps}</span>
    <span class="dial" style="background:radial-gradient(circle,{rbg},#000);border-color:{rline}"><b style="background:{rline}"></b></span>
  </span>
  <span class="txt"><b>{html.escape(label)}</b></span>
  <span class="tick">✓</span>
</button>""")
    json_notes = json.dumps({str(k): v for k, v in RANGE_NOTES.items()})
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>ALX · Board style</title>
<style>
body{{margin:0;background:#0b0b0b;color:#e9e4d8;font:16px/1.4 system-ui,sans-serif;padding:22px 18px 40px}}
h1{{font-size:13px;letter-spacing:.28em;color:#ffc53d;margin:0 0 4px;font-weight:600}}
h2{{font-size:26px;margin:0 0 6px;font-weight:600}}
p.sub{{margin:0 0 20px;color:#9a9a9a;font-size:14px}}
.card{{width:100%;display:flex;align-items:center;gap:14px;padding:12px;margin:0 0 10px;border-radius:14px;border:2px solid #222;
  background:#151515;color:inherit;font:inherit;text-align:left;cursor:pointer}}
.card.on{{border-color:var(--acc);background:#1b1b1b}}
.prev{{flex:none;width:112px;height:58px;border-radius:8px;display:flex;align-items:center;justify-content:space-between;padding:0 8px;box-sizing:border-box}}
.flaps{{display:flex;gap:2px}}.flaps i{{font:600 15px/24px system-ui;font-style:normal;width:15px;text-align:center;border-radius:2px}}
.dial{{width:38px;height:38px;border-radius:50%;border:1.5px solid;position:relative;opacity:.95}}
.dial b{{position:absolute;left:50%;top:50%;width:4px;height:4px;margin:-2px;border-radius:50%}}
.txt{{display:flex;flex-direction:column;gap:2px;flex:1}}.txt b{{font-size:18px}}.txt small{{color:#9a9a9a;font-size:13px}}
.tick{{flex:none;width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;
  color:#111;background:var(--acc);opacity:0}}.card.on .tick{{opacity:1}}
#toast{{position:fixed;left:18px;right:18px;bottom:20px;padding:14px;border-radius:12px;background:#ffc53d;color:#111;font-weight:600;
  text-align:center;transform:translateY(120px);transition:transform .25s}}#toast.show{{transform:none}}
.note{{margin-top:18px;color:#7a7a7a;font-size:13px}}
h3{{font-size:13px;letter-spacing:.2em;text-transform:uppercase;color:#9a9a9a;margin:22px 0 8px;font-weight:600}}
.loc{{background:#151515;border:2px solid #222;border-radius:14px;padding:4px 14px 12px}}
.loc h3{{margin-top:12px}}.now{{margin:0 0 10px;font-size:15px}}.bad{{color:#ff8a7a}}
#pcForm{{display:flex;gap:8px}}#pc{{flex:1;min-width:0;padding:12px;font-size:17px;border-radius:10px;border:1px solid #333;
  background:#0e0e0e;color:#fff;text-transform:uppercase}}
#pcForm button{{padding:0 18px;border:0;border-radius:10px;background:#ffc53d;color:#111;font:600 16px system-ui}}
.hint{{margin:8px 0 0;color:#7a7a7a;font-size:12px}}.ver{{color:#555;font-size:11px;text-align:center;margin-top:26px}}
#toast.err{{background:#ff6b5a}}
.ranges{{display:flex;gap:8px}}.rg{{flex:1;padding:12px 0 10px;border-radius:12px;border:2px solid #222;background:#151515;color:inherit;
  font:600 22px system-ui;display:flex;flex-direction:column;align-items:center;gap:2px;cursor:pointer}}
.rg small{{font:500 11px system-ui;color:#8f8f8f;letter-spacing:.1em;text-transform:uppercase}}.rg.on{{border-color:#ffc53d;color:#ffc53d}}
</style></head><body>
<h1>HOWE INTERNATIONAL · ALX</h1>
<h2>Your board</h2>
{place_card(place)}
{range_card(radius)}
<h3>Board style</h3>
<p class="sub">Pick a look, {html.escape(name)}. The board changes straight away.</p>
{''.join(cards)}
<p class="note">Every style keeps the same layout, so it always lines up with the frame. You can also tap the board itself to change it.</p>
<p class="ver">ALX Departures {html.escape(version or "")}</p>
<div id="toast">Changed. Have a look at the board</div>
<script>
function toast(msg, bad) {{
  const t = document.getElementById('toast'); t.textContent = msg; t.classList.toggle('err', !!bad);
  t.classList.add('show'); clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove('show'), 3200);
}}
document.getElementById('pcForm').onsubmit = async e => {{
  e.preventDefault();
  const btn = e.target.querySelector('button'); btn.disabled = true; btn.textContent = '…';
  try {{
    const r = await fetch('/api/settings', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ postcode: document.getElementById('pc').value }}) }});
    const d = await r.json();
    if (!r.ok) toast(d.error || 'Something went wrong', true);
    else {{
      document.getElementById('pc').value = d.postcode;
      document.getElementById('placeNow').textContent = d.place ? `Centred on ${{d.place}} (${{d.postcode}})` : 'Saved.';
      toast(d.message || 'Saved');
    }}
  }} catch (err) {{ toast("Couldn’t reach the board. Is your phone on the same Wi-Fi?", true); }}
  btn.disabled = false; btn.textContent = 'Save';
}};
const NOTES = {json_notes};
document.querySelectorAll('.rg').forEach(b => b.onclick = async () => {{
  const r = await fetch('/api/settings', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify({{ radius_mi: +b.dataset.r }}) }});
  if (!r.ok) return toast('Something went wrong', true);
  document.querySelectorAll('.rg').forEach(x => x.classList.toggle('on', x === b));
  document.getElementById('rgNote').textContent = NOTES[b.dataset.r] || '';
  toast(`Radar range ${{b.dataset.r}} miles`);
}});
document.querySelectorAll('.card').forEach(c => c.onclick = async () => {{
  const r = await fetch('/api/settings', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({{ theme: c.dataset.id }}) }});
  if (!r.ok) return;
  document.querySelectorAll('.card').forEach(x => x.classList.toggle('on', x === c));
  toast('Changed. Have a look at the board');
}});
</script></body></html>"""
