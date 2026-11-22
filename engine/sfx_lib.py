"""Procedural sound-effect helpers (numpy/scipy). Import as: import sfx_lib as S"""
import numpy as np
from scipy.signal import butter, sosfilt

SR = 48000
rng = np.random.default_rng(5)


def filt(x, lo=None, hi=None, order=4):
    if lo and hi:
        sos = butter(order, [lo, hi], "bandpass", fs=SR, output="sos")
    elif lo:
        sos = butter(order, lo, "highpass", fs=SR, output="sos")
    else:
        sos = butter(order, hi, "lowpass", fs=SR, output="sos")
    return sosfilt(sos, x).astype(np.float32)


def env_exp(n, tau):
    return np.exp(-np.arange(n) / (tau * SR)).astype(np.float32)


def tone(freqs, amps, decays, dur):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    out = np.zeros(n, np.float32)
    for f, a, d in zip(freqs, amps, decays):
        out += a * np.sin(2 * np.pi * f * tt + rng.uniform(0, 6)) * np.exp(-tt / d)
    return out


def noise(dur):
    return rng.standard_normal(int(dur * SR)).astype(np.float32)


def thud(f0=80, dur=0.35, amp=1.0):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    f = f0 * (1 + 0.8 * np.exp(-tt / 0.03))
    ph = 2 * np.pi * np.cumsum(f) / SR
    return (amp * np.sin(ph) * np.exp(-tt / (dur / 3))).astype(np.float32)


def burst(dur, lo, hi, tau):
    x = filt(noise(dur), lo, hi)
    return x * env_exp(len(x), tau)


def fade_window(n, fin=0.05, fout=0.5):
    w = np.ones(n, np.float32)
    a, b = int(fin * SR), int(fout * SR)
    w[:a] = np.linspace(0, 1, a)
    w[-b:] *= np.linspace(1, 0, b) ** 1.5
    return w


def wobble(n, rate=6, depth=0.4):
    k = max(4, int(n / SR * rate))
    ctrl = rng.uniform(1 - depth, 1, k)
    return np.interp(np.arange(n), np.linspace(0, n, k), ctrl).astype(np.float32)


def pops(dur, rate, lo, hi, plen=(0.003, 0.01), amp=(0.2, 1.0)):
    n = int(dur * SR)
    out = np.zeros(n, np.float32)
    k = rng.poisson(rate * dur)
    for _ in range(k):
        i = rng.integers(0, n)
        pl = int(rng.uniform(*plen) * SR)
        p = rng.standard_normal(pl).astype(np.float32) * env_exp(pl, pl / SR / 3) * rng.uniform(*amp)
        j = min(n, i + pl)
        out[i:j] += p[: j - i]
    return filt(out, lo, hi, 2)


def blips(dur, rate, f0=(220, 520)):
    n = int(dur * SR)
    out = np.zeros(n, np.float32)
    for _ in range(rng.poisson(rate * dur)):
        i = rng.integers(0, n)
        bl = int(rng.uniform(0.02, 0.05) * SR)
        tt = np.arange(bl) / SR
        f = rng.uniform(*f0) * (1 + 1.5 * tt / tt[-1])
        b = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * np.arange(bl) / bl) * rng.uniform(0.3, 1)
        j = min(n, i + bl)
        out[i:j] += b[: j - i].astype(np.float32)
    return out


