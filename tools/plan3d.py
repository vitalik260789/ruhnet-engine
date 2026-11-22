"""Plan a 3D reel: pick the pull sequence (physics AI) and replay it on the video timeline.
python3 tools/plan3d.py projects/<slug>   -> projects/<slug>/out/frames.json
All later steps (Blender shards, compose, sound) only read frames.json, so shards are seamless."""
import sys, os, json, math
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import phys3d as P

FPS = 30
DT = 1 / FPS


def schedule(NP):
    sched, t = [], 1.3
    for i in range(NP):
        late, last = i >= 10, i == NP - 1
        wait = 0.3 if last else (0.18 if late else 0.12)
        hl = 1.0 if last else (0.5 if late else 0.3)
        sched.append(dict(hl=t + wait, pull=t + wait + hl, end=t + wait + hl + 0.36))
        t += wait + hl + 0.36
    return sched


def replay(turns):
    NP = len(turns)
    sched = schedule(NP)
    rng = np.random.default_rng(0)
    sp, items = P.build()
    alive = list(items.keys())
    P.step(sp, 45)
    impacts, clock = [], {"t": 0.0}

    def post(arb, space, data):
        if arb.is_first_contact:
            m = arb.total_impulse.length
            if m > 15:
                kinds = [getattr(s, "kind_", "floor") for s in arb.shapes]
                kind = "plank" if "plank" in kinds else ("floor" if "floor" in kinds else "bottle")
                impacts.append((round(clock["t"], 4), round(float(m), 1), kind))
    sp.on_collision(None, None, post_solve=post)

    frames, events = [], []
    pulled, collapse_t, collapse_n = 0, None, None
    flying = []
    snap = P.snapshot(items, alive)
    t, f = 0.0, 0
    while True:
        cur = None
        if collapse_t is None:
            for i, s in enumerate(sched):
                if i != pulled:
                    continue
                if s["hl"] <= t < s["pull"]:
                    cur = [i, (t - s["hl"]) / (s["pull"] - s["hl"])]
                if t >= s["pull"]:
                    k, imps = turns[i]
                    if k in alive:
                        b = items[k]["body"]
                        flying.append(dict(k=k, x=b.position.x, y=b.position.y, a=b.angle, t0=t))
                        snap = P.snapshot(items, [a for a in alive if a != k])
                        P.apply_pull(sp, items, alive, k, rng, 0, imps=[(j, tuple(im), tuple(pt)) for j, im, pt in imps])
                    pulled += 1
                    events.append(("pull", round(t, 4)))
        if collapse_t is None and pulled > 0:
            mx, mv = P.damage(items, alive, snap)
            if mx > 12 or mv >= 3:
                collapse_t, collapse_n = t, pulled
                events.append(("collapse", round(t, 4)))
        slow = 1.0
        if collapse_t is not None:
            el = t - collapse_t
            slow = 0.3 if el < 2.6 else min(1.0, 0.3 + (el - 2.6) * 0.8)
        elif pulled == NP and t - sched[-1]["pull"] > 0.05:
            slow = 0.3
        clock["t"] = t
        P.step(sp, 1, slow)
        if (collapse_t is not None and t - collapse_t > 4.6) or t > 40:
            break
        bodies = {str(k): [round(items[k]["body"].position.x, 2), round(items[k]["body"].position.y, 2),
                           round(items[k]["body"].angle, 5)] for k in alive}
        fl = []
        for fly in flying:
            e = (t - fly["t0"]) / 0.36
            if e < 1:
                fl.append([fly["k"], round(fly["x"], 2), round(fly["y"], 2), round(fly["a"], 5), round(e, 4)])
        frames.append(dict(t=round(t, 4), pulled=pulled, hl=cur, slow=slow, bodies=bodies, fly=fl))
        t += DT
        f += 1
    return dict(frames=frames, events=events, impacts=impacts, sched=sched, collapse_n=collapse_n,
                collapse_t=collapse_t, duration=t, items={str(k): dict(kind=v["kind"], row=v["row"], col=v["col"],
                                                                       w=v["w"], h=v["h"]) for k, v in items.items()})


def dedupe(frames):
    """frames whose 3D state is identical (rounded) share one render"""
    keys, rid, uniq = {}, [], []
    for fr in frames:
        key = json.dumps([{k: [round(v[0], 1), round(v[1], 1), round(v[2], 4)] for k, v in sorted(fr["bodies"].items())},
                          [[x[0], round(x[4], 3)] for x in fr["fly"]]], sort_keys=True)
        if key not in keys:
            keys[key] = len(uniq)
            uniq.append(len(rid))          # first frame index that has this state
        rid.append(keys[key])
    return rid, uniq


if __name__ == "__main__":
    proj = sys.argv[1]
    cfg = json.load(open(os.path.join(proj, "config.json")))
    seed = cfg["seed"]
    turns, collapsed = P.plan(seed)
    print("seed", seed, "pulls", len(turns), "collapsed", collapsed)
    data = replay([[t[0], t[4]] for t in turns])
    rid, uniq = dedupe(data["frames"])
    data["rid"], data["uniq"] = rid, uniq
    data["phys"] = dict(PPM=P.PPM, TABLE_Y=P.TABLE_Y, CXP=P.CXP, BW=P.BW, BH=P.BH, LEVELS=P.LEVELS, PITCH=P.PITCH,
                        PL_H=P.PL_H)
    os.makedirs(os.path.join(proj, "out"), exist_ok=True)
    json.dump(data, open(os.path.join(proj, "out", "frames.json"), "w"))
    print("frames", len(data["frames"]), "unique renders", len(uniq), "collapse at", data["collapse_n"],
          "duration", round(data["duration"], 2))
