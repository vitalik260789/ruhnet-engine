"""Procedural SFX for 3D reels: glass clinks, wooden planks, sea waves.
python3 tools/sound3d.py projects/<slug> -> out/sfx.wav (reads out/events.json)"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "engine"))
import json, math
import numpy as np
from scipy.io import wavfile
import sfx_lib as S

SR = S.SR
rng = np.random.default_rng(31)
PROJ = sys.argv[1]
E = json.load(open(os.path.join(PROJ, "out", "frames.json")))
E = {k: E[k] for k in ("events", "impacts", "sched", "duration")}
E["events"] = [list(e) for e in E["events"]] + [["hl", s["hl"], i] for i, s in enumerate(E["sched"])]
DUR = E["duration"] + 0.4
N = int(DUR * SR)
L = np.zeros(N, np.float32)
R = np.zeros(N, np.float32)


def put(sig, t, gain=1.0, pan=0.0):
    i = int(t * SR)
    if i >= N or i < 0:
        return
    sig = sig[: N - i] * gain
    L[i:i + len(sig)] += sig * np.sqrt(0.5 * (1 - pan))
    R[i:i + len(sig)] += sig * np.sqrt(0.5 * (1 + pan))


def knock(f0=None, amp=1.0, dur=0.12):
    f0 = f0 or rng.uniform(550, 1300)
    s = S.tone([f0, f0 * 2.3, f0 * 3.9], [0.6, 0.25, 0.1], [0.035, 0.02, 0.012], dur)
    b = S.burst(0.02, 1500, 8000, 0.003)
    s[: len(b)] += b * 0.5
    return s * amp


def scrape(d=0.32):
    n = int(d * SR)
    tt = np.arange(n) / SR
    stick = (np.sin(2 * np.pi * rng.uniform(45, 70) * tt) > 0.3).astype(np.float32)
    s = S.filt(S.noise(d), 500, 3500) * (0.4 + 0.6 * stick) * np.sin(np.pi * tt / d) ** 0.6
    s += S.filt(S.noise(d), 150, 600) * 0.4 * np.sin(np.pi * tt / d)
    return s.astype(np.float32)


def clink(f0=None, amp=1.0, dur=0.22):
    f0 = f0 or rng.uniform(380, 700)
    r = rng.uniform(0.96, 1.04, 4)
    s = S.tone([f0, f0 * 2.72 * r[0], f0 * 5.32 * r[1], f0 * 8.1 * r[2]], [0.5, 0.35, 0.22, 0.12],
               [0.09, 0.06, 0.035, 0.02], dur)
    b = S.burst(0.015, 2500, 12000, 0.002)
    s[: len(b)] += b * 0.6
    return s * amp


def glass(f0=None, amp=1.0, dur=0.3):
    f0 = f0 or rng.uniform(3000, 5200)
    r = rng.uniform(0.97, 1.03, 3)
    s = S.tone([f0, f0 * 1.52 * r[0], f0 * 2.31 * r[1], f0 * 0.31 * r[2]], [0.45, 0.3, 0.15, 0.25],
               [0.12, 0.08, 0.05, 0.05], dur)
    b = S.burst(0.01, 4000, 14000, 0.0015)
    s[: len(b)] += b * 0.5
    return s * amp


def waves(d):
    n = int(d * SR)
    tt = np.arange(n) / SR
    swell = 0.55 + 0.45 * np.sin(2 * np.pi * tt / 6.5 - 1.2) ** 2
    x = S.filt(S.noise(d), 120, 900, 2) * swell
    x += S.filt(S.noise(d), 1500, 6000, 2) * 0.25 * swell ** 3
    return (x * S.fade_window(n, 0.8, 1.0)).astype(np.float32)


def heartbeat():
    return S.thud(52, 0.22, 1.0) + np.concatenate([np.zeros(int(0.16 * SR), np.float32), S.thud(48, 0.22, 0.7)])[: int(0.22 * SR)]


coll = [e[1] for e in E["events"] if e[0] == "collapse"]
coll = coll[0] if coll else DUR
sched = E["sched"]
last_pull = sched[-1]["pull"]

put(waves(DUR), 0, 0.16)

# tension drone: rises until the collapse
n = int(coll * SR)
tt = np.arange(n) / SR
rise = (tt / coll) ** 1.6
drone = (np.sin(2 * np.pi * 55 * tt) * 0.5 + np.sin(2 * np.pi * 82.5 * tt) * 0.25 * rise + np.sin(2 * np.pi * 110.5 * tt) * 0.12 * rise)
drone += S.filt(S.noise(coll), 80, 400) * 0.6
drone *= (0.25 + 0.75 * rise)
w = np.ones(n, np.float32)
w[: int(1.0 * SR)] = np.linspace(0, 1, int(1.0 * SR))
w[-int(0.05 * SR):] = np.linspace(1, 0, int(0.05 * SR))
put((drone * w).astype(np.float32), 0, 0.22)

# heartbeat in the second half, accelerating
tb = sched[9]["hl"]
period = 0.85
while tb < coll - 0.1:
    put(heartbeat(), tb, 0.55)
    prog = (tb - sched[9]["hl"]) / max(0.1, coll - sched[9]["hl"])
    period = 0.85 - 0.45 * prog
    tb += period

for e in E["events"]:
    if e[0] == "hl":
        i = e[2]
        last = i == len(sched) - 1
        put(S.tone([1250 if not last else 880], [0.5], [0.05], 0.12), e[1], 0.18)
        if last:
            # rising tension whine during final highlight
            d = last_pull - e[1]
            m = int(d * SR)
            x = np.arange(m) / SR
            f = 300 + 500 * (x / d) ** 2
            s = np.sin(2 * np.pi * np.cumsum(f) / SR) * (x / d) ** 1.5
            put(s.astype(np.float32), e[1], 0.12)
    elif e[0] == "pull":
        put(scrape(0.26), e[1], 0.45, rng.uniform(-0.2, 0.2))
        put(glass(rng.uniform(2500, 3500), 0.4, 0.2), e[1] + 0.02, 0.3)
        put(knock(amp=0.4), e[1] + 0.25, 0.4)
    elif e[0] == "collapse":
        put(S.thud(42, 1.2, 1.0), e[1], 0.9)
        put(S.burst(1.4, 60, 400, 0.5), e[1], 0.6)
        put(S.burst(0.5, 400, 6000, 0.1), e[1], 0.25)

# collapse clatter from physics impacts (slow-mo => lower pitch while slowed)
imps = sorted(E["impacts"], key=lambda x: x[0])
last_t = -1
for t, m, kind in imps:
    if t < coll - 0.05:
        continue
    if t - last_t < 0.012:
        continue
    last_t = t
    slow = (t - coll) < 2.6
    amp = min(1.0, 0.25 + math.log10(m / 40 + 1) * 0.6)
    pan = rng.uniform(-0.6, 0.6)
    if kind == "plank":
        f0 = rng.uniform(300, 700) if slow else rng.uniform(550, 1100)
        put(knock(f0, amp, 0.2 if slow else 0.12), t, 0.5, pan)
    else:
        f0 = rng.uniform(1800, 3200) if slow else rng.uniform(3000, 6500)
        put(glass(f0, amp, 0.45 if slow else 0.3), t, 0.38, pan)
    if kind == "floor":
        put(S.burst(0.12, 300, 3000, 0.04), t, 0.15 * amp, pan)   # sand puff

# end sting
put(S.thud(55, 0.7), coll + 0.9, 0.5)
put(S.tone([660, 990, 1320], [0.35, 0.25, 0.15], [0.5, 0.4, 0.3], 1.3), coll + 0.95, 0.12)

mix = np.stack([L, R], 1)
mix /= np.abs(mix).max() + 1e-6
mix *= 0.89
wavfile.write(os.path.join(PROJ, "out", "sfx.wav"), SR, (mix * 32767).astype(np.int16))
print("ok", len(imps), "impacts")
