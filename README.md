# Oto-e (音絵)
[Disclaimer: this project is entirely vibecoded and lightly tested. As I continue working on it I try to get better understanding of the code underneath]

Databending for images, Audacity-style. The image's pixel data is treated as an audio
stream: pick a range on the waveform, apply an effect (echo, phaser, bitcrusher, …) and
watch the image change live.

![Oto-e main window](screenshot_1.png)
## Run

Requires **Python 3.10+** (with `venv`/`pip`) and a desktop session.

```bash
git clone git@github.com:mxtrnhf/oto-e.git && cd oto-e
./run.sh                 # first run creates .venv and installs dependencies
./run.sh photo.jpg       # or open an image directly
```

Manual alternative (Windows/macOS or if you prefer):

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt     # Windows: .venv\Scripts\pip
.venv/bin/python -m oto_e                 # Windows: .venv\Scripts\python
```

On some Linux distros you may need `python3-venv` and the Qt xcb libraries (`libxcb-cursor0` on Debian/Ubuntu).

## Use

- **Open** an image (Ctrl+O or drag it in). **Drag on the image** or **on the waveform** to select a range (on the image, a selection runs in reading order, left-to-right then top-to-bottom, like the data itself). Click to clear. The outline shows what's selected. No selection = whole image.
- **Hold Space and drag** (or middle-drag) to pan the image; wheel zooms.
- **Double-click** an effect on the right (or Apply…). Tweak sliders with live preview, OK to commit.
- **🎲 Randomize** (Ctrl+Shift+R) applies a random effect with random settings to the selection. Undo (Ctrl+Z) if you don't like it.
- **Ctrl+C** copies the selection (or the whole image) to the clipboard as a picture, ready to paste into other apps. Unselected ends of the first and last row are transparent.
- Ctrl+R repeats the last effect. On the waveform: wheel zooms, Shift+wheel / middle-drag pans, double-click fits.
- **Data** menu (also in the toolbar): how the picture's bytes become audio, like the import settings in Audacity's raw import.
  *Layout*: interleaved RGB (classic) or planar (R, then G, then B). *Samples*: unsigned 8-bit (classic, one byte per sample),
  signed 8-bit, 16-bit little- or big-endian (pairs of bytes), or µ-law. The same effect looks completely different under each.
  Changing either clears the selection, because positions in the stream mean something else.
- Save never overwrites your original unless you choose it: first Save asks for a path, and *Save As* picks a new one. *Export a copy* (Ctrl+E) writes a copy without changing which file you are working on, handy for dumping variants. Formats: PNG, JPEG, WebP (lossless), BMP, TIFF, JPEG 2000, TGA.

## Image effects

Besides the audio-style effects, the **Image** category works on the picture itself: Pixel Sort, Channel Swap,
Chromatic Aberration, Row Shift, Warp, Block Displacement, Pixelate, JPEG Crunch (one harsh pass, optionally corrupting the
compressed data) and JPEG Cruncher (hundreds of gentle re-saves, like a picture recovered from an abandoned Soviet computer in Mongolia). They apply to the whole image or to a **rectangle selection**; with a
reading-order (run) selection they are unavailable, so switch to rectangle selection first. Randomize skips them
while a run selection is active.

## Tape emulation

*Tape & Analog → Tape Recording* simulates recording the image to cassette/reel and playing it back. Start from a preset
(Fresh cassette, Old mixtape, Dolby mismatch, Dubbed five times, Basement find, …) and tweak:

- **Recording**: tape type, *which machine recorded it* (Nakamichi-class, AKAI-class, JVC-class, boombox, portable recorder), recording quality, record level (overload/saturation). Each machine sets a treble ceiling, noise floor, built-in wow/flutter, overload margin and head alignment (my own rough approximations, not measured specs).
- **Noise reduction**: what it was *recorded* with vs *played back* with (Off / Dolby B / Dolby C) plus a playback-level error. Matched Dolby cuts hiss; a mismatch makes it too bright or too dull.
- **Tape condition**: age, physical damage, hiss, dropouts, wow, flutter. Age and damage also add treble loss and print-through ghosts.
- **Playback**: *which machine plays it* (recording on one machine and playing on another can add a speed mismatch that slants the rows; it's off unless you enable *Machine speed difference*), head quality, azimuth error, extra speed error.
- **Passes**: how many times it was re-recorded onto another tape, and extra plays (head/oxide wear).

Good to know: colour is stored at ~14.7 kHz in the "audio", so lost treble = lost colour. By default timing errors (wow, flutter, speed)
snap to whole pixels so they shear the picture without rotating the hue; switch *Timing errors* to "Rotate hue freely" for rainbow chaos.
Several generations on large images can take a few seconds per preview; untick *Live preview* if it feels slow.

## Credits

The Image effects were inspired by [gfejer/databender](https://github.com/gfejer/databender) (GPL-3.0), a different
tool that applies pixel-level glitch effects to images and video. Oto-e is an unrelated project with its own code;
the effects here are written from scratch.

## License

GPL-3.0. See [LICENSE](LICENSE). (PyQt6, which Oto-e is built on, is also GPL-3.0.)
