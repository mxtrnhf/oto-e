# Oto-e (音絵)

**Databending for images, Audacity-style.** Oto-e reads a picture's pixels as an audio recording, lets you edit that recording
with sound effects (echo, phaser, bitcrusher, tape ageing, …), and writes the glitched result back as a picture, live.

![Oto-e main window](screenshot_1.png)

> **Heads-up:** this project is entirely vibecoded and lightly tested. As I continue working on it I try to get a better
> understanding of the code underneath.

[Features](#features) · [Quick start](#quick-start) · [How it works](#how-it-works) · [Effects](#effects) ·
[Saving](#saving-and-exporting) · [Controls](#controls) · [Credits](#credits) · [License](#license)

## Features

- **72 effects in 11 categories.** Audio-style effects (volume, EQ, delay and reverb, modulation, distortion, spectral), glitch tools,
  picture-domain effects (pixel sort, channel swap, JPEG cruncher, …) and a full cassette-tape emulation.
- **Live preview** on a background thread, so sliders stay smooth. A small-scale preview keeps big images responsive.
- **Two ways to select.** *Run* selects a stretch of the data in reading order, like on a waveform. *Rectangle* draws a box that
  becomes its own small picture.
- **Choose how bytes become sound.** Interleaved or planar layout, and 8-bit, signed 8-bit, 16-bit (either endianness) or µ-law
  samples, like the import settings in Audacity's raw import. The same effect looks completely different under each.
- **History as a tree.** Undo, redo, jump to any step, and tweak the settings of any past step as a new branch. Nothing is thrown away.
  Edit → Copy Edit History as Text puts your steps and their exact settings on the clipboard, ready to share.
- **Randomize.** One key applies a random effect with random settings; undo it or try another.
- **Compare** with the original at any moment.
- **Save and export** to PNG, JPEG, WebP, BMP, TIFF, JPEG 2000 and TGA, with each format's own settings.
- **Built-in guide.** Help → Controls (F1) is a searchable guide, Help → Effect reference lists every effect and setting, and
  every control has a tooltip.
- **Your text size.** View → Text size scales the font of the whole program from 85 % to 175 %.

## Quick start

Requires **Python 3.10+** (with `venv`/`pip`) and a desktop session.

```bash
git clone https://github.com/mxtrnhf/oto-e.git && cd oto-e
./run.sh                 # first run creates .venv and installs dependencies
./run.sh photo.jpg       # or open an image directly
```

Manual alternative (Windows, macOS, or if you prefer):

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt     # Windows: .venv\Scripts\pip
.venv/bin/python -m oto_e                     # Windows: .venv\Scripts\python
```

On some Linux distros you may need `python3-venv` and the Qt xcb libraries (`libxcb-cursor0` on Debian/Ubuntu).

### Your first glitch

1. **Open** an image with Ctrl+O, or drop a file on the window.
2. **Select a part of it** by dragging on the image or on the waveform underneath. Selecting nothing affects the whole picture.
3. **Double-click an effect** in the list on the right, for example *Echo* or *Phaser*.
4. **Drag the sliders.** The picture changes live. Press **OK** to keep it, or Cancel.
5. **Try your luck** with Randomize (Ctrl+Shift+R). Undo (Ctrl+Z) anything you don't like, or click a step in the history on the left.
6. **Save** with Save As (Ctrl+Shift+S), or Export a copy (Ctrl+E) to keep working on the same file.

## How it works

**A picture becomes sound.** Every pixel is three bytes (red, green, blue), read row after row. Each byte is one audio sample,
played at 44,100 samples per second, so a row 1,000 pixels wide is 3,000 samples long. The red-green-blue pattern repeats every
three samples, which puts colour at about 14.7 kHz: anything that removes treble also removes colour. Effects change that audio,
and the result is written back into the picture.

### Selections: Run or Rectangle

The **Selection** switch in the toolbar decides what dragging on the image makes. Switching clears the current selection.

| | Run (default) | Rectangle |
|---|---|---|
| **What it is** | A stretch of the data in reading order, left to right then top to bottom. A staircase on the image when it starts or ends mid-row. | A box you drag. It is treated as its own small picture. |
| **Audio effects** | Process it as one continuous stream. | See the box's rows joined end to end, so settings measured in samples relate to the box's width. |
| **Image effects** | Not available (a staircase has no picture shape). Whole rows count as a rectangle. | Available. |

### Data and samples

The **Data** and **Samples** boxes in the toolbar decide how the picture's bytes become audio.

- **Layout:** *interleaved* (R, G, B, R, G, B, … pixel after pixel, the classic) or *planar* (all red bytes, then all green, then all blue).
- **Samples:** *unsigned 8-bit* (classic, one byte per sample), *signed 8-bit* (values above 127 count as negative), *16-bit little-endian*
  or *big-endian* (pairs of bytes, so low bytes act as grain), or *µ-law* (telephone-style companding).

Changing either clears the selection, because positions in the stream mean something else.

## Effects

| Category | Effects | Examples |
|---|---:|---|
| Volume | 8 | Amplify, Normalize, Fade In/Out, Tremolo, Compressor, Noise Gate |
| EQ & Filters | 9 | Low-pass, High-pass, Band-pass, Notch, 5-Band EQ, Median Filter |
| Delay & Reverb | 7 | Echo, Reverb, Flanger, Chorus, Vibrato |
| Modulation | 3 | Phaser, Wahwah, Ring Modulator |
| Distortion | 5 | Distortion, Wavefolder, Bitcrusher, Sample-rate Reducer |
| Spectral | 8 | Paulstretch, Whisper, Robotize, Frequency Shifter, Spectral Gate |
| Time & Glitch | 7 | Stutter, Reverse Chunks, Sort Chunks, Tape Stop, Multi-tap Delay |
| Bits & Bytes | 5 | Bitwise Operation, Byte Add (wrap-around), Wraparound Gain, Rectify |
| **Image** | 9 | Pixel Sort, Channel Swap, Chromatic Aberration, Row Shift, Warp, Block Displacement, Pixelate, JPEG Crunch, JPEG Cruncher |
| Tape & Analog | 1 | Tape Recording (a whole cassette in one effect) |
| Special | 10 | Invert, Reverse, Shift, Change Speed, Repeat Beginning |

Every effect and every setting is described in Help → Effect reference, and in its tooltips.

### Image effects

The **Image** category works on the picture itself instead of its audio. These effects apply to the whole image or to a
**rectangle selection**; with a Run selection they are greyed out, and double-clicking one offers to switch the toolbar to
Rectangle for you. Randomize skips them while a Run selection is active.

- **JPEG Crunch** is one harsh JPEG pass, optionally corrupting the compressed data for broken-file glitches.
- **JPEG Cruncher** is hundreds of gentle re-saves, with drifting block grids, resizing, stretching and colour bleed: it makes the
  picture look like it was recovered from an abandoned Soviet computer in Mongolia.

### Tape emulation

*Tape & Analog → Tape Recording* simulates recording the image to cassette or reel and playing it back. Start from a preset
(Fresh cassette, Old mixtape, Dolby mismatch, Dubbed five times, Basement find, …) and tweak:

- **Recording**: tape type, *which machine recorded it* (Nakamichi-class, AKAI-class, JVC-class, boombox, portable recorder),
  recording quality and record level (overload and saturation). Each machine sets a treble ceiling, noise floor, built-in wow and
  flutter, overload margin and head alignment (my own rough approximations, not measured specs).
- **Noise reduction**: what it was *recorded* with against what it is *played back* with (Off, Dolby B, Dolby C), plus a playback-level
  error. Matched Dolby cuts hiss; a mismatch makes it too bright or too dull.
- **Tape condition**: age, physical damage, hiss, dropouts, wow and flutter. Age and damage also add treble loss and print-through ghosts.
- **Playback**: *which machine plays it* (recording on one machine and playing on another can add a speed mismatch that slants the
  rows; it is off unless you enable *Machine speed difference*), head quality, azimuth error, extra speed error.
- **Passes**: how many times it was re-recorded onto another tape, and extra plays (head and oxide wear).

Good to know: by default timing errors (wow, flutter, speed) snap to whole pixels so they shear the picture without rotating the hue;
switch *Timing errors* to "Rotate hue freely" for rainbow chaos. Several generations on large images can take a few seconds per
preview; untick *Live preview* if it feels slow.

## Saving and exporting

Oto-e never overwrites your original unless you choose that file.

| Command | What it does |
|---|---|
| **Save** (Ctrl+S) | The first time it asks where to write. After that it writes to the same file, reusing the last settings for that format. |
| **Save As** (Ctrl+Shift+S) | Always asks for a file and its settings. The new file becomes the one you are working on. |
| **Export a copy** (Ctrl+E) | Writes a copy and leaves your working file alone. Handy for dumping variants. |
| **Revert to Original** | Puts the original back as a new history step, so you can still jump back. |

Formats: **PNG**, **JPEG**, **WebP**, **BMP**, **TIFF**, **JPEG 2000** and **TGA**. Save As and Export ask for the format's settings
(JPEG quality, colour detail and progressive loading; lossless or lossy WebP and JPEG 2000; PNG, TIFF and TGA compression) and remember
them. For an exact copy of your glitch choose a lossless setting: PNG, BMP, TIFF, TGA, or lossless WebP or JPEG 2000.

## Controls

The complete list is in **Help → Controls (F1)**. The essentials:

| | |
|---|---|
| **Image** | Wheel zooms; drag selects; click clears the selection; Space + drag or middle-drag pans |
| **Waveform and spectrogram** | Wheel zooms the time axis; Shift + wheel scrolls; middle-drag pans; double-click fits; drag selects; drag a selection's edge resizes it |
| **Effects** | Double-click or Enter opens an effect's settings; right-click for About |
| **History** | Click a step to jump to it; right-click a step to tweak it as a new branch |
| **Compare** | Hold the toolbar button, or hold **C** anywhere in the main window (not while an effect window is open; there, untick *Live preview*) |
| **Copy** | Ctrl+C copies the selection as a picture, Ctrl+Shift+C the whole image |
| **Repeat / Randomize** | Ctrl+R repeats the last effect; Ctrl+Shift+R randomizes; Ctrl+Shift+E reverts the last randomize and tries another |
| **Undo / Redo** | Ctrl+Z / Ctrl+Shift+Z |

## Credits

The Image effects were inspired by [gfejer/databender](https://github.com/gfejer/databender) (GPL-3.0), a different tool that applies
pixel-level glitch effects to images and video. Oto-e is an unrelated project with its own code; the effects here are written from scratch.

## License

GPL-3.0. See [LICENSE](LICENSE). (PyQt6, which Oto-e is built on, is also GPL-3.0.)
