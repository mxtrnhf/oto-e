"""The text of the Help window: section trees for the controls guide and the effect reference.

Qt-free. Each builder takes a `Colors` (derived from the current theme by helpview) so tables get visible borders
whether the theme is light or dark, and returns a list of Section. A section's `html` is its body; the window adds the
heading, so bodies start straight with text.
"""
from __future__ import annotations

import html as _html
from dataclasses import dataclass, field

from .helptext import _fmt_range


@dataclass
class Colors:
    border: str = "#b8b8b8"
    head: str = "#f0f0f0"
    cell: str = "#ffffff"


@dataclass
class Section:
    id: str
    title: str
    html: str = ""
    children: list["Section"] = field(default_factory=list)


def table(rows, c: Colors, head: tuple | None = None, widths: tuple | None = None) -> str:
    """A bordered table. Rows are tuples of HTML cells; a row that is a plain string becomes a full-width group heading."""
    ncol = len(head) if head else max(len(r) for r in rows if not isinstance(r, str))
    w = [f' width="{x}"' for x in (widths or [None] * ncol)]
    out = [f'<table width="100%" cellspacing="1" cellpadding="7" bgcolor="{c.border}">']
    if head:
        out.append("<tr>" + "".join(f'<th align="left" bgcolor="{c.head}"{w[i] if i < len(w) else ""}>{h}</th>' for i, h in enumerate(head)) + "</tr>")
    for r in rows:
        if isinstance(r, str):
            out.append(f'<tr><td colspan="{ncol}" bgcolor="{c.head}"><b>{r}</b></td></tr>')
        else:
            out.append("<tr>" + "".join(f'<td bgcolor="{c.cell}" valign="top"{w[i] if i < len(w) and not head else ""}>{x}</td>' for i, x in enumerate(r)) + "</tr>")
    return "".join(out) + "</table>"


