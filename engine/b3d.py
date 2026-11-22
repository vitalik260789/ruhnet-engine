"""Blender (bpy) helpers for realistic 3D concept stills."""
import math, os, time
import numpy as np
import bpy
from mathutils import Vector, Euler
from scipy.ndimage import gaussian_filter

R = np.random.default_rng(5)


# ------------------------------------------------------------------ scene / render
def reset(res=(1080, 1920), samples=64, pct=100):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.02
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = "OPENIMAGEDENOISE"
    except Exception:
        pass
    sc.cycles.max_bounces = 8
    sc.cycles.transmission_bounces = 10
    sc.cycles.glossy_bounces = 4
    sc.cycles.diffuse_bounces = 3
    sc.cycles.transparent_max_bounces = 16
    sc.cycles.caustics_reflective = False
    sc.cycles.caustics_refractive = False
    sc.cycles.blur_glossy = 1.0
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = pct
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = "PNG"
    sc.render.threads_mode = "AUTO"
    try:
        sc.view_settings.view_transform = os.environ.get("VT", "Khronos PBR Neutral")
        if sc.view_settings.view_transform == "AgX":
            sc.view_settings.look = "AgX - Punchy"
        sc.view_settings.exposure = float(os.environ.get("EXPO", "-0.6"))
    except Exception:
        try:
            sc.view_settings.view_transform = "Filmic"
        except Exception:
            pass
    return sc


def render(path):
    t = time.time()
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print(f"rendered {path} in {time.time() - t:.0f}s", flush=True)


def camera(loc, look_at, lens=35, fstop=None, focus=None):
    cd = bpy.data.cameras.new("cam")
    cd.lens = lens
    cd.clip_start = 0.01
    cd.clip_end = 50000
    ob = bpy.data.objects.new("cam", cd)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    d = Vector(look_at) - Vector(loc)
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = ob
    if fstop:
        cd.dof.use_dof = True
        cd.dof.aperture_fstop = fstop
        cd.dof.focus_distance = focus if focus else d.length
    return ob


def sun(elev_deg, azim_deg, strength=3.0, color=(1, 0.95, 0.88), angle=0.6):
    ld = bpy.data.lights.new("sun", "SUN")
    ld.energy = strength
    ld.color = color
    ld.angle = math.radians(angle)
    ob = bpy.data.objects.new("sun", ld)
    bpy.context.scene.collection.objects.link(ob)
    # sun direction: from azimuth (0 = +Y forward, i.e. behind scene) and elevation
    el, az = math.radians(elev_deg), math.radians(azim_deg)
    dirv = Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))  # towards sun
    ob.rotation_euler = (-dirv).to_track_quat("-Z", "Y").to_euler()
    return ob


def world_sky(elev_deg, azim_deg, strength=1.0, sky_type="MULTIPLE_SCATTERING", air=1.0, dust=1.0, ozone=1.0, extra=None):
    w = bpy.data.worlds.new("world")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = sky_type
    sky.sun_elevation = math.radians(elev_deg)
    # blender sun_rotation: 0 = +Y? rotate so azimuth matches our convention (0 = +Y)
    sky.sun_rotation = math.radians(azim_deg)
    sky.air_density = air
    sky.aerosol_density = dust
    sky.ozone_density = ozone
    sky.sun_disc = True
    bg.inputs["Strength"].default_value = strength
    nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    if extra:
        extra(nt, sky, bg, out)
    return w


# ------------------------------------------------------------------ meshes
def mesh_from_grid(name, Z, size_x, size_y, origin=(0, 0, 0)):
    ny, nx = Z.shape
    xs = np.linspace(-size_x / 2, size_x / 2, nx) + origin[0]
    ys = np.linspace(-size_y / 2, size_y / 2, ny) + origin[1]
    XX, YY = np.meshgrid(xs, ys)
    verts = np.stack([XX.ravel(), YY.ravel(), Z.ravel() + origin[2]], 1)
    idx = np.arange(nx * ny).reshape(ny, nx)
    a, b, c, d = idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(), idx[1:, 1:].ravel(), idx[1:, :-1].ravel()
    faces = np.stack([a, b, c, d], 1)
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts.astype(np.float64).tolist(), [], faces.tolist())
    me.update()
    me.polygons.foreach_set("use_smooth", np.ones(len(faces), bool))
    # UVs
    uv = me.uv_layers.new(name="UVMap")
    U = ((XX - XX.min()) / (XX.max() - XX.min())).ravel()
    V = ((YY - YY.min()) / (YY.max() - YY.min())).ravel()
    luv = np.stack([U[faces.ravel()], V[faces.ravel()]], 1)
    uv.data.foreach_set("uv", luv.astype(np.float32).ravel())
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def ridged(n, scales, seed, sharp=True):
    r = np.random.default_rng(seed)
    out = np.zeros((n, n), np.float32)
    amp = 1.0
    tot = 0
    for s in scales:
        z = gaussian_filter(r.standard_normal((n, n)), s, mode="wrap")
        z /= z.std() + 1e-6
        if sharp:
            z = 1 - np.abs(z)
        out += amp * z
        tot += amp
        amp *= 0.5
    return out / tot


