"""Calm ambient score and soft glitch sound effects, synthesised with numpy. No samples, no third-party music."""
import numpy as np
from scipy.signal import butter, fftconvolve, lfilter, sosfilt

SR = 44100
rng = np.random.default_rng(11)


def note(n):  # MIDI number -> Hz
    return 440.0 * 2 ** ((n - 69) / 12)


def env(n, a, r, sr=SR):
    e = np.ones(n)
    na, nr = int(a * sr), int(r * sr)
    e[:na] = np.linspace(0, 1, na) ** 2
    e[-nr:] = np.minimum(e[-nr:], np.linspace(1, 0, nr) ** 2)
    return e


def lowpass(x, f, order=2):
    return sosfilt(butter(order, f, "low", fs=SR, output="sos"), x)


def pad_voice(midi, dur, pan, cutoff_lfo_phase):
    n = int(dur * SR); t = np.arange(n) / SR; f = note(midi); out = np.zeros(n)
    for det in (-0.07, 0.0, 0.06):  # slightly detuned partials make it breathe
        out += np.sin(2 * np.pi * f * (1 + det / 100 * 12) * t + rng.uniform(0, 6.28))
        out += 0.30 * np.sin(2 * np.pi * 2 * f * (1 + det / 100 * 12) * t + rng.uniform(0, 6.28))
        out += 0.12 * np.sin(2 * np.pi * 3 * f * t + rng.uniform(0, 6.28))
    out *= 0.5 * (1 + 0.18 * np.sin(2 * np.pi * 0.11 * t + cutoff_lfo_phase))  # slow swell
    out = lowpass(out, 1400) * env(n, 3.0, 3.5)
    return np.stack([out * (1 - pan), out * (1 + pan)]) * 0.5


def soft_tone(midi, dur=7.0, vel=1.0, pan=0.0):
    """A breath of sound: slow attack, no percussive onset, a touch of vibrato. Replaces the bell, which pinged."""
    n = int(dur * SR); t = np.arange(n) / SR; f = note(midi)
    vib = 1 + 0.0025 * np.sin(2 * np.pi * 4.6 * t) * np.minimum(t / 2.5, 1)
    s = np.sin(2 * np.pi * f * vib * t) + 0.18 * np.sin(2 * np.pi * 2 * f * vib * t)
    s = lowpass(s, 1800) * env(n, 1.8, 3.2) * vel * 0.10
    return np.stack([s * (1 - pan), s * (1 + pan)])


def glitch_tick(strength=1.0, dur=0.09):
    n = int(dur * SR); x = rng.uniform(-1, 1, n)
    step = int(rng.integers(6, 30)); x = np.repeat(x[::step], step)[:n]  # sample-and-hold: bitcrushed noise
    x = np.round(x * 3) / 3
    x = lowpass(x, 4200) * np.exp(-np.arange(n) / SR * 38)
    return np.stack([x, x[::-1] if False else np.roll(x, 40)]) * 0.16 * strength


def swell(dur, f0=300, f1=2600, gain=0.07):
    n = int(dur * SR); x = rng.uniform(-1, 1, n) * np.linspace(0, 1, n) ** 3
    f = np.geomspace(f0, f1, n)
    # time-varying lowpass by chunked filtering
    out = np.zeros(n); z = None
    for i in range(0, n, 2048):
        sos = butter(2, min(f[i], SR / 2 - 100), "low", fs=SR, output="sos")
        seg, z0 = sosfilt(sos, x[i:i + 2048], zi=(np.zeros((sos.shape[0], 2)) if z is None else z)); out[i:i + 2048] = seg; z = z0
    return np.stack([out, np.roll(out, 90)]) * gain


def tick(gain=0.05):
    """A very soft, dark key tap (low-passed noise), for typing and screen changes."""
    n = int(0.035 * SR); x = lowpass(rng.uniform(-1, 1, n), 1100) * np.exp(-np.arange(n) / SR * 120) * gain * 4
    return np.stack([x, x])


def sub(midi, dur):
    n = int(dur * SR); t = np.arange(n) / SR
    s = np.sin(2 * np.pi * note(midi) * t) * env(n, 2.5, 3.0) * 0.16
    return np.stack([s, s])


