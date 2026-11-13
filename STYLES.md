# ALX Departures: board styles

Saved styles for the board and radar. Tap the board to open the style picker, or use the phone page. The choice is saved on the board.

| Style | Look | Notes |
|---|---|---|
| **Solari** (default) | Amber split flaps on black, green radar | The classic departure board, unchanged. |
| **Terminal** | Modern UK airport screen: navy header and footer bands, striped rows, yellow tags | Clean and very readable. |
| **Cockpit** | Airbus glass cockpit: B612 (the font made for Airbus displays), green values, cyan labels, magenta for the nearest plane, a compass-arc radar with no sweep | Dark, so good at night. |
| **CRT** | Green phosphor text with scanlines | Unchanged. |
| **Sage** | Calm: soft sage green and oat, Jost lettering on rounded tiles, a peach accent, dotted radar rings | Easy on the eye. |
| **Dusk** | Twilight: lavender and slate, Titillium, an apricot sunset glow low on the board and in the radar, the first stars | Easy on the eye; good in the evening. |
| **Sandstone** | Warm and light: sand with a stucco texture, cream tiles with terracotta letters, olive tag, terracotta and olive double rule | Easy on the eye; the warm light style. |
| **Paper** | Printed timetable: typewriter letters straight on paper, dotted leaders, double red rule, serif title | The light style. Best in a bright room. |
| **Renaissance** | An illuminated manuscript: vellum with darkened edges, Cinzel capitals with a red initial, Playfair italics with old-style numbers, double gold rules with an ornament, sepia photos, a brass astrolabe radar with fleurons | Light. |
| **Wavepunk** | Synthwave: neon cyan flaps, chrome-gradient Orbitron title, a magenta grid horizon, a striped sun in the radar | Replaces Sunset. |
| **Blueprint** | An engineering drawing: white line-work on blue with a drawing grid, outlined character boxes in B612 Mono, a dashed card, centre-lines and a protractor scale on the radar, and a dimension line across the top giving the board window's real width: 95.94 mm | |
| **Bosnia** | The flag: royal blue, white letters, yellow tags and rules, the flag's triangle and line of stars faintly behind the board, and nine white stars round a yellow-ringed radar | |
| **Sunflower** | Her favourite colour: marigold, sunburst rays, and the radar is a sunflower (seed-head face, petal rim) | Bold, like airport signs. |
| **Disco** | Glitter-gold flaps on faceted tiles, a Monoton title in a gold-to-pink gradient, a lit dance floor fading up the board, spotlight beams, and the radar is a mirrorball with sparkles | Funky. |
| **Pop Art** | A comic strip: Bangers lettering, Ben-Day halftone dots, white boxes with black ink outlines, a speech-bubble card with a tail, a yellow halftone radar inside a red POW burst | Funky. |
| **Groovy** | The 1970s: a fat italic Shrikhand title with a stacked shadow, every column its own colour (red, orange, mustard, brown, avocado), rainbow stripe rules, rainbow arcs, a 70s-ringed radar | Funky. |
| **Candy** | A sweet shop: pink with sprinkles, rounded Fredoka letters on white tiles, icing drips under the header, a dashed card, and the radar is a sprinkled pink doughnut | Funky. |
| **Cosmos** | Deep space: a starfield and purple and teal nebulae on the board, a constellation by the clock, Michroma lettering, glowing flaps, and the radar is an orrery: dashed orbits with planets (one ringed), the home dot as the sun | Funky. |
| **Grand Prix** | The pit wall: asphalt, italic Titillium, a timing tower (white flight column, purple for the nearest, yellow types), red-and-white kerbs, sector colours on the card, a chequered flag, and the radar is a soft tyre | Funky. Generic: no team or series logos. |
| **Pho** | A noodle shop: red lacquer with a lattice pattern, gold Lilita One signage, two lanterns, cream enamel menu tiles, and the radar is a bowl of pho from above (broth, noodles, beef, herbs, chilli, a lime wedge, steam) in a blue-and-white bowl | Funky. |

Retired: Racing Green, Jet Age and Graphite (v1.5), Ivory (v1.7). A board that had one saved moves to Sage, Dusk, Solari or Renaissance.

## Choosing the style on the Pi

Set it in `config.json`:

```json
{ "theme": "cosmos" }
```

