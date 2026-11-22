"""Render the 3D layer (objects + shadow on transparent film) for one shard of unique frames.
python3 tools/render3d.py projects/<slug> --shard k/N [--pct 100] [--spp 16] [--only 0,57,300]
-> projects/<slug>/out/rgba/r_<uid>.png"""
import sys, os, json, math, argparse, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "engine"))
import bpy
import b3d as B, obj3d as O

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
el, az = cfg["sun"]
B.world_sky(el, az, strength=0.45, air=1.0, dust=0.3, ozone=3.0)
sc.world.node_tree.nodes["Sky Texture"].sun_disc = False
B.sun(el, az, strength=5.5, color=(1, 0.95, 0.85), angle=1.2)
g = B.prim_cube((60, 60, 0.01), (0, 0, -0.005), name="catcher")
g.is_shadow_catcher = True

cols = [(0.08, 0.45, 0.15), (0.45, 0.2, 0.05), (0.75, 0.9, 0.85), (0.05, 0.35, 0.1)]
wood = B.wood_material("plank", (0.42, 0.27, 0.14), scale=5, rough=0.7)
rigs = {}
for k, it in D["items"].items():
    emp = bpy.data.objects.new("rig" + k, None)
    sc.collection.objects.link(emp)
    if it["kind"] == "bottle":
        name = f"bt{k}"
        O.bottle((0, 0, 0), cols[(it["row"] + it["col"]) % 4], name=name)
        parts = [bpy.data.objects[n] for n in (name, name + "_lab", name + "_cap")]
    else:
        L = it["w"] / PPM
        pl = B.prim_cube((L, 0.12, it["h"] / PPM), (0, 0, 0), bevel=0.002, name="pl" + k)
        pl.data.materials.append(wood)
        parts = [pl]
    for p in parts:
        p.parent = emp
    rigs[k] = (emp, parts)

cam = B.camera((0.0, -cfg["cam_d"], cfg["cam_h"]), (0.0, 0.0, cfg["cam_h"]), lens=cfg["lens"])
cam.data.sensor_fit = "VERTICAL"
cam.data.sensor_height = 36


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