def reverb_ir(sec=4.0):
    n = int(sec * SR); t = np.arange(n) / SR
    ir = np.stack([rng.normal(0, 1, n), rng.normal(0, 1, n)]) * np.exp(-t * 1.9)
    ir = np.stack([lowpass(c, 3800) for c in ir])
    ir[:, :int(.02 * SR)] *= np.linspace(0, 1, int(.02 * SR))
    return ir / np.sqrt((ir ** 2).sum(axis=1, keepdims=True)) * 0.9


def mix(dst, src, t):
    i = int(t * SR); n = min(src.shape[1], dst.shape[1] - i)
    if n > 0 and i >= 0:
        dst[:, i:i + n] += src[:, :n]


def score(total, glitches, clicks, reveals, title_t, end_t, ui_range):
    n = int((total + 5) * SR)
    music = np.zeros((2, n)); fx = np.zeros((2, n))
    # slow progression in A minor; each chord lasts 8 s and overlaps the next
    chords = [[45, 57, 60, 64, 67], [41, 53, 57, 60, 64], [48, 55, 60, 64, 67], [43, 55, 59, 62, 66], [45, 57, 60, 64, 71], [41, 53, 57, 60, 65]]
    t, k = 3.0, 0
    while t < total:
        ch = chords[k % len(chords)]
        for j, m in enumerate(ch):
            mix(music, pad_voice(m, 11.5, [-.5, -.2, 0, .25, .5][j % 5] * .8, k + j), t + j * 0.18)
        mix(music, sub(ch[0] - 12, 11.5), t)
        t += 8.0; k += 1
    # sparse bell melody (pentatonic), thinner during the UI scene
    scale = [69, 72, 74, 76, 79, 81, 84]
    t, last = 8.0, 3
    while t < total - 4:
        quiet = ui_range[0] < t < ui_range[1]
        if rng.random() < (0.55 if quiet else 0.8):
            last = int(np.clip(last + rng.integers(-2, 3), 0, len(scale) - 1))
            mix(music, soft_tone(scale[last], vel=0.7 if quiet else 1.0, pan=float(rng.uniform(-.5, .5))), t)
        t += float(rng.choice([3.0, 4.5, 6.0]))
    mix(music, soft_tone(69, dur=9.0, vel=1.4), end_t + 0.3); mix(music, soft_tone(76, dur=9.0, vel=1.0, pan=.3), end_t + 1.2)
    # sound effects
    mix(fx, swell(title_t + 2.5, 80, 900, 0.09), 0.0)
    for gt, gs in glitches:
        mix(fx, glitch_tick(gs), gt)
        if gs > .6:
            mix(fx, glitch_tick(gs * .6, .06), gt + 0.11); mix(fx, glitch_tick(gs * .4, .05), gt + 0.19)
    for rt in reveals:
        mix(fx, swell(2.4, 200, 2200, 0.05), rt - 0.1)
    for ct in clicks:
        mix(fx, tick(0.04), ct)
    # reverb on the music and bells; fx get a little too
    ir = reverb_ir()
    wet = np.stack([fftconvolve(music[c], ir[c])[:n] for c in range(2)])
    wetfx = np.stack([fftconvolve(fx[c], ir[c])[:n] for c in range(2)])
    out = music * 0.7 + wet * 0.55 + fx * 0.9 + wetfx * 0.25
    # tape hiss under everything, slowly breathing
    tt = np.arange(n) / SR
    hiss = lowpass(rng.normal(0, 1, n), 7000) * 0.0045 * (0.8 + 0.2 * np.sin(2 * np.pi * 0.07 * tt))
    out += np.stack([hiss, np.roll(hiss, 311)])
    out = sosfilt(butter(2, 28, "high", fs=SR, output="sos"), out, axis=1)
    out = out[:, :int(total * SR)]
    nn = out.shape[1]
    out *= np.minimum(1, np.minimum(np.arange(nn) / (2.0 * SR), (nn - np.arange(nn)) / (3.5 * SR)))[None, :] ** 1.5
    out *= 0.12 / np.sqrt((out[:, nn // 8:nn * 7 // 8] ** 2).mean())  # calm: about -18 dBFS rms
    out = np.tanh(out * 1.3) / 1.3  # only the odd loud transient gets rounded
    out *= min(1.0, 0.85 / np.abs(out).max())
    return out.T.astype(np.float32)
