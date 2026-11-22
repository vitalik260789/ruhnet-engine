"""Compose final frames: photo background + 3D layer (rgba) + HUD, encode H.264.
python3 tools/compose.py projects/<slug> [--stills 15,300] [--scale 1.0]
-> out/silent.mp4 (or out/still_XXXX.jpg)"""
import sys, os, json, math, argparse, subprocess
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.join(os.path.dirname(__file__), "..")
FONT_B = os.path.join(ROOT, "fonts", "InterDisplay-Black.otf")
FONT_S = os.path.join(ROOT, "fonts", "Inter-Bold.otf")
W, H, FPS = 1080, 1920, 30


def text_sprite(lines, stroke=8):
    fonts = [ImageFont.truetype(p, s) for _, p, s, _ in lines]
    d0 = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    boxes = [d0.textbbox((0, 0), tx, font=f, stroke_width=stroke) for (tx, _, _, _), f in zip(lines, fonts)]
    wmax = max(b[2] - b[0] for b in boxes) + 40
    htot = sum(b[3] - b[1] for b in boxes) + 10 * (len(lines) - 1) + 40
    im = Image.new("RGBA", (wmax, htot), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    y = 20
    for (tx, _, _, col), f, b in zip(lines, fonts, boxes):
        d.text((wmax // 2, y - b[1]), tx, font=f, fill=tuple(col) + (255,), anchor="ma",
               stroke_width=stroke, stroke_fill=(8, 8, 12, 255))
        y += b[3] - b[1] + 10
    arr = np.asarray(im, np.float32) / 255.0
    sh = cv2.GaussianBlur(arr[..., 3], (0, 0), 9) * 0.6
    out = arr.copy()
    out[..., 3] = arr[..., 3] + sh * (1 - arr[..., 3])
    out[..., :3] = arr[..., :3] * arr[..., 3:4] / np.maximum(out[..., 3:4], 1e-4)
    return out


def paste(frame, spr, cx, cy, alpha=1.0, scale=1.0):
    if alpha <= 0.01:
        return
    if abs(scale - 1) > 0.01:
        spr = cv2.resize(spr, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
    h, w = spr.shape[:2]
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    sx0, sy0 = max(0, -x0), max(0, -y0)
    x0c, y0c, x1c, y1c = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
    s = spr[sy0:sy0 + (y1c - y0c), sx0:sx0 + (x1c - x0c)]
    a = s[..., 3:4] * alpha
    reg = frame[y0c:y1c, x0c:x1c]
    reg[:] = reg * (1 - a) + s[..., :3] * 255 * a


def pop(t, t0, dur=0.22):
    if t < t0:
        return 0.0, 1.0
    u = min(1, (t - t0) / dur)
    return min(1, u * 2.5), 1 + 0.35 * (1 - u) ** 2 - 0.06 * math.sin(u * math.pi)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("proj")
    ap.add_argument("--stills", default="")
    a = ap.parse_args()
    cfg = json.load(open(os.path.join(a.proj, "config.json")))
    D = json.load(open(os.path.join(a.proj, "out", "frames.json")))
    ph = D["phys"]
    PPM, TY, CXP = ph["PPM"], ph["TABLE_Y"], ph["CXP"]
    fpx = cfg["lens"] / 36.0 * H
    cd, chh = cfg["cam_d"], cfg["cam_h"]

    def proj(X, Z):                                    # level camera looking along +Y
        return W / 2 + fpx * X / cd, H / 2 - fpx * (Z - chh) / cd

    # background: photo scaled to frame width, horizon on the camera horizon (frame centre)
    im = Image.open(os.path.join(a.proj, cfg["bg"])).convert("RGB")
    s = max(W / im.width, (H / 2) / cfg["bg_horizon"], (H / 2) / (im.height - cfg["bg_horizon"])) * 1.005
    big = np.asarray(im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS), np.float32)
    oy = int(round(cfg["bg_horizon"] * s - H / 2))
    ox = int(round((big.shape[1] - W) / 2))
    bg = cv2.GaussianBlur(big[oy:oy + H, ox:ox + W].copy(), (0, 0), cfg.get("bg_blur", 1.6))

    frames, rid, sched = D["frames"], D["rid"], D["sched"]
    NP, cn, ct = len(sched), D["collapse_n"], D["collapse_t"]
    title = text_sprite([(cfg["title"][0], FONT_B, 96, (255, 255, 255)), (cfg["title"][1], FONT_B, 92, (255, 175, 50))])
    bet = text_sprite([("Сделай ставку в комментариях", FONT_B, 52, (255, 255, 255))], stroke=6)
    label = text_sprite([("ВЫТАЩЕНО", FONT_S, 50, (255, 245, 230))], stroke=6)
    end1 = text_sprite([(cfg.get("end", "РУХНУЛА НА {n}-Й!").format(n=cn), FONT_B, 92, (255, 95, 60))])
    end2 = text_sprite([("Угадал? Пиши в комментариях", FONT_B, 54, (255, 255, 255))], stroke=6)
    nums = {}
    rng = np.random.default_rng(3)
    stills = set(int(v) for v in a.stills.split(",")) if a.stills else None
    proc = None
    out = os.path.join(a.proj, "out")
    if stills is None:
        proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                                 "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
                                 "-pix_fmt", "yuv420p", "-movflags", "+faststart", os.path.join(out, "silent_tmp.mp4")],
                                stdin=subprocess.PIPE)
    cache = {}
    for f, fr in enumerate(frames):
        if stills is not None and f not in stills:
            continue
        t = fr["t"]
        u = rid[f]
        if u not in cache:
            p = os.path.join(out, "rgba", f"r_{u:04d}.png")
            rgba = np.asarray(Image.open(p).convert("RGBA"), np.float32) / 255
            if rgba.shape[0] != H:
                rgba = cv2.resize(rgba, (W, H), interpolation=cv2.INTER_LINEAR)
            cache = {u: rgba}
        rgba = cache[u]
        frame = bg * (1 - rgba[..., 3:4]) + rgba[..., :3] * 255 * rgba[..., 3:4]
        # highlight outline around the bottle about to be pulled
        if fr["hl"] is not None and (ct is None or t < ct):
            i, uu = fr["hl"]
            # which body: the one pulled at sched[i] = first body missing right after the pull
            k = D.setdefault("_pk", {}).get(i)
            if k is None:
                pf = next(j for j, x in enumerate(frames) if x["pulled"] > i)
                gone = set(frames[pf - 1]["bodies"]) - set(frames[pf]["bodies"])
                k = D["_pk"][i] = gone.pop() if gone else None
            if k is not None and k in fr["bodies"]:
                x, y, ang = fr["bodies"][k]
                it = D["items"][k]
                X0, Z0 = (x - CXP) / PPM, (TY - y) / PPM
                bw, bh = it["w"] / PPM, it["h"] / PPM
                c, s_ = math.cos(ang), math.sin(ang)
                pts = []
                for dx, dz in ((-bw / 2 - 0.01, -0.01), (bw / 2 + 0.01, -0.01), (bw / 2 + 0.01, bh + 0.01), (-bw / 2 - 0.01, bh + 0.01)):
                    pts.append(proj(X0 + dx * c + dz * s_, Z0 - dx * s_ + dz * c))
                last = i == NP - 1
                pulse = 0.6 + 0.4 * math.sin(uu * math.pi * (8 if last else 2))
                col = (255, 55, 45) if last else (120, 220, 255)
                add = np.zeros((H // 2, W // 2, 3), np.float32)
                cv2.polylines(add, [np.round(np.array(pts) / 2 * 8).astype(np.int32)], True, col, 3, cv2.LINE_AA, 3)
                add = cv2.GaussianBlur(add, (0, 0), 3) * 2.2 + add
                frame += cv2.resize(add * pulse, (W, H), interpolation=cv2.INTER_LINEAR)
        # slow push-in, then pull back after the collapse; shake on collapse
        if ct is None or t < ct:
            zoom = 1.0 + 0.08 * min(1, t / (sched[-1]["pull"] + 0.3))
        else:
            zoom = 1.08 - 0.08 * min(1, (t - ct) / 3.0)
        cx, cy = W / 2, H * 0.6
        dx = dy = 0.0
        if ct is not None and 0 <= t - ct < 0.6:
            amp = 10 * (1 - (t - ct) / 0.6)
            dx, dy = rng.normal(0, amp, 2)
        M = np.float32([[zoom, 0, cx - cx * zoom + dx], [0, zoom, cy - cy * zoom + dy]])
        frame = cv2.warpAffine(np.clip(frame, 0, 255), M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        # HUD
        if t < 2.5:
            al, sc = pop(t, 0.05)
            if t > 2.15:
                al *= max(0, 1 - (t - 2.15) / 0.35)
            paste(frame, title, W / 2, 300, al, sc)
        if 0.4 < t < 3.9:
            al, sc = pop(t, 0.4)
            if t > 3.5:
                al *= max(0, 1 - (t - 3.5) / 0.4)
            paste(frame, bet, W / 2, 1790, al, sc)
        if t >= 2.4 and (ct is None or t - ct < 0.9):
            al, _ = pop(t, 2.4)
            if ct is not None and t >= ct:
                al *= max(0, 1 - (t - ct - 0.5) / 0.4)
            n = fr["pulled"] if (ct is None or t < ct) else cn
            if n not in nums:
                c = (255, 255, 255) if n < 7 else ((255, 205, 80) if n < 11 else (255, 110, 55))
                nums[n] = text_sprite([(str(n), FONT_B, 210, c)], stroke=10)
            _, sc = pop(t, sched[n - 1]["pull"] if n > 0 else 2.4, 0.2)
            paste(frame, label, W / 2, 175, al, 1)
            paste(frame, nums[n], W / 2, 330, al, sc)
        if ct is not None and t - ct > 0.9:
            al, sc = pop(t, ct + 0.9, 0.3)
            paste(frame, end1, W / 2, 280, al, sc)
            al2, sc2 = pop(t, ct + 1.5, 0.3)
            paste(frame, end2, W / 2, 1790, al2, sc2)
        o = np.clip(frame, 0, 255).astype(np.uint8)
        if proc is not None:
            proc.stdin.write(o.tobytes())
        else:
            Image.fromarray(o).save(os.path.join(out, f"still_{f:04d}.jpg"), quality=90)
    if proc is not None:
        proc.stdin.close()
        proc.wait()
        os.replace(os.path.join(out, "silent_tmp.mp4"), os.path.join(out, "silent.mp4"))
    json.dump(dict(duration=D["duration"], events=D["events"], impacts=D["impacts"], sched=sched, collapse_n=cn),
              open(os.path.join(out, "events.json"), "w"))
    print("composed", "stills" if stills else "video")


if __name__ == "__main__":
    main()
