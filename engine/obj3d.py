"""3D props for the How-Many concepts: cards, blocks, bottles, ice cubes, palms, rocks, clouds, ocean."""
import math
import numpy as np
import bpy, bmesh
from mathutils import Vector, Matrix
import b3d as B

rng = np.random.default_rng(12)


# ---------------------------------------------------------------- card textures (PNG)
def make_card_pngs(n=26):
    import cv2, os
    os.makedirs("tex", exist_ok=True)
    from concepts import card_face, card_back
    paths = []
    ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "A", "K", "Q", "J"]
    for i in range(n):
        f = card_face(ranks[i % 13], "hdsc"[(i * 7) % 4])
        img = np.dstack([f[..., :3], f[..., 3:] * 255]).astype(np.uint8)
        img = cv2.resize(img, (440, 640), interpolation=cv2.INTER_CUBIC)
        p = f"tex/card_{i}.png"
        cv2.imwrite(p, cv2.cvtColor(img, cv2.COLOR_RGBA2BGRA))
        paths.append(p)
    bk = card_back()
    img = cv2.resize(bk[..., :3].astype(np.uint8), (440, 640), interpolation=cv2.INTER_CUBIC)
    cv2.imwrite("tex/card_back.png", cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
    return paths, "tex/card_back.png"


def card_object(face_png, back_png, name="card", w=0.063, h=0.088):
    """thin card: plane with front image (-Y facing) and back image."""
    me = bpy.data.meshes.new(name)
    t = 0.0004
    v = [(-w / 2, -t, -h / 2), (w / 2, -t, -h / 2), (w / 2, -t, h / 2), (-w / 2, -t, h / 2),
         (-w / 2, t, -h / 2), (w / 2, t, -h / 2), (w / 2, t, h / 2), (-w / 2, t, h / 2)]
    f = [(0, 1, 2, 3), (5, 4, 7, 6), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    me.from_pydata(v, [], f)
    uv = me.uv_layers.new()
    uvs = {0: [(0, 0), (1, 0), (1, 1), (0, 1)], 1: [(0, 0), (1, 0), (1, 1), (0, 1)]}
    for pi, p in enumerate(me.polygons):
        for k, li in enumerate(p.loop_indices):
            uv.data[li].uv = uvs.get(pi, [(0.02, 0.02)] * 4)[k]
        p.material_index = 0 if pi == 0 else (1 if pi == 1 else 2)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    mf = _img_mat(face_png, "face_" + name)
    mb = _img_mat(back_png, "back")
    me.materials.append(mf)
    me.materials.append(mb)
    me.materials.append(B.mat_principled("edge", (0.92, 0.92, 0.9), rough=0.5))
    return ob


_imgcache = {}


def _img_mat(path, name):
    if path in _imgcache:
        return _imgcache[path]
    m = B.image_material(name, path, rough=0.32, coat=0.4)
    _imgcache[path] = m
    return m


def card_house(levels=4, pitch=0.13, lean=17, base=(0, 0, 0)):
    faces, back = make_card_pngs()
    w, h = 0.063, 0.088
    a = math.radians(lean)
    cz = h * math.cos(a)
    half_dx = h * math.sin(a) / 2 + 0.0015
    z = base[2]
    k = 0
    for lv in range(levels):
        n = levels - lv
        for i in range(n):
            ax = base[0] + (i - (n - 1) / 2) * pitch
            for side in (-1, 1):
                ob = card_object(faces[k % len(faces)], back, f"c{k}")
                k += 1
                # card plane is XZ (normal -Y). lean around Y so tops meet at ax
                ob.rotation_euler = (0, -side * a, 0)
                ob.location = (ax + side * half_dx, base[1] + side * 0.002, z + cz / 2)
        z += cz
        if lv < levels - 1:
            for i in range(n - 1):
                ax = base[0] + (i - (n - 2) / 2) * pitch
                ob = card_object(back, back, f"f{k}")
                k += 1
                ob.rotation_euler = (math.radians(90), 0, math.radians(90))
                ob.location = (ax, base[1], z + 0.0006)
                ob.scale = (1.0, 1.0, 1.0)
            # floor cards: lying flat; card long side (h) along X to bridge apexes
        z += 0.0012


# ---------------------------------------------------------------- jenga-like tower
def block_tower(layers=16, base=(0, 0, 0), pulled=None, shifted=None):
    pulled = pulled or {}
    shifted = shifted or {}
    L, Wd, Hh = 0.075, 0.025, 0.015
    mats = [B.wood_material(f"blk{i}", (0.78 + rng.uniform(-.05, .05), 0.52 + rng.uniform(-.05, .05), 0.26),
                            scale=rng.uniform(70, 110), seed=float(i), rough=0.6, distortion=1.8, contrast=0.86) for i in range(6)]
    for l in range(layers):
        z = base[2] + Hh / 2 + l * (Hh + 0.0002)
        for i in range(3):
            if pulled.get(l) == i:
                continue
            off = (i - 1) * (Wd + 0.0004)
            sh = shifted.get((l, i), 0.0)
            if l % 2 == 0:   # long axis along Y (blocks seen end-on)
                loc = (base[0] + off, base[1] + sh, z); size = (Wd, L, Hh)
            else:            # long axis along X
                loc = (base[0] + sh, base[1] + off, z); size = (L, Wd, Hh)
            ob = B.prim_cube(size, loc, rot=(0, 0, rng.normal(0, 0.012)), bevel=0.0012, segs=2, name=f"b{l}{i}")
            B.add_obj(ob, mats[rng.integers(len(mats))])


# ---------------------------------------------------------------- bottles
def bottle(loc, col, label_col=(0.9, 0.85, 0.72), name="bottle"):
    prof = [(0.0, 0.002), (0.030, 0.0), (0.0355, 0.004), (0.0365, 0.015), (0.0365, 0.16), (0.034, 0.18),
            (0.024, 0.2), (0.0135, 0.215), (0.0125, 0.27), (0.0145, 0.272), (0.0145, 0.285), (0.0115, 0.287),
            (0.0105, 0.282), (0.0105, 0.22), (0.022, 0.2), (0.032, 0.18), (0.034, 0.16), (0.034, 0.015), (0.03, 0.006), (0.0, 0.008)]
    ob = B.lathe(prof, name, 48, loc)
    B.add_obj(ob, B.glass_material("g_" + name, col, rough=0.03, ior=1.5))
    # label: thin cylinder sleeve
    lab = B.lathe([(0.0369, 0.06), (0.0369, 0.125)], name + "_lab", 48, loc)
    m = B.mat_principled("lab_" + name, label_col, rough=0.6)
    N, Lk, b = B.nodes(m)
    tc = N.new("ShaderNodeTexCoord"); sep = N.new("ShaderNodeSeparateXYZ"); Lk.new(tc.outputs["Object"], sep.inputs[0])
    st = N.new("ShaderNodeMath"); st.operation = "COMPARE"; st.inputs[1].default_value = 0.0925; st.inputs[2].default_value = 0.008
    Lk.new(sep.outputs["Z"], st.inputs[0])
    mx = N.new("ShaderNodeMix"); mx.data_type = "RGBA"
    Lk.new(st.outputs[0], mx.inputs[0]); mx.inputs[6].default_value = (*label_col, 1); mx.inputs[7].default_value = (0.6, 0.05, 0.05, 1)
    Lk.new(mx.outputs[2], b.inputs["Base Color"])
    B.add_obj(lab, m)
    # cap
    cap = B.lathe([(0.0, 0.287), (0.0152, 0.287), (0.0152, 0.272), (0.0, 0.272)], name + "_cap", 32, loc)
    B.add_obj(cap, B.mat_principled("cap", (0.8, 0.65, 0.2), rough=0.3, metal=1.0))
    return ob


def bottle_tower(base=(0, 0, 0)):
    cols = [(0.08, 0.45, 0.15), (0.45, 0.2, 0.05), (0.75, 0.9, 0.85), (0.05, 0.35, 0.1)]
    wood = B.wood_material("plank", (0.68, 0.48, 0.28), scale=5)
    z = base[2]
    pitch = 0.095
    for lv, n in enumerate((4, 3, 2, 1)):
        for i in range(n):
            x = base[0] + (i - (n - 1) / 2) * pitch
            bottle((x, base[1], z), cols[(i + lv) % 4], name=f"bt{lv}{i}")
        z += 0.2875
        if n > 1:
            pw = (n - 1) * pitch + 0.11
            B.add_obj(B.prim_cube((pw, 0.12, 0.018), (base[0], base[1], z + 0.009), bevel=0.002, name=f"pl{lv}"), wood)
            z += 0.018


# ---------------------------------------------------------------- ice cubes
def ice_pyramid(rows=6, s=0.04, base=(0, 0, 0)):
    m = bpy.data.materials.new("ice")
    m.use_nodes = True
    N, L, b = B.nodes(m)
    b.inputs["Base Color"].default_value = (0.82, 0.93, 1.0, 1)
    b.inputs["Transmission Weight"].default_value = 1.0
    b.inputs["IOR"].default_value = 1.31
    b.inputs["Roughness"].default_value = 0.06
    nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 60; nz.inputs["Detail"].default_value = 6
    bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.08
    L.new(nz.outputs["Fac"], bump.inputs["Height"]); L.new(bump.outputs["Normal"], b.inputs["Normal"])
    # faint frosty volume
    vol = N.new("ShaderNodeVolumeAbsorption"); vol.inputs["Color"].default_value = (0.75, 0.9, 1.0, 1); vol.inputs["Density"].default_value = 4
    L.new(vol.outputs[0], N["Material Output"].inputs["Volume"])
    for r in range(rows):
        n = rows - r
        for i in range(n):
            x = base[0] + (i - (n - 1) / 2) * (s + 0.0015)
            ob = B.prim_cube((s, s, s), (x, base[1] + rng.normal(0, 0.001), base[2] + s / 2 + r * (s + 0.0004)),
                             rot=(0, 0, rng.normal(0, 0.04)), bevel=0.005, segs=3, name=f"ice{r}{i}")
            B.add_obj(ob, m)


# ---------------------------------------------------------------- palms (realistic-ish geometry)
def palm(base, height=9.0, lean=(0.25, 0.1), seed=0, n_fronds=14):
    r = np.random.default_rng(seed)
    bm = bmesh.new()
    # trunk: curved tube with ring bulges
    segs, ring = 60, 12
    pts = []
    for k in range(segs + 1):
        u = k / segs
        pts.append(Vector((base[0] + lean[0] * height * u ** 1.8, base[1] + lean[1] * height * u ** 1.8, base[2] + height * u)))
    verts_rings = []
    for k, p in enumerate(pts):
        u = k / segs
        rad = 0.2 * (1 - 0.45 * u) * (1 + 0.06 * (math.sin(u * 140) > 0.6))
        t = (pts[min(k + 1, segs)] - pts[max(k - 1, 0)]).normalized()
        nrm = t.orthogonal().normalized()
        bin_ = t.cross(nrm)
        ringv = []
        for j in range(ring):
            a = 2 * math.pi * j / ring
            ringv.append(bm.verts.new(p + (nrm * math.cos(a) + bin_ * math.sin(a)) * rad))
        verts_rings.append(ringv)
    for k in range(segs):
        for j in range(ring):
            bm.faces.new((verts_rings[k][j], verts_rings[k][(j + 1) % ring], verts_rings[k + 1][(j + 1) % ring], verts_rings[k + 1][j]))
    trunk_me = bpy.data.meshes.new("trunk")
    bm.to_mesh(trunk_me)
    bm.free()
    for p in trunk_me.polygons:
        p.use_smooth = True
    tob = bpy.data.objects.new("trunk", trunk_me)
    bpy.context.scene.collection.objects.link(tob)
    tm = B.mat_principled("bark", (0.42, 0.34, 0.25), rough=0.95)
    N, L, b = B.nodes(tm)
    tc = N.new("ShaderNodeTexCoord")
    wv = N.new("ShaderNodeTexWave"); wv.bands_direction = "Z"; wv.inputs["Scale"].default_value = 18; wv.inputs["Distortion"].default_value = 3
    L.new(tc.outputs["Object"], wv.inputs["Vector"])
    cr = N.new("ShaderNodeValToRGB"); cr.color_ramp.elements[0].color = (0.16, 0.1, 0.05, 1); cr.color_ramp.elements[1].color = (0.45, 0.32, 0.18, 1)
    L.new(wv.outputs["Fac"], cr.inputs["Fac"]); L.new(cr.outputs["Color"], b.inputs["Base Color"])
    bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.6
    L.new(wv.outputs["Fac"], bump.inputs["Height"]); L.new(bump.outputs["Normal"], b.inputs["Normal"])
    B.add_obj(tob, tm)
    top = pts[-1]
    # fronds
    lm = bpy.data.materials.new("leaf")
    lm.use_nodes = True
    N, L, b = B.nodes(lm)
    b.inputs["Base Color"].default_value = (0.08, 0.3, 0.05, 1)
    b.inputs["Roughness"].default_value = 0.55
    b.inputs["Subsurface Weight"].default_value = 0.0
    oi = N.new("ShaderNodeObjectInfo")
    gc = N.new("ShaderNodeNewGeometry")
    cr = N.new("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].color = (0.05, 0.22, 0.03, 1); cr.color_ramp.elements[1].color = (0.25, 0.42, 0.08, 1)
    nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 3
    L.new(nz.outputs["Fac"], cr.inputs["Fac"])
    L.new(cr.outputs["Color"], b.inputs["Base Color"])
    tl = N.new("ShaderNodeBsdfTranslucent"); tl.inputs["Color"].default_value = (0.25, 0.45, 0.05, 1)
    mixs = N.new("ShaderNodeMixShader"); mixs.inputs[0].default_value = 0.3
    L.new(b.outputs[0], mixs.inputs[1]); L.new(tl.outputs[0], mixs.inputs[2])
    L.new(mixs.outputs[0], N["Material Output"].inputs["Surface"])
    bm = bmesh.new()
    for f in range(n_fronds):
        az = 2 * math.pi * f / n_fronds + r.uniform(-0.2, 0.2)
        up = r.uniform(0.15, 0.75) if f % 3 else r.uniform(-0.3, 0.2)
        length = r.uniform(3.2, 4.4)
        d = Vector((math.cos(az), math.sin(az), 0))
        side = Vector((-math.sin(az), math.cos(az), 0))
        spine = []
        NS = 34
        for k in range(NS + 1):
            u = k / NS
            droop = (u ** 2) * 1.6 * (1 - up * 0.5)
            spine.append(top + d * length * u * 0.95 + Vector((0, 0, length * up * u * 0.5 - droop)))
        for k in range(1, NS):
            u = k / NS
            ll = (0.95 * math.sin(math.pi * min(1, u * 1.08)) * (1 - 0.3 * u) + 0.1) * r.uniform(0.85, 1.1)
            for sgn in (-1, 1):
                p0 = spine[k]
                tip = p0 + side * sgn * ll + d * ll * 0.35 + Vector((0, 0, -ll * 0.45))
                p1 = spine[k + 1]
                mid = (p0 + p1) / 2
                v1 = bm.verts.new(p0); v2 = bm.verts.new(p0 + (p1 - p0) * 0.55)
                v3 = bm.verts.new(tip + (p1 - p0) * 0.25 + Vector((0, 0, -0.04)))
                v4 = bm.verts.new(tip)
                bm.faces.new((v1, v2, v3, v4))
        # spine as thin strip
        for k in range(NS):
            a, c = spine[k], spine[k + 1]
            w = Vector((0, 0, 0.03))
            bm.faces.new((bm.verts.new(a - w), bm.verts.new(c - w), bm.verts.new(c + w), bm.verts.new(a + w)))
    fme = bpy.data.meshes.new("fronds")
    bm.to_mesh(fme)
    bm.free()
    fob = bpy.data.objects.new("fronds", fme)
    bpy.context.scene.collection.objects.link(fob)
    B.add_obj(fob, lm)
    # coconuts
    cm = B.mat_principled("coco", (0.25, 0.18, 0.08), rough=0.7)
    for k in range(5):
        a = 2 * math.pi * k / 5
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.14, location=top + Vector((math.cos(a) * 0.22, math.sin(a) * 0.22, -0.25)))
        bpy.ops.object.shade_smooth()
        B.add_obj(bpy.context.active_object, cm)


# ---------------------------------------------------------------- rock
def rock(loc, size, seed=0, color=(0.36, 0.34, 0.32)):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=6, radius=1, location=loc)
    ob = bpy.context.active_object
    ob.scale = size
    tex = bpy.data.textures.new(f"rk{seed}", "CLOUDS")
    tex.noise_scale = 0.6
    d = ob.modifiers.new("disp", "DISPLACE"); d.texture = tex; d.strength = 0.35
    tex3 = bpy.data.textures.new(f"rk3{seed}", "CLOUDS"); tex3.noise_scale = 0.08
    d3 = ob.modifiers.new("disp3", "DISPLACE"); d3.texture = tex3; d3.strength = 0.03
    tex2 = bpy.data.textures.new(f"rk2{seed}", "VORONOI")
    tex2.noise_scale = 0.35
    d2 = ob.modifiers.new("disp2", "DISPLACE"); d2.texture = tex2; d2.strength = -0.15
    bpy.ops.object.shade_smooth()
    m = B.mat_principled(f"rock{seed}", color, rough=0.85)
    N, L, b = B.nodes(m)
    nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 25; nz.inputs["Detail"].default_value = 15
    nz.inputs["Roughness"].default_value = 0.7
    cr = N.new("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].color = (color[0] * 0.45, color[1] * 0.45, color[2] * 0.45, 1); cr.color_ramp.elements[1].color = (*color, 1)
    lic = cr.color_ramp.elements.new(0.75); lic.color = (0.45, 0.48, 0.3, 1)
    L.new(nz.outputs["Fac"], cr.inputs["Fac"]); L.new(cr.outputs["Color"], b.inputs["Base Color"])
    bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.9
    L.new(nz.outputs["Fac"], bump.inputs["Height"]); L.new(bump.outputs["Normal"], b.inputs["Normal"])
    B.add_obj(ob, m)
    return ob


# ---------------------------------------------------------------- world clouds (cheap, in sky shader)
def add_sky_clouds(nt, sky, bg, out, cover=0.5, scale=3.0, color=(1, 1, 1), strength=1.0, low=0.02, high=0.45):
    N, L = nt.nodes, nt.links
    tc = N.new("ShaderNodeTexCoord")
    sep = N.new("ShaderNodeSeparateXYZ"); L.new(tc.outputs["Generated"], sep.inputs[0])
    # project direction onto a plane: (x/z, y/z)
    dx = N.new("ShaderNodeMath"); dx.operation = "DIVIDE"; dz = N.new("ShaderNodeMath"); dz.operation = "DIVIDE"
    zc = N.new("ShaderNodeMath"); zc.operation = "MAXIMUM"; zc.inputs[1].default_value = 0.03
    L.new(sep.outputs["Z"], zc.inputs[0])
    L.new(sep.outputs["X"], dx.inputs[0]); L.new(zc.outputs[0], dx.inputs[1])
    L.new(sep.outputs["Y"], dz.inputs[0]); L.new(zc.outputs[0], dz.inputs[1])
    cmb = N.new("ShaderNodeCombineXYZ"); L.new(dx.outputs[0], cmb.inputs[0]); L.new(dz.outputs[0], cmb.inputs[1])
    nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = scale; nz.inputs["Detail"].default_value = 10
    nz.inputs["Roughness"].default_value = 0.6
    L.new(cmb.outputs[0], nz.inputs["Vector"])
    cr = N.new("ShaderNodeMapRange")
    cr.inputs["From Min"].default_value = 0.62 - cover * 0.2
    cr.inputs["From Max"].default_value = 0.62 - cover * 0.2 + 0.14
    L.new(nz.outputs["Fac"], cr.inputs["Value"])
    # fade near horizon / zenith
    hz = N.new("ShaderNodeMapRange"); hz.inputs["From Min"].default_value = low; hz.inputs["From Max"].default_value = low + 0.08
    L.new(sep.outputs["Z"], hz.inputs["Value"])
    hz2 = N.new("ShaderNodeMapRange"); hz2.inputs["From Min"].default_value = high; hz2.inputs["From Max"].default_value = high + 0.2
    hz2.inputs["To Min"].default_value = 1; hz2.inputs["To Max"].default_value = 0
    L.new(sep.outputs["Z"], hz2.inputs["Value"])
    f1 = N.new("ShaderNodeMath"); f1.operation = "MULTIPLY"; L.new(cr.outputs[0], f1.inputs[0]); L.new(hz.outputs[0], f1.inputs[1])
    f2 = N.new("ShaderNodeMath"); f2.operation = "MULTIPLY"; L.new(f1.outputs[0], f2.inputs[0]); L.new(hz2.outputs[0], f2.inputs[1])
    shade = N.new("ShaderNodeMapRange"); shade.inputs["To Min"].default_value = 0.55; shade.inputs["To Max"].default_value = 1.0
    L.new(nz.outputs["Fac"], shade.inputs["Value"])
    cc = N.new("ShaderNodeMix"); cc.data_type = "RGBA"
    L.new(shade.outputs[0], cc.inputs[0]); cc.inputs[6].default_value = (color[0] * 0.72, color[1] * 0.76, color[2] * 0.86, 1)
    cc.inputs[7].default_value = (*color, 1)
    cs = N.new("ShaderNodeMix"); cs.data_type = "RGBA"
    L.new(f2.outputs[0], cs.inputs[0]); L.new(sky.outputs["Color"], cs.inputs[6])
    sm = N.new("ShaderNodeMix"); sm.data_type = "RGBA"; sm.blend_type = "MULTIPLY"; sm.inputs[0].default_value = 1.0
    L.new(cc.outputs[2], sm.inputs[6]); sm.inputs[7].default_value = (strength, strength, strength, 1)
    L.new(sm.outputs[2], cs.inputs[7])
    L.new(cs.outputs[2], bg.inputs["Color"])


def ocean(size=3000, z=0.0, res=10, time=1.0, wave_scale=1.0, spatial=50, mat=None, choppiness=1.0, loc=(0, 0, 0)):
    bpy.ops.mesh.primitive_plane_add(size=2, location=(loc[0], loc[1], z))
    ob = bpy.context.active_object
    ob.name = "ocean"
    m = ob.modifiers.new("ocean", "OCEAN")
    m.geometry_mode = "GENERATE"
    m.repeat_x = m.repeat_y = 1
    m.size = 1.0
    m.spatial_size = spatial
    m.resolution = res
    m.wave_scale = wave_scale
    m.choppiness = choppiness
    m.time = time
    m.random_seed = 3
    ob.scale = (size / spatial, size / spatial, 1)
    bpy.ops.object.shade_smooth()
    if mat:
        B.add_obj(ob, mat)
    return ob


def sea_plane(size, z, mat, loc=(0, 0, 0)):
    bpy.ops.mesh.primitive_plane_add(size=size, location=(loc[0], loc[1], z))
    ob = bpy.context.active_object
    ob.name = "sea"
    N, L, b = B.nodes(mat)
    tc = N.new("ShaderNodeTexCoord")
    mp = N.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1.0, 2.2, 1.0)
    L.new(tc.outputs["Object"], mp.inputs["Vector"])
    n1 = N.new("ShaderNodeTexNoise"); n1.inputs["Scale"].default_value = 0.9; n1.inputs["Detail"].default_value = 12
    n1.inputs["Roughness"].default_value = 0.62
    L.new(mp.outputs["Vector"], n1.inputs["Vector"])
    bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.35; bump.inputs["Distance"].default_value = 0.4
    L.new(n1.outputs["Fac"], bump.inputs["Height"]); L.new(bump.outputs["Normal"], b.inputs["Normal"])
    B.add_obj(ob, mat)
    return ob