Or add it to the kiosk address: `http://localhost:8080/?kiosk&theme=cosmos`. The address wins over `config.json`.

## The one rule: same layout

The faceplate is cut to fit the board window and the radar porthole, so **a style may only change colours, fonts and textures, never sizes or positions.** Decoration goes in backgrounds, shadows and overlays (`::before`/`::after`) inside the two windows: `--board-bg` for the board window, `--face` under the planes and `--deco`/`--tick` over the radar. Element heights are fixed in the CSS ("Fixed sizes" block) so even a different font can't move anything. After adding a style, check it lines up exactly with the others.

**No drawn frame.** The real faceplate is wood or carbon, so the screen never draws one. Each style has a single flat background colour, `--bg`, that fills the whole screen around and behind both windows, with no gradient and no border. If the cut-outs come out a touch large, the edge you see is just that same colour.

Alex picks between the styles with the on-screen picker (tap the board) or the phone page. A new style needs adding in three places: its CSS block, the `THEMES` list in `web/index.html`, and the `THEMES` list in `settings_page.py` (which has the preview colours for the phone page).

## Adding or tweaking a style

All colours, fonts and map tints are variables in the `<style>` block of `web/index.html`:

1. Copy one of the `body[data-theme="..."]` blocks and give it a new name.
2. Change only the variables you want. Anything left out falls back to the Solari values.
3. Add it to the `THEMES` list near the top of the script.

The variables that matter most:

- **Background:** `--bg`, one flat colour for the whole screen
- **Board:** `--title`, `--accent`, `--text`
- **Flaps:** `--flap-ink` (letters), `--flap-top`, `--flap-bot` (tile halves), `--flap-line` (the split; `transparent` for flat cells), `--flap-radius`
- **Radar:** `--radar-in`, `--radar-out` (background), `--radar-line` (rings), `--radar-ink` (planes), `--radar-near` (nearest plane)
- **Map tint:** `--map-hue` (colour shift), `--map-invert` (1 for a dark map, 0 for a light map), `--map-opacity`
- **Font:** `--font`. Built in: Oswald, Barlow Condensed, VT323, Orbitron, B612, B612 Mono, Jost, Courier Prime, Playfair Display, Cinzel, Titillium Web, Monoton, Bangers, Shrikhand, Fredoka, Michroma and Lilita One (all SIL Open Font License).

## Ideas to try next

- An automatic day/night switch, for example Sandstone by day and Cockpit after dark.
- Airline-coloured flight codes on the Terminal style.

# Layout concepts

`web/concepts.html` holds four complete layout ideas, each designed around its own faceplate cut-outs. Switch layouts with **‹ ›** and the face with **Wood / Carbon / Bare**. Wood gets a warm amber screen with brass bezels and brass-inlay engraving; carbon gets graphite and white with a motorsport red, aluminium bezels and etched lettering. These run on demo data for now. Whichever is picked gets wired to live data.

| Layout | Faceplate cut-outs | What it does well | Trade-offs |
|---|---|---|---|
| **Overhead Now** | 1 rectangle + 1 round porthole | Nearest flight in big flaps (flight, from → to, airline, type, altitude, distance, speed, which way to look), 4 more below, radar with map | Busiest screen |
| **Gate Board** | 1 long slot, title engraved above it | The most "real departure board": 7 big rows, nearest pinned on top, an arrow on every row pointing where to look | No map or radar |
| **Instrument Cluster** | 3 round dials + 1 strip | Dashboard look: altimeter, big radar, a "look here" compass, and the nearest flight on a flap strip. Pairs well with carbon | Details for one flight only; 4 cut-outs to make |
| **Arriving / Leaving** | 3 slots with engraved labels beside them | Sorts traffic into arriving nearby, leaving nearby and passing over | Needs airport-distance logic added to the server; no map |

**Closest flight:** every layout leads with the nearest aircraft. It only changes when another plane is clearly closer, so it doesn't flicker between two.

**Live numbers:** distance and flight level update in place without flipping, since they change every second. Everything else flips.

**Physical scale:** the 7" panel is about 154 × 86 mm, so 1 px on these layouts ≈ 0.15 mm. Cut-outs must match the screen exactly, but engraving drawn inside the screen area here is only 2–5 mm tall. On the real build, the faceplate can extend past the screen so titles and labels sit in a wider border at a readable size.
