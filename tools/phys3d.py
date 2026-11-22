"""2D physics (pymunk, XZ plane) for the 3D reels. Units: px, 1 m = PPM px, y grows downwards.
Every body's origin is the centre of its base (planks: their centre).
Materials:
  bottles - tower of bottles with planks between levels (necks are narrow)
  cans    - pyramid of cans with boards between levels
  blocks  - running-bond pyramid of wooden blocks
  ice     - running-bond pyramid of ice bricks (slippery)"""
import copy, math
import numpy as np
import pymunk

MATS = {
    "bottles": dict(kind="bottle", style="planked", PPM=400, w=0.073, h=0.2875, shoulder=0.20, neck=0.03,
                    pitch=0.11, plank=0.018, levels=[6, 5, 4, 3, 2, 1], fr=0.6, mass=0.4),
    "cans": dict(kind="can", style="planked", PPM=850, w=0.066, h=0.122, pitch=0.081, plank=0.016,
                 levels=[7, 6, 5, 4, 3, 2, 1], fr=0.7, mass=0.35),
    "blocks": dict(kind="block", style="bond", PPM=800, w=0.14, h=0.078, gap=0.002, rows=8, fr=0.75, mass=0.5),
    "ice": dict(kind="ice", style="bond", PPM=1600, w=0.07, h=0.05, gap=0.0015, rows=7, fr=0.45, mass=0.15),
}
M = None
PPM = TABLE_Y = CXP = GRAVITY = None
BW = BH = PITCH = PL_H = None
LEVELS = None
SUB = 8
FDT = 1 / 30


def set_material(name):
    global M, PPM, TABLE_Y, CXP, GRAVITY, BW, BH, PITCH, PL_H, LEVELS
    M = dict(MATS[name]); M["name"] = name
    PPM = M["PPM"]; TABLE_Y = 1000.0; CXP = 0.0; GRAVITY = 9.81 * PPM
    BW, BH = M["w"] * PPM, M["h"] * PPM
    PITCH = M.get("pitch", M["w"] + M.get("gap", 0)) * PPM
    PL_H = M.get("plank", 0) * PPM
    LEVELS = M["levels"] if M["style"] == "planked" else [M["rows"] - r for r in range(M["rows"])]


set_material("bottles")


def plank_len(n):
    return (n - 1) * PITCH + BW * 1.5


def _piece(sp, x, ybase):
    b = pymunk.Body()
    b.position = (x, ybase)
    hw = BW / 2
    if M["kind"] == "bottle":
        sh, nw = M["shoulder"] * PPM, M["neck"] * PPM / 2
        parts = [([(-hw, 0), (hw, 0), (hw, -sh), (-hw, -sh)], 0.92), ([(-nw, -sh), (nw, -sh), (nw, -BH), (-nw, -BH)], 0.08)]
    else:
        parts = [([(-hw, 0), (hw, 0), (hw, -BH), (-hw, -BH)], 1.0)]
    shapes = []
    for verts, mfrac in parts:
        s = pymunk.Poly(b, verts, radius=0.3)
        area = abs(pymunk.Poly(None, verts).area)
        s.density = M["mass"] * mfrac / area * 1000
        s.friction = M["fr"]
        s.elasticity = 0.05
        shapes.append(s)
    sp.add(b, *shapes)
    return b, shapes


def _plank(sp, x, ycen, L):
    b = pymunk.Body()
    b.position = (x, ycen)
    s = pymunk.Poly.create_box(b, (L - 1, PL_H - 0.4), radius=0.4)
    s.density = (0.65 * L / plank_len(6)) / (L * PL_H) * 1000
    s.friction = 0.7
    s.elasticity = 0.03
    sp.add(b, s)
    return b, [s]


def build():
    sp = pymunk.Space()
    sp.gravity = (0, GRAVITY)
    sp.iterations = 50
    sp.collision_slop = 0.2
    floor = pymunk.Segment(sp.static_body, (-6000, TABLE_Y), (6000, TABLE_Y), 0)
    floor.friction = 0.9
    sp.add(floor)
    items, k, y = {}, 0, TABLE_Y
    for r, n in enumerate(LEVELS):
        for i in range(n):
            x = CXP + (i - (n - 1) / 2) * PITCH
            b, s = _piece(sp, x, y - 0.05)
            items[k] = dict(body=b, shapes=s, row=r, col=i, kind=M["kind"], w=BW, h=BH)
            k += 1
        y -= BH + 0.1
        if M["style"] == "planked" and r < len(LEVELS) - 1:
            L = plank_len(n)
            b, s = _plank(sp, CXP, y - PL_H / 2, L)
            items[k] = dict(body=b, shapes=s, row=r, col=-1, kind="plank", w=L, h=PL_H)
            k += 1
            y -= PL_H + 0.1
    for it in items.values():
        for s in it["shapes"]:
            s.kind_ = it["kind"]
    return sp, items


def tower_size():
    """width and height of the built tower in metres"""
    h = len(LEVELS) * M["h"] + (len(LEVELS) - 1) * M.get("plank", 0)
    w = max(plank_len(LEVELS[0]) / PPM if M["style"] == "planked" else 0, LEVELS[0] * PITCH / PPM)
    return w, h


def step(sp, frames=1, slow=1.0):
    for _ in range(frames):
        for _ in range(SUB):
            sp.step(FDT * slow / SUB)


def snapshot(items, alive):
    return {k: (tuple(items[k]["body"].position), items[k]["body"].angle) for k in alive}


def damage(items, alive, snap):
    """displacement in units of 'one object = 100 px' so thresholds work for every material"""
    norm = 100.0 / max(BW, BH)
    mx, moved = 0.0, 0
    for k in alive:
        if k not in snap:
            continue
        p0, a0 = snap[k]
        b = items[k]["body"]
        arm = 60 if items[k]["kind"] != "plank" else 120
        d = math.hypot(b.position.x - p0[0], b.position.y - p0[1]) * norm + abs(b.angle - a0) * arm
        mx = max(mx, d)
        if d > 5:
            moved += 1
    return mx, moved


def above(items, alive, k):
    r = items[k]["row"]
    if M["style"] == "planked":
        return [j for j in alive if items[j]["kind"] == "plank" and items[j]["row"] == r]
    x = items[k]["body"].position.x
    return [j for j in alive if items[j]["row"] == r + 1 and abs(items[j]["body"].position.x - x) < BW * 1.05]


def apply_pull(sp, items, alive, k, rng, strength, imps=None):
    up = above(items, alive, k)
    cx = items[k]["body"].position.x
    sp.remove(items[k]["body"], *items[k]["shapes"])
    alive.remove(k)
    sc = max(BW, BH) / 100.0
    if imps is None:
        imps = []
        for j in up:
            bj = items[j]["body"]
            m = bj.mass
            pt = (float(cx - bj.position.x), 0.0) if items[j]["kind"] == "plank" else (0.0, float(-BH / 2))
            imps.append((j, (float(rng.normal(0, strength) * m * sc), float(rng.normal(0, strength * 0.3) * m * sc)), pt))
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
        cands = [k for k in alive if items[k]["kind"] != "plank" and items[k]["row"] < top]
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
    set_material(sys.argv[1])
    sp, items = build()
    alive = list(items.keys())
    snap = snapshot(items, alive)
    step(sp, 60)
    print(sys.argv[1], "settle damage", damage(items, alive, snap), "bodies", len(items), "size m", tower_size())
    for seed in range(int(sys.argv[2]), int(sys.argv[3])):
        t, col = plan(seed)
        print("seed", seed, "pulls", len(t), "collapsed", col, "lastrow", t[-1][1], flush=True)
