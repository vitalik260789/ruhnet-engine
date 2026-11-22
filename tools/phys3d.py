"""2D physics (pymunk, XZ plane) for a tower of bottles with planks between levels.
Units: px, 1 m = PPM px, y grows downwards. Body origin of a bottle = centre of its base."""
import copy, math
import numpy as np
import pymunk

PPM = 400.0
BW, BH = 0.073 * PPM, 0.2875 * PPM        # bottle width / height
SHOULDER = 0.20 * PPM                     # body part height, neck above
NECK_W = 0.03 * PPM
PITCH = 0.11 * PPM
PL_H = 0.018 * PPM
LEVELS = [6, 5, 4, 3, 2, 1]
TABLE_Y = 1000.0
CXP = 0.0
GRAVITY = 9.81 * PPM
SUB = 8
FDT = 1 / 30


def plank_len(n):
    return (n - 1) * PITCH + 0.11 * PPM


def _bottle(sp, x, ybase):
    b = pymunk.Body()
    b.position = (x, ybase)
    hw, nw = BW / 2, NECK_W / 2
    body = pymunk.Poly(b, [(-hw, 0), (hw, 0), (hw, -SHOULDER), (-hw, -SHOULDER)], radius=0.3)
    neck = pymunk.Poly(b, [(-nw, -SHOULDER), (nw, -SHOULDER), (nw, -BH), (-nw, -BH)], radius=0.3)
    for s, d in ((body, 0.4 / (BW * SHOULDER)), (neck, 0.03 / (NECK_W * (BH - SHOULDER)))):
        s.density = d * 1000
        s.friction = 0.6
        s.elasticity = 0.05
    sp.add(b, body, neck)
    return b, [body, neck]


def _plank(sp, x, ycen, L):
    b = pymunk.Body()
    b.position = (x, ycen)
    s = pymunk.Poly.create_box(b, (L - 1, PL_H - 0.4), radius=0.4)
    s.density = 0.65 / (L * PL_H) * 1000 * (L / plank_len(6))
    s.friction = 0.7
    s.elasticity = 0.03
    sp.add(b, s)
    return b, [s]


def build():
    sp = pymunk.Space()
    sp.gravity = (0, GRAVITY)
    sp.iterations = 50
    sp.collision_slop = 0.2
    floor = pymunk.Segment(sp.static_body, (-4000, TABLE_Y), (4000, TABLE_Y), 0)
    floor.friction = 0.9
    sp.add(floor)
    items = {}
    k = 0
    y = TABLE_Y
    for r, n in enumerate(LEVELS):
        for i in range(n):
            x = CXP + (i - (n - 1) / 2) * PITCH
            b, s = _bottle(sp, x, y - 0.05)
            items[k] = dict(body=b, shapes=s, row=r, col=i, kind="bottle", w=BW, h=BH)
            k += 1
        y -= BH + 0.1
        if r < len(LEVELS) - 1:
            L = plank_len(n)
            b, s = _plank(sp, CXP, y - PL_H / 2, L)
            items[k] = dict(body=b, shapes=s, row=r, col=-1, kind="plank", w=L, h=PL_H)
            k += 1
            y -= PL_H + 0.1
    for it in items.values():
        for s in it["shapes"]:
            s.kind_ = it["kind"]
    return sp, items


def step(sp, frames=1, slow=1.0):
    for _ in range(frames):
        for _ in range(SUB):
            sp.step(FDT * slow / SUB)


def snapshot(items, alive):
    return {k: (tuple(items[k]["body"].position), items[k]["body"].angle) for k in alive}


def damage(items, alive, snap):
    mx, moved = 0.0, 0
    for k in alive:
        if k not in snap:
            continue
        p0, a0 = snap[k]
        b = items[k]["body"]
        arm = 60 if items[k]["kind"] == "bottle" else 120
        d = math.hypot(b.position.x - p0[0], b.position.y - p0[1]) + abs(b.angle - a0) * arm
        mx = max(mx, d)
        if d > 5:
            moved += 1
    return mx, moved


def plank_above(items, alive, k):
    r = items[k]["row"]
    return [j for j in alive if items[j]["kind"] == "plank" and items[j]["row"] == r]


def apply_pull(sp, items, alive, k, rng, strength, imps=None):
    up = plank_above(items, alive, k)
    cx = items[k]["body"].position.x
    sp.remove(items[k]["body"], *items[k]["shapes"])
    alive.remove(k)
    if imps is None:
        imps = []
        for j in up:
            bj = items[j]["body"]
            m = bj.mass
            imps.append((j, (float(rng.normal(0, strength) * m), float(rng.normal(0, strength * 0.3) * m)),
                         (float(cx - bj.position.x), 0.0)))
    for j, imp, pt in imps:
        if j in alive:
            items[j]["body"].apply_impulse_at_local_point(imp, pt)
    return imps


def lookahead(sp, items, alive, k, rng, strength, frames=40):
    sp2, it2 = copy.deepcopy((sp, items))
    al2 = list(alive)
    snap = snapshot(it2, [a for a in al2 if a != k])
    apply_pull(sp2, it2, al2, k, rng, strength)
    step(sp2, frames)
    return damage(it2, al2, snap)


def plan(seed, verbose=False, max_turns=40):
    rng = np.random.default_rng(seed)
    sp, items = build()
    alive = list(items.keys())
    step(sp, 45)
    turns = []
    top = len(LEVELS) - 1
    for turn in range(max_turns):
        snap = snapshot(items, alive)
        cands = [k for k in alive if items[k]["kind"] == "bottle" and items[k]["row"] < top]
        if not cands:
            break
        rng.shuffle(cands)
        safe = []
        for k in cands[:14]:
            mx, mv = lookahead(sp, items, alive, k, rng, strength=25)
            if mx < 4:
                safe.append((mx, k))
        if safe:
            safe.sort(key=lambda s: (items[s[1]]["row"] + rng.uniform(0, 3)))
            k = safe[0][1]
        else:
            k = cands[0]
        row = items[k]["row"]
        imps = apply_pull(sp, items, alive, k, rng, strength=60)
        step(sp, 40)
        mx, mv = damage(items, alive, snap)
        turns.append((k, row, round(mx, 1), mv, imps))
        if verbose:
            print(turn + 1, k, "row", row, "dmg", round(mx, 1), mv, "safe", len(safe))
        if mx > 25 or mv >= 4:
            return turns, True
    return turns, False


if __name__ == "__main__":
    import sys
    sp, items = build()
    alive = list(items.keys())
    snap = snapshot(items, alive)
    step(sp, 60)
    print("settle damage", damage(items, alive, snap), "bodies", len(items))
    for seed in range(int(sys.argv[1]), int(sys.argv[2])):
        t, col = plan(seed)
        print("seed", seed, "pulls", len(t), "collapsed", col, "lastrow", t[-1][1], flush=True)
