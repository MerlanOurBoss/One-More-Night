"""Synthesizes the appliances' sounds: 22 kHz mono, loops seamless. Needs numpy; run with any Python that has it:
C:/Users/merla/Tools/sand3d-env/Scripts/python.exe ArtSource/make_appliance_sounds.py
Writes Assets/Audio/{fridge_hum,aircon_fan,microwave_hum,washer_drum,washer_thump,microwave_beep,appliance_open,appliance_close}.wav. Written blind: judge by ear.
"""
import wave
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent.parent / "Assets" / "Audio"
RATE = 22050
rng = np.random.default_rng(11)


def save(name, signal, peak=0.8):
    signal = signal / np.max(np.abs(signal)) * peak
    with wave.open(str(OUT / f"{name}.wav"), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes((signal * 32767).astype(np.int16).tobytes())
    print("WROTE", name, round(len(signal) / RATE, 2), "s")


def looping_noise(seconds, low, high):
    """Band-limited noise that loops: shaped in the frequency domain over exactly its length."""
    n = int(seconds * RATE)
    spectrum = np.fft.rfft(rng.standard_normal(n))
    freqs = np.fft.rfftfreq(n, 1 / RATE)
    spectrum[(freqs < low) | (freqs > high)] = 0
    noise = np.fft.irfft(spectrum, n)
    return noise / np.max(np.abs(noise))


def tones(seconds, partials):
    """Whole-numbered cycles over its length, so that it loops."""
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    out = np.zeros(n)
    for freq, amp in partials:
        cycles = round(freq * seconds)
        out += amp * np.sin(2 * np.pi * cycles * t / seconds)
    return out, t


# Fridge: mains hum and a compressor's rattle, breathing slowly.
LENGTH = 6.0
hum, t = tones(LENGTH, [(50, 1.0), (100, 0.55), (150, 0.22), (200, 0.1), (300, 0.04)])
slow = 0.85 + 0.15 * np.sin(2 * np.pi * t / LENGTH)
save("fridge_hum", hum * slow + 0.12 * looping_noise(LENGTH, 300, 1500) * slow)

# Air conditioner: soft moving air, a little tone from the fan.
LENGTH = 6.0
fan, t = tones(LENGTH, [(120, 0.12), (240, 0.05)])
air = looping_noise(LENGTH, 150, 1100)
save("aircon_fan", air * (0.9 + 0.1 * np.sin(2 * np.pi * 2 * t / LENGTH)) + fan, peak=0.6)

# Microwave: the magnetron's harsh 100 Hz buzz over its fan.
LENGTH = 4.0
buzz, t = tones(LENGTH, [(100, 1.0), (200, 0.7), (300, 0.5), (400, 0.3), (600, 0.15), (800, 0.08)])
save("microwave_hum", buzz + 0.5 * looping_noise(LENGTH, 400, 3000))

# Washer: the drum's turn, and something heavy in it falling once a turn.
TURN, TURNS = 1.5, 2
LENGTH = TURN * TURNS
turn, t = tones(LENGTH, [(40, 0.3), (80, 0.14)])
swish = looping_noise(LENGTH, 200, 1200) * (0.5 + 0.5 * np.sin(2 * np.pi * TURNS * t / LENGTH)) ** 2
drum = turn + 0.35 * swish
for k in range(TURNS):
    since = (t - (k + 0.15) * TURN) % LENGTH     # wraps round the loop's end
    fall = 0.8 + 0.2 * (k % 2)                    # not quite the same every time
    drum += fall * np.exp(-since * 14) * np.sin(2 * np.pi * 62 * since)
    drum += 0.3 * fall * np.exp(-since * 40) * np.sin(2 * np.pi * 130 * since)
save("washer_drum", drum)

# A single dull knock from inside the drum, for a false alarm: the machine is off.
t = np.arange(int(0.9 * RATE)) / RATE
thump = np.exp(-t * 11) * np.sin(2 * np.pi * 58 * t) + 0.35 * np.exp(-t * 34) * np.sin(2 * np.pi * 124 * t)
thump += 0.1 * np.exp(-t * 60) * looping_noise(0.9, 200, 1400)[:len(t)]
save("washer_thump", thump * np.minimum(1, (t[-1] - t) * 40))

# Microwave's beep: done, three times. Nothing was put in it.
t = np.arange(int(1.1 * RATE)) / RATE
beep = np.zeros(len(t))
for start in (0.0, 0.4, 0.8):
    gate = ((t >= start) & (t < start + 0.22)).astype(float)
    beep += gate * np.sign(np.sin(2 * np.pi * 1850 * t)) * 0.5
edge = np.minimum(1, np.minimum(t, t[-1] - t) * 200)
save("microwave_beep", beep * edge, peak=0.55)

# An appliance door pulled open: the seal lets go, and the door's weight comes along.
t = np.arange(int(0.4 * RATE)) / RATE
pop = np.exp(-t * 18) * np.sin(2 * np.pi * 95 * t) + 0.45 * np.exp(-t * 45) * looping_noise(0.4, 700, 3000)[:len(t)]
save("appliance_open", pop * np.minimum(1, (t[-1] - t) * 40), peak=0.6)

# Pushed shut: a soft thud, and the latch.
t = np.arange(int(0.35 * RATE)) / RATE
thud = np.exp(-t * 24) * np.sin(2 * np.pi * 72 * t) + 0.5 * np.exp(-t * 80) * looping_noise(0.35, 500, 2500)[:len(t)]
save("appliance_close", thud * np.minimum(1, (t[-1] - t) * 40), peak=0.65)