def controls_sections(c: Colors) -> list[Section]:
    k = lambda s: f"<b>{s}</b>"
    two = lambda rows, head=("Do this", "To get this"): table(rows, c, head, ("34%", "66%"))
    return [
        Section("basics", "Getting started", "<p>Oto-e reads a picture's bytes as an audio recording, lets you edit that recording with sound effects, "
                "and writes the result back as a picture. An echo smears the image sideways, a filter blurs it or strips its colour, a bitcrusher "
                "posterizes it. Open an image, pick a range, double-click an effect, and watch it change.</p>", [
            Section("how", "How a picture becomes sound",
                    "<p>Every pixel is three bytes (red, green, blue), read row after row. Each byte is one audio sample, played at 44,100 samples per "
                    "second, so a row 1,000 pixels wide is 3,000 samples long. The red-green-blue pattern repeats every three samples, which puts colour "
                    "at about 14.7 kHz: anything that removes treble also removes colour.</p>"
                    "<p>The <b>Data</b> menu changes how the bytes are read (see <i>Data and samples</i>), which changes what every effect does.</p>"),
            Section("window", "The window", table([
                (k("Top centre"), "The image. Select on it, zoom it, pan it."),
                (k("Bottom"), "The same data drawn as a waveform and spectrogram. Select ranges on it too."),
                (k("Right"), "The effects list with search, plus Apply, Repeat last, Randomize."),
                (k("Left"), "History: every step you have made, as a tree."),
                (k("Toolbar"), "Save, Undo, Redo, Compare, the View, Data and Samples boxes, and the Selection switch."),
            ], c, ("Where", "What"), ("24%", "76%"))),
        ]),
        Section("image", "The image", "<p>The picture at the top. It reacts to the mouse as follows.</p>", [
            Section("image-view", "Zooming and panning", two([
                (k("Mouse wheel"), "Zoom in and out around the pointer"),
                (k("Space + drag") + " or " + k("middle-drag"), "Pan. Hold Space with the pointer over the image"),
                ("Toolbar buttons above the image", "− + Fit, Fill, 100 %, Center. Same as the View menu (Ctrl+0, Ctrl+1, Ctrl+Shift+M, Ctrl+=, Ctrl+-)"),
            ])),
            Section("image-select", "Selecting",
                    "<p>Dragging selects; what a drag makes depends on the <b>Selection</b> switch (see <i>Selection modes</i>). The outline shows what is "
                    "selected. With nothing selected, effects apply to the whole image.</p>" + two([
                        (k("Drag"), "Select a Run or a Rectangle"),
                        (k("Click") + " (no drag)", "Clear the selection"),
                        (k("Ctrl+A") + " / " + k("Ctrl+Shift+A"), "Select all / select none"),
                        (k("Ctrl+C") + " / " + k("Ctrl+Shift+C"), "Copy the selection / the whole image as a picture"),
                    ]) + "<p>In <i>Planar</i> data layout a selection on the image covers the red plane only.</p>"),
            Section("compare", "Comparing with the original",
                    "<p><b>Hold C</b> (anywhere in the main window, no need to hover over the image) or hold the <b>Compare</b> button in the "
                    "toolbar to see the original. Let go and your edit comes back. It changes only the picture; the waveform keeps showing your edit.</p>"
                    "<p>C does nothing while an effect window is open (and not in the search box). To compare an effect you are still tuning, tick and "
                    "untick <b>Live preview</b> in its window instead.</p>"),
            Section("opening", "Opening files",
                    "<p>Press <b>Ctrl+O</b> or drop an image file on the window. Your original file is never overwritten: the first Save always asks where "
                    "to write.</p>"),
        ]),
        Section("wave", "Waveform and spectrogram",
                "<p>The bottom panel draws the picture's data as sound. The <b>View</b> box in the toolbar switches between Waveform, Spectrogram and Both. "
                "<b>Every control below works on the spectrogram just as on the waveform.</b></p>", [
            Section("wave-view", "Zooming and scrolling", two([
                (k("Mouse wheel"), "Zoom the time axis around the pointer"),
                (k("Shift + wheel"), "Scroll sideways"),
                (k("Middle-drag"), "Pan"),
                (k("Double-click"), "Fit the whole stream in view (also Ctrl+Shift+0)"),
            ])),
            Section("wave-select", "Selecting a range", two([
                (k("Drag"), "Select a range. The matching pixels are outlined on the image"),
                (k("Drag a selection's edge"), "Resize it"),
                (k("Click") + " (no drag)", "Clear the selection"),
            ]) + "<p>A selection made here is always a Run, and the Selection switch follows.</p>"),
        ]),
        Section("selection", "Selection modes: Run or Rectangle",
                "<p>The <b>Selection</b> switch in the toolbar decides what your next drag on the image makes, and the kind of selection decides "
                "<b>how effects are applied</b>. Switching it clears the current selection, because the two kinds do not convert into each other.</p>", [
            Section("sel-run", "Run (the default)",
                    "<p>Selects a stretch of the picture's data in reading order, left to right and then top to bottom, exactly like selecting on the waveform. "
                    "On the image it is a staircase whenever it starts or ends partway along a row. Audio effects process it as one continuous stream, so an "
                    "echo or a filter carries on from the end of one row into the next.</p>"
                    "<p><b>Picture effects (the Image category) cannot use it.</b> A staircase has no picture shape to sort, shift or warp, and the waveform is "
                    "a flat list of samples with no rows or columns at all. Whole rows, or Select All, do count as a rectangle, so those work.</p>"),
            Section("sel-rect", "Rectangle",
                    "<p>Drag a box. The box is treated as its own small picture, and only its pixels change.</p>" + table([
                        (k("Audio effects"), "See the box's rows joined end to end. Settings measured in samples (delays, chunk sizes) relate to the box's width, "
                                             "not the whole image's, so the same settings can look quite different from a Run."),
                        (k("Picture effects"), "Work, since a box is a picture."),
                        (k("Waveform"), "Shows a rectangle as many thin bands. You cannot edit it there."),
                    ], c, None, ("24%", "76%"))),
            Section("sel-more", "Good to know", "<ul><li>With nothing selected, both modes apply to the whole image, and picture effects work.</li>"
                    "<li>History remembers each step's selection, so undo, redo and tweaking behave the same in both modes.</li>"
                    "<li>The ⓘ button next to the switch opens this page.</li></ul>"),
        ]),
        Section("effects", "Effects", "<p>The list on the right holds every effect, sorted into categories. The <b>Image</b> category holds the picture effects.</p>", [
            Section("fx-apply", "Applying an effect", two([
                (k("Double-click") + " or " + k("Enter") + " on an effect", "Open its settings window. It applies to the selection, or to the whole image"),
                (k("Apply…") + " button", "Same, for the effect that is highlighted"),
                ("Type in the " + k("search box"), "Narrow the list"),
                (k("Right-click") + " an effect", "About this effect (what it does, in picture terms), or apply it"),
            ])),
            Section("fx-dialog", "The settings window",
                    "<p>Sliders preview live on the image. <b>OK</b> applies, <b>Cancel</b> changes nothing. Every setting has a tooltip, and "
                    "<b>ⓘ About this effect</b> explains it in full. Some effects have a <b>Preset</b> box.</p>"
                    "<p><b>Small-scale preview</b> (audio effects) computes only a stretch of rows in the middle of the target, which is much faster on big "
                    "images; OK still applies to everything. Picture effects always preview in full.</p>"),
            Section("fx-repeat", "Repeating and randomizing", two([
                (k("Repeat last") + " (Ctrl+R)", "Apply the previous effect again with the same settings"),
                (k("Randomize") + " (Ctrl+Shift+R)", "Apply a random effect with random settings. Undo it if you do not like it"),
                (k("Revert and randomize") + " (Ctrl+Shift+E)", "Undo the last randomize, then try another"),
            ]) + "<p>Randomize never picks Tape Recording (it can take a minute), and skips the Image effects while the selection is a Run.</p>"),
            Section("fx-image", "Picture effects",
                    "<p>Effects in the <b>Image</b> category (Pixel Sort, Channel Swap, Chromatic Aberration, Row Shift, Warp, Block Displacement, Pixelate, "
                    "JPEG Crunch, JPEG Cruncher) treat the picture as a picture. They need a <b>rectangle</b> or no selection, and ignore the Data settings. "
                    "While a Run is selected they are greyed out in the list; double-click one and Oto-e offers to switch to Rectangle for you.</p>"),
        ]),
        Section("history", "History and undo", "<p>The panel on the left lists every step you have made. Nothing is ever thrown away.</p>", [
            Section("hist-jump", "Jumping around", two([
                (k("Click") + " a step", "Jump to that moment"),
                (k("Ctrl+Z") + " / " + k("Ctrl+Shift+Z"), "Undo / redo"),
                ("Edit after jumping back", "Starts a new branch. The old one stays in the list, shown grey, and you can jump to it any time"),
            ]) + "<p>Very old abandoned branches are dropped only when history grows past its memory budget.</p>"),
            Section("hist-tweak", "Tweaking a step", two([
                (k("Right-click") + " a step, then <i>Tweak settings…</i>", "Reopens that effect with its old settings, starting from the picture as it was before that step. "
                                                                       "Applying creates a new branch next to the original step"),
            ]) + "<p>Steps with no adjustable settings cannot be tweaked.</p>"),
        ]),
        Section("data", "Data and samples", "<p>These two boxes in the toolbar (also in the Data menu) decide how the picture's bytes become audio, like the "
                "import settings in Audacity's raw import. <b>The same effect looks completely different under each.</b> Changing either clears the selection, "
                "because positions in the stream mean something else.</p>", [
            Section("data-layout", "Layout", table([
                (k("Interleaved RGB"), "The classic reading: R, G, B, R, G, B… pixel after pixel."),
                (k("Planar"), "All the red bytes first, then all the green, then all the blue."),
            ], c, ("Layout", "Meaning"), ("26%", "74%"))),
            Section("data-samples", "Sample format", table([
                (k("Unsigned 8-bit") + " (classic)", "One byte is one sample. Mid-grey is silence."),
                (k("Signed 8-bit"), "One byte is one sample, but values above 127 count as negative, so smooth gradients become jagged waveforms."),
                (k("16-bit little-endian"), "Pairs of bytes make one sample, low byte first. The low bytes act as noise, so effects fill the picture with grain. The stream is half as long."),
                (k("16-bit big-endian"), "Pairs of bytes, high byte first."),
                (k("µ-law"), "A telephone-audio encoding: each byte is a logarithmically scaled sample."),
            ], c, ("Format", "How a byte is read"), ("30%", "70%"))),
        ]),
        Section("saving", "Saving and exporting", "<p>Oto-e never overwrites your original unless you choose that file.</p>", [
            Section("save-cmds", "Save, Save As, Export", table([
                (k("Save") + " (Ctrl+S)", "First time it asks where to write. After that it writes to the same file, reusing the last settings for that format."),
                (k("Save As") + " (Ctrl+Shift+S)", "Always asks for a file and settings. The new file becomes the one you are working on."),
                (k("Export a copy") + " (Ctrl+E)", "Asks for a file and settings, writes a copy, and leaves your working file and its unsaved-changes mark alone. Handy for dumping variants."),
                (k("Revert to Original") + " (File menu)", "Puts the original picture back as a new history step, so you can still jump back."),
            ], c, ("Command", "What it does"), ("30%", "70%"))),
            Section("save-formats", "File formats and their settings", table([
                (k("PNG"), "Compression level", "Lossless"),
                (k("JPEG"), "Quality, colour detail, baseline or progressive", "Lossy"),
                (k("WebP"), "Lossless or lossy, and quality", "Lossless by default"),
                (k("BMP"), "None", "Lossless"),
                (k("TIFF"), "Compression: none, LZW or Deflate", "Lossless"),
                (k("JPEG 2000"), "Lossless or lossy, and ratio", "Lossless by default"),
                (k("TGA"), "Compression: none or RLE", "Lossless"),
            ], c, ("Format", "Settings asked for", "Quality"), ("22%", "50%", "28%")) +
                    "<p>Save As and Export show the settings box and remember your choices per format. Choose a lossless format to keep every pixel of your glitch exactly.</p>"),
        ]),
        Section("keys", "Keyboard shortcuts", table([
            "File",
            (k("Ctrl+O"), "Open"), (k("Ctrl+S"), "Save"), (k("Ctrl+Shift+S"), "Save As"), (k("Ctrl+E"), "Export a copy"), (k("Ctrl+Q"), "Quit"),
            "Edit",
            (k("Ctrl+Z"), "Undo"), (k("Ctrl+Shift+Z"), "Redo"), (k("Ctrl+C"), "Copy selection as a picture"), (k("Ctrl+Shift+C"), "Copy the whole image as a picture"),
            (k("Ctrl+A"), "Select all"), (k("Ctrl+Shift+A"), "Select none"),
            (k("Ctrl+R"), "Repeat the last effect"), (k("Ctrl+Shift+R"), "Randomize"), (k("Ctrl+Shift+E"), "Revert the last randomize and try another"),
            "View",
            (k("Ctrl+0"), "Fit image to window"), (k("Ctrl+1"), "Actual size (100 %)"), (k("Ctrl+Shift+M"), "Center the image"),
            (k("Ctrl+="), "Zoom in"), (k("Ctrl+-"), "Zoom out"), (k("Ctrl+Shift+0"), "Fit the waveform"),
            "Held keys",
            (k("Space"), "Pan while dragging (pointer over the image)"), (k("C"), "Show the original while held (not while an effect window is open)"),
            "Other",
            (k("Enter"), "Open the highlighted effect"), (k("F1"), "This window"),
        ], c, None, ("30%", "70%"))),
    ]


