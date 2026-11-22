"""Render the 3D layer (objects + shadow on transparent film) for one shard of unique frames.
python3 tools/render3d.py projects/<slug> --shard k/N [--pct 100] [--spp 16] [--only 0,57,300]
-> projects/<slug>/out/rgba/r_<uid>.png"""
import sys, os, json, math, argparse, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "engine"))
import bpy
import b3d as B, obj3d as O
import mat3d as M3

ap = argparse.ArgumentParser()
ap.add_argument("proj")
ap.add_argument("--shard", default="0/1")
ap.add_argument("--pct", type=int, default=100)
ap.add_argument("--spp", type=int, default=None)
ap.add_argument("--only", default="")
ap.add_argument("--resume", action="store_true")
a = ap.parse_args()
cfg = json.load(open(os.path.join(a.proj, "config.json")))
D = json.load(open(os.path.join(a.proj, "out", "frames.json")))
CAM = D["camera"]
ph = D["phys"]
PPM, TY, CXP = ph["PPM"], ph["TABLE_Y"], ph["CXP"]
outdir = os.path.join(a.proj, "out", "rgba")
os.makedirs(outdir, exist_ok=True)

# ---------------------------------------------------------------- scene
sc = B.reset(samples=a.spp or cfg.get("spp", 16), pct=a.pct)
sc.render.film_transparent = True
sc.cycles.film_transparent_glass = True
sc.render.image_settings.color_mode = "RGBA"
sc.cycles.seed = 7                                   # same noise pattern in every shard
el, az = cfg.get("sun", [60, 85])
B.world_sky(el, az, strength=cfg.get("sky_strength", 0.45), air=1.0, dust=0.3, ozone=3.0)
sc.world.node_tree.nodes["Sky Texture"].sun_disc = False
B.sun(el, az, strength=cfg.get("sun_strength", 5.5), color=(1, 0.95, 0.85), angle=1.2)
g = B.prim_cube((60, 60, 0.01), (0, 0, -0.005), name="catcher")
g.is_shadow_catcher = True

cols = [(0.08, 0.45, 0.15), (0.45, 0.2, 0.05), (0.75, 0.9, 0.85), (0.05, 0.35, 0.1)]
wood = B.wood_material("plank", (0.26, 0.15, 0.075), scale=5, rough=0.7)
can_mats = [M3.can_material(f"can{i}", c) for i, c in enumerate(M3.CAN_COLS)]
block_mats = [B.wood_material(f"blk{i}", c, scale=9, rough=0.65, seed=i * 1.7, contrast=0.8)
              for i, c in enumerate([(0.42, 0.17, 0.045), (0.34, 0.13, 0.03), (0.48, 0.22, 0.07), (0.3, 0.11, 0.03)])]
ice_mat = M3.ice_material()
rigs = {}
import random
rnd = random.Random(cfg["seed"])
for k, it in D["items"].items():
    emp = bpy.data.objects.new("rig" + k, None)
    sc.collection.objects.link(emp)
    w, h = it["w"] / PPM, it["h"] / PPM
    if it["kind"] == "bottle":
        name = f"bt{k}"
        O.bottle((0, 0, 0), cols[(it["row"] + it["col"]) % 4], name=name)
        parts = [bpy.data.objects[n] for n in (name, name + "_lab", name + "_cap")]
    elif it["kind"] == "can":
        ob = B.lathe(M3.can_profile(w / 2, h), "can" + k, 48, (0, 0, 0))
        ob.data.materials.append(rnd.choice(can_mats))
        ob.rotation_euler.z = rnd.uniform(-0.3, 0.3)
        parts = [ob]
    elif it["kind"] == "block":
        ob = B.prim_cube((w, w * 0.5, h), (0, 0, h / 2), bevel=0.0025, name="blk" + k)
        ob.data.materials.append(rnd.choice(block_mats))
        parts = [ob]
    elif it["kind"] == "ice":
        ob = B.prim_cube((w, w * 0.6, h), (0, 0, h / 2), bevel=0.006, segs=3, name="ice" + k)
        ob.data.materials.append(ice_mat)
        parts = [ob]
    else:
        L = it["w"] / PPM
        depth = 0.12 if D["material"] == "bottles" else 0.075
        pl = B.prim_cube((L, depth, it["h"] / PPM), (0, 0, 0), bevel=0.002, name="pl" + k)
        pl.data.materials.append(wood)
        parts = [pl]
    for p in parts:
        p.parent = emp
    rigs[k] = (emp, parts)
if cfg.get("platform"):
    pw, pd = cfg["platform"]
    deck = B.wood_material("deck", (0.2, 0.12, 0.065), scale=2.5, rough=0.75)
    n = int(pd / 0.14)
    for i in range(n):
        y = -pd / 2 + (i + 0.5) * pd / n
        bd = B.prim_cube((pw, pd / n - 0.008, 0.04), (0, y, -0.02), bevel=0.004, name=f"deck{i}")
        bd.data.materials.append(B.wood_material(f"deck{i}", (0.22 + 0.03 * math.sin(i * 2.1), 0.13, 0.07),
                                                 scale=2.5, rough=0.75, seed=i * 1.3))
    for x in (-pw / 2 + 0.06, pw / 2 - 0.06):
        for y in (-pd / 2 + 0.06, pd / 2 - 0.06):
            B.prim_cube((0.08, 0.08, 1.2), (x, y, -0.62), name="post").data.materials.append(deck)

cam = B.camera((0.0, -CAM["d"], CAM["h"]), (0.0, 0.0, CAM["h"]), lens=CAM["lens"])
cam.data.sensor_fit = "VERTICAL"
cam.data.sensor_height = 36
cam.data.shift_y = CAM["shift_y"]


def set_state(fr):
    vis = set()
    for k, (x, y, ang) in fr["bodies"].items():
        emp, parts = rigs[k]
        emp.location = ((x - CXP) / PPM, 0.0, (TY - y) / PPM)
        emp.rotation_euler = (0.0, ang, 0.0)
        vis.add(k)
    for k, x, y, ang, e in fr["fly"]:
        k = str(k)
        emp, parts = rigs[k]
        ee = e * e
        emp.location = ((x - CXP) / PPM, -1.9 * ee, (TY - y) / PPM + 0.06 * ee)
        emp.rotation_euler = (0.0, ang, 0.0)
        vis.add(k)
    for k, (emp, parts) in rigs.items():
        for p in parts:
            p.hide_render = k not in vis


uniq = D["uniq"]
k, n = (int(v) for v in a.shard.split("/"))
todo = [int(v) for v in a.only.split(",")] if a.only else list(range(len(uniq)))
mine = [u for u in todo if u % n == k]
t0 = time.time()
for i, u in enumerate(mine):
    path = os.path.join(outdir, f"r_{u:04d}.png")
    if a.resume and os.path.exists(path):
        continue
    set_state(D["frames"][uniq[u]])
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print(f"[{i + 1}/{len(mine)}] r_{u:04d} {time.time() - t0:.0f}s", flush=True)
print("shard done", k, n, len(mine), f"{time.time() - t0:.0f}s")