def add_obj(ob, mat=None):
    if mat:
        if ob.data.materials:
            ob.data.materials[0] = mat
        else:
            ob.data.materials.append(mat)
    return ob


def prim_cube(size, loc, rot=(0, 0, 0), bevel=0.0, segs=3, name="cube"):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel > 0:
        m = ob.modifiers.new("bev", "BEVEL")
        m.width = bevel
        m.segments = segs
        m.limit_method = "NONE"
    bpy.ops.object.shade_smooth()
    return ob


def lathe(profile, name, segs=48, loc=(0, 0, 0)):
    """profile: list of (r, z). returns closed surface of revolution"""
    verts, faces = [], []
    n = len(profile)
    for i in range(segs):
        a = 2 * math.pi * i / segs
        for r, z in profile:
            verts.append((r * math.cos(a), r * math.sin(a), z))
    for i in range(segs):
        j = (i + 1) % segs
        for k in range(n - 1):
            faces.append((i * n + k, j * n + k, j * n + k + 1, i * n + k + 1))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    bpy.context.scene.collection.objects.link(ob)
    return ob


# ------------------------------------------------------------------ materials
def mat_principled(name, color, rough=0.5, metal=0.0, transmission=0.0, ior=1.45, alpha=1.0, emission=None, sss=0.0,
                   coat=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Transmission Weight"].default_value = transmission
    b.inputs["IOR"].default_value = ior
    b.inputs["Alpha"].default_value = alpha
    if coat:
        b.inputs["Coat Weight"].default_value = coat
    if sss:
        b.inputs["Subsurface Weight"].default_value = sss
    if emission:
        b.inputs["Emission Color"].default_value = (*emission[0], 1)
        b.inputs["Emission Strength"].default_value = emission[1]
    return m


def nodes(m):
    return m.node_tree.nodes, m.node_tree.links, m.node_tree.nodes["Principled BSDF"]


def image_material(name, path, rough=0.35, alpha_from_image=False, coat=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    N, L, b = nodes(m)
    tex = N.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(path)
    tex.interpolation = "Cubic"
    L.new(tex.outputs["Color"], b.inputs["Base Color"])
    if alpha_from_image:
        L.new(tex.outputs["Alpha"], b.inputs["Alpha"])
    b.inputs["Roughness"].default_value = rough
    if coat:
        b.inputs["Coat Weight"].default_value = coat
    return m


def haze_mix(m, haze_color, start, end, max_f=0.85):
    """blend the material's output toward a haze emission with camera distance (aerial perspective)."""
    N, L = m.node_tree.nodes, m.node_tree.links
    out = N["Material Output"]
    src = out.inputs["Surface"].links[0].from_socket
    cam = N.new("ShaderNodeCameraData")
    mr = N.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = start
    mr.inputs["From Max"].default_value = end
    mr.inputs["To Max"].default_value = max_f
    L.new(cam.outputs["View Distance"], mr.inputs["Value"])
    em = N.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*haze_color, 1)
    em.inputs["Strength"].default_value = 1.0
    mix = N.new("ShaderNodeMixShader")
    L.new(mr.outputs["Result"], mix.inputs["Fac"])
    L.new(src, mix.inputs[1])
    L.new(em.outputs["Emission"], mix.inputs[2])
    L.new(mix.outputs["Shader"], out.inputs["Surface"])


def terrain_material(name, rock=(0.32, 0.30, 0.28), grass=(0.12, 0.25, 0.06), snow=(0.92, 0.94, 0.98), snow_line=0.6,
                     grass_line=0.25, zmax=1.0, haze=None, slope_snow=0.75):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    N, L, b = nodes(m)
    geo = N.new("ShaderNodeNewGeometry")
    sep = N.new("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Position"], sep.inputs[0])
    sepn = N.new("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Normal"], sepn.inputs[0])
    noise = N.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.02
    noise.inputs["Detail"].default_value = 8
    # height normalised + noise
    hz = N.new("ShaderNodeMath"); hz.operation = "DIVIDE"; hz.inputs[1].default_value = zmax
    L.new(sep.outputs["Z"], hz.inputs[0])
    hn = N.new("ShaderNodeMath"); hn.operation = "ADD"
    nz = N.new("ShaderNodeMath"); nz.operation = "MULTIPLY"; nz.inputs[1].default_value = 0.18
    L.new(noise.outputs["Fac"], nz.inputs[0])
    L.new(hz.outputs[0], hn.inputs[0]); L.new(nz.outputs[0], hn.inputs[1])
    # rock vs grass by slope & height
    def ramp(inp, a, bb):
        mr = N.new("ShaderNodeMapRange")
        mr.inputs["From Min"].default_value = a
        mr.inputs["From Max"].default_value = bb
        L.new(inp, mr.inputs["Value"])
        return mr.outputs["Result"]
    flat = ramp(sepn.outputs["Z"], 0.72, 0.9)
    low = ramp(hn.outputs[0], grass_line + 0.12, grass_line - 0.05)
    gfac = N.new("ShaderNodeMath"); gfac.operation = "MULTIPLY"
    L.new(flat, gfac.inputs[0]); L.new(low, gfac.inputs[1])
    flat2 = ramp(sepn.outputs["Z"], slope_snow - 0.1, slope_snow + 0.05)
    high = ramp(hn.outputs[0], snow_line - 0.06, snow_line + 0.06)
    sfac = N.new("ShaderNodeMath"); sfac.operation = "MULTIPLY"
    L.new(flat2, sfac.inputs[0]); L.new(high, sfac.inputs[1])
    # rock color with noise variation
    n2 = N.new("ShaderNodeTexNoise"); n2.inputs["Scale"].default_value = 0.2; n2.inputs["Detail"].default_value = 10
    rc = N.new("ShaderNodeMix"); rc.data_type = "RGBA"
    rc.inputs[6].default_value = (*rock, 1); rc.inputs[7].default_value = (rock[0] * 0.55, rock[1] * 0.55, rock[2] * 0.6, 1)
    L.new(n2.outputs["Fac"], rc.inputs[0])
    g1 = N.new("ShaderNodeMix"); g1.data_type = "RGBA"
    L.new(gfac.outputs[0], g1.inputs[0]); L.new(rc.outputs[2], g1.inputs[6]); g1.inputs[7].default_value = (*grass, 1)
    s1 = N.new("ShaderNodeMix"); s1.data_type = "RGBA"
    L.new(sfac.outputs[0], s1.inputs[0]); L.new(g1.outputs[2], s1.inputs[6]); s1.inputs[7].default_value = (*snow, 1)
    L.new(s1.outputs[2], b.inputs["Base Color"])
    rr = N.new("ShaderNodeMapRange")
    L.new(sfac.outputs[0], rr.inputs["Value"])
    rr.inputs["To Min"].default_value = 0.9
    rr.inputs["To Max"].default_value = 0.45
    L.new(rr.outputs["Result"], b.inputs["Roughness"])
    # bump
    bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.4
    L.new(n2.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], b.inputs["Normal"])
    if haze:
        haze_mix(m, *haze)
    return m