def reference_sections(effects: list, c: Colors, order: list[str] | None = None) -> list[Section]:
    """Every effect, grouped by category: a section per category, a child per effect. `order` lists the categories
    in the order to show them (any others follow)."""
    cats: dict[str, list] = {}
    for e in effects:
        cats.setdefault(e.category, []).append(e)
    first = [x for x in (order or []) if x in cats]
    cats = {k: cats[k] for k in first + [k for k in cats if k not in first]}
    out = []
    for ci, (cat, items) in enumerate(cats.items()):
        kids = []
        for ei, e in enumerate(items):
            body = f"<p>{_html.escape(e.summary).replace(chr(10), '<br>')}</p>"
            if e.audio:
                body += f"<p><i>In audio:</i> {_html.escape(e.audio)}</p>"
            if e.info:
                body += "<p><i>This effect has its own guide: see Help, Tape emulation guide.</i></p>"
            elif e.params:
                body += table([(f"<b>{_html.escape(p.label)}</b>", _html.escape(_fmt_range(p)), _html.escape(p.help)) for p in e.params],
                              c, ("Setting", "Range", "What it does"), ("22%", "26%", "52%"))
            else:
                body += "<p><i>No settings: it just applies.</i></p>"
            if e.domain == "image":
                body += "<p><i>Picture effect: needs a rectangle selection or none.</i></p>"
            kids.append(Section(f"fx{ci}-{ei}", e.name, body))
        out.append(Section(f"cat{ci}", cat, f"<p>{len(items)} effect{'s' if len(items) != 1 else ''}.</p>", kids))
    return out
