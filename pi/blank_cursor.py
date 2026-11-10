#!/usr/bin/env python3
"""
Writes an invisible mouse-pointer theme, so nothing ever draws a pointer on the board.

The screen's USB lead can show up as a pointing device even with no touch, and the
kiosk then shows a pointer in the middle of the screen until it's moved. The board page
hides it with CSS, but only after the pointer moves over the page; this hides it everywhere,
from the moment the screen starts.

    sudo python3 blank_cursor.py /usr/share/icons/alx-blank  [/home/alx/.icons/default]
"""

import os
import struct
import sys

# Every pointer name the screen program (cage/wlroots) or Chromium might ask for
NAMES = ["default", "left_ptr", "arrow", "top_left_arrow", "text", "xterm", "pointer", "hand1", "hand2",
         "progress", "left_ptr_watch", "wait", "watch", "crosshair", "cross", "grab", "grabbing", "move",
         "fleur", "all-scroll", "not-allowed", "no-drop", "help", "question_arrow", "context-menu", "cell",
         "copy", "alias", "col-resize", "row-resize", "n-resize", "s-resize", "e-resize", "w-resize",
         "ne-resize", "nw-resize", "se-resize", "sw-resize", "ew-resize", "ns-resize", "nesw-resize",
         "nwse-resize", "zoom-in", "zoom-out", "vertical-text", "sb_h_double_arrow", "sb_v_double_arrow"]


def xcursor(size=24):
    """An Xcursor file with one fully transparent 1x1 image (format: libXcursor's file spec)."""
    image_type = 0xFFFD0002
    header = struct.pack("<4sIII", b"Xcur", 16, 0x10000, 1)
    toc = struct.pack("<III", image_type, size, 16 + 12)
    image = struct.pack("<IIIIIIIII", 36, image_type, size, 1, 1, 1, 0, 0, 0) + struct.pack("<I", 0)
    return header + toc + image


def write_theme(root, name="alx-blank"):
    cursors = os.path.join(root, "cursors")
    os.makedirs(cursors, exist_ok=True)
    data = xcursor()
    for n in NAMES:
        with open(os.path.join(cursors, n), "wb") as f:
            f.write(data)
    with open(os.path.join(root, "index.theme"), "w") as f:
        f.write(f"[Icon Theme]\nName={name}\nComment=Invisible pointer for ALX Departures\n")


if __name__ == "__main__":
    for target in sys.argv[1:] or ["/usr/share/icons/alx-blank"]:
        write_theme(target)
        print(f"blank pointer theme written to {target}")