def wood_material(name, base=(0.62, 0.42, 0.22), scale=6.0, rough=0.55, rings=False, seed=0.0, distortion=6, contrast=0.72):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    N, L, b = nodes(m)
    tc = N.new("ShaderNodeTexCoord")
    mp = N.new("ShaderNodeMapping")
    mp.inputs["Location"].default_value = (seed, seed * 1.7, seed * 0.3)
    L.new(tc.outputs["Object"], mp.inputs["Vector"])
    wave = N.new("ShaderNodeTexWave")
    wave.wave_type = "RINGS" if rings else "BANDS"
    wave.bands_direction = "X" if not rings else "X"
    wave.rings_direction = "X"
    wave.inputs["Scale"].default_value = scale
    wave.inputs["Distortion"].default_value = distortion
    wave.inputs["Detail"].default_value = 3
    wave.inputs["Detail Scale"].default_value = 2
    L.new(mp.outputs["Vector"], wave.inputs["Vector"])
    cr = N.new("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].color = (base[0] * contrast, base[1] * (contrast - 0.04), base[2] * (contrast - 0.1), 1)
    cr.color_ramp.elements[1].color = (*base, 1)
    L.new(wave.outputs["Fac"], cr.inputs["Fac"])
    L.new(cr.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.08
    L.new(wave.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def water_material(name, color=(0.02, 0.15, 0.2), rough=0.03, depth_tint=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    N, L, b = nodes(m)
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Transmission Weight"].default_value = 0.0
    b.inputs["IOR"].default_value = 1.33
    b.inputs["Specular IOR Level"].default_value = 0.5
    b.inputs["Coat Weight"].default_value = 1.0
    b.inputs["Coat Roughness"].default_value = 0.02
    return m


def glass_material(name, color=(0.2, 0.6, 0.3), rough=0.02, ior=1.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    N, L, b = nodes(m)
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Transmission Weight"].default_value = 1.0
    b.inputs["IOR"].default_value = ior
    return m


def ground_plane(size, z, mat, name="ground", subdiv=0, disp=None):
    if disp is not None:
        n = disp.shape[0]
        ob = mesh_from_grid(name, disp, size, size, (0, 0, z))
    else:
        bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, z))
        ob = bpy.context.active_object
        ob.name = name
    add_obj(ob, mat)
    return ob


def ridged_mf(n, seed, octaves=7, base=None, warp=0.06, gain=2.0):
    """ridged multifractal heightfield in [0,1] with domain warping (looks like real ranges)."""
    from scipy.ndimage import map_coordinates
    r = np.random.default_rng(seed)
    base = base or n / 6
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    w1 = gaussian_filter(r.standard_normal((n, n)), n / 8, mode="wrap")
    w2 = gaussian_filter(r.standard_normal((n, n)), n / 8, mode="wrap")
    w1 /= w1.std(); w2 /= w2.std()
    cy, cx = yy + w1 * n * warp, xx + w2 * n * warp
    total = np.zeros((n, n), np.float32)
    weight = np.ones((n, n), np.float32)
    amp, s = 1.0, base
    for k in range(octaves):
        g = gaussian_filter(r.standard_normal((n, n)), s, mode="wrap")
        g /= g.std() + 1e-6
        g = map_coordinates(g, [cy % n, cx % n], order=1, mode="wrap")
        sig = (1 - np.abs(g * 0.7)) ** 2
        sig = np.clip(sig, 0, 1) * weight
        weight = np.clip(sig * gain, 0, 1)
        total += sig * amp
        amp *= 0.52
        s = max(0.6, s / 2)
    total -= total.min()
    return total / total.max()


def scatter_instances(mesh_data, pts, scales, rotz=True, name="inst"):
    rng = np.random.default_rng(1)
    for (x, y, z), s in zip(pts, scales):
        ob = bpy.data.objects.new(name, mesh_data)
        bpy.context.scene.collection.objects.link(ob)
        ob.location = (x, y, z)
        ob.scale = s if hasattr(s, "__len__") else (s, s, s)
        if rotz:
            ob.rotation_euler = (0, 0, rng.uniform(0, 6.28))


def sample_grid(Z, size_x, size_y, origin, x, y):
    ny, nx = Z.shape
    j = (x - origin[0] + size_x / 2) / size_x * (nx - 1)
    i = (y - origin[1] + size_y / 2) / size_y * (ny - 1)
    i = int(np.clip(round(i), 0, ny - 1)); j = int(np.clip(round(j), 0, nx - 1))
    return Z[i, j] + origin[2]


def pine_mesh(mat):
    """simple layered conifer: 4 stacked cones + trunk"""
    import bmesh
    bm = bmesh.new()
    for k, (r, z0, h) in enumerate(((1.0, 0.25, 0.45), (0.8, 0.45, 0.4), (0.6, 0.62, 0.32), (0.38, 0.78, 0.24))):
        bmesh.ops.create_cone(bm, cap_ends=True, segments=9, radius1=r * 0.32, radius2=0.0, depth=h,
                              matrix=__import__("mathutils").Matrix.Translation((0, 0, z0 + h / 2)))
    me = bpy.data.meshes.new("pine")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    return me


def postprocess(path_in, path_out, sat=1.18, contrast=1.06, title=None, bet=True):
    from PIL import Image, ImageEnhance
    im = Image.open(path_in).convert("RGB")
    im = ImageEnhance.Color(im).enhance(sat)
    im = ImageEnhance.Contrast(im).enhance(contrast)
    if im.size != (1080, 1920):
        im = im.resize((1080, 1920), Image.LANCZOS)
    if title:
        from sim import text_sprite, paste, FONT_B
        fr = np.asarray(im, np.float32).copy()
        t = text_sprite([(title[0], FONT_B, 92, (255, 255, 255)), (title[1], FONT_B, 92, (255, 175, 50))], stroke=9)
        paste(fr, t, 540, 255)
        if bet:
            b = text_sprite([("Сделай ставку в комментариях", FONT_B, 52, (255, 255, 255))], stroke=7)
            paste(fr, b, 540, 1810)
        im = Image.fromarray(np.clip(fr, 0, 255).astype(np.uint8))
    im.save(path_out, quality=93)
