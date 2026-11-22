"""Materials and shapes shared by the 3D reels (cans, ice)."""
import bpy
import b3d as B

CAN_COLS = [(205, 28, 36), (28, 140, 70), (30, 90, 200), (245, 170, 20), (125, 45, 165), (240, 95, 25), (20, 160, 175)]


def lin(c):
    return tuple(((v / 255) ** 2.2) for v in c) + (1,)


def can_material(name, col, R=0.033, HC=0.122):
    m = bpy.data.materials.new(name); m.use_nodes = True
    N, L, b = B.nodes(m)
    tc = N.new("ShaderNodeTexCoord"); sep = N.new("ShaderNodeSeparateXYZ"); L.new(tc.outputs["Object"], sep.inputs[0])

    def band(lo, hi):
        a = N.new("ShaderNodeMath"); a.operation = "GREATER_THAN"; a.inputs[1].default_value = lo; L.new(sep.outputs["Z"], a.inputs[0])
        c = N.new("ShaderNodeMath"); c.operation = "LESS_THAN"; c.inputs[1].default_value = hi; L.new(sep.outputs["Z"], c.inputs[0])
        mm = N.new("ShaderNodeMath"); mm.operation = "MULTIPLY"; L.new(a.outputs[0], mm.inputs[0]); L.new(c.outputs[0], mm.inputs[1])
        return mm.outputs[0]

    def mix(fac, c_a, c_b_socket=None, c_b=None):
        mx = N.new("ShaderNodeMix"); mx.data_type = "RGBA"
        L.new(fac, mx.inputs[0])
        if isinstance(c_a, tuple):
            mx.inputs[6].default_value = c_a
        else:
            L.new(c_a, mx.inputs[6])
        mx.inputs[7].default_value = c_b
        return mx.outputs[2]

    col_s = mix(band(HC * 0.40, HC * 0.56), lin(col), c_b=lin((242, 240, 232)))
    col_s = mix(band(HC * 0.60, HC * 0.64), col_s, c_b=lin((250, 215, 80)))
    # emblem circle on the front (-Y side)
    d = N.new("ShaderNodeVectorMath"); d.operation = "DISTANCE"
    cmb = N.new("ShaderNodeCombineXYZ"); L.new(sep.outputs["X"], cmb.inputs[0]); L.new(sep.outputs["Z"], cmb.inputs[2])
    L.new(cmb.outputs[0], d.inputs[0]); d.inputs[1].default_value = (0, 0, HC * 0.73)
    lt = N.new("ShaderNodeMath"); lt.operation = "LESS_THAN"; lt.inputs[1].default_value = R * 0.32; L.new(d.outputs["Value"], lt.inputs[0])
    fr = N.new("ShaderNodeMath"); fr.operation = "LESS_THAN"; fr.inputs[1].default_value = 0.0; L.new(sep.outputs["Y"], fr.inputs[0])
    em = N.new("ShaderNodeMath"); em.operation = "MULTIPLY"; L.new(lt.outputs[0], em.inputs[0]); L.new(fr.outputs[0], em.inputs[1])
    col_s = mix(em.outputs[0], col_s, c_b=lin((255, 230, 110)))
    # silver rims
    rl = N.new("ShaderNodeMath"); rl.operation = "LESS_THAN"; rl.inputs[1].default_value = 0.008; L.new(sep.outputs["Z"], rl.inputs[0])
    rh = N.new("ShaderNodeMath"); rh.operation = "GREATER_THAN"; rh.inputs[1].default_value = HC - 0.009; L.new(sep.outputs["Z"], rh.inputs[0])
    rim = N.new("ShaderNodeMath"); rim.operation = "MAXIMUM"; L.new(rl.outputs[0], rim.inputs[0]); L.new(rh.outputs[0], rim.inputs[1])
    col_s = mix(rim.outputs[0], col_s, c_b=lin((205, 205, 212)))
    L.new(col_s, b.inputs["Base Color"])
    met = N.new("ShaderNodeMapRange"); L.new(rim.outputs[0], met.inputs["Value"])
    met.inputs["To Min"].default_value = 0.15; met.inputs["To Max"].default_value = 1.0
    L.new(met.outputs[0], b.inputs["Metallic"])
    b.inputs["Roughness"].default_value = 0.38
    b.inputs["Coat Weight"].default_value = 0.15
    b.inputs["Coat Roughness"].default_value = 0.08
    return m




def can_profile(R, HC):
    return [(0.0, 0.0), (R - 0.004, 0.0), (R - 0.001, 0.002), (R, 0.007), (R, HC - 0.012), (R - 0.003, HC - 0.006),
            (R - 0.005, HC - 0.002), (R - 0.004, HC), (R - 0.007, HC - 0.0015), (0.0, HC - 0.0015)]


def ice_material():
    m = bpy.data.materials.new("ice")
    m.use_nodes = True
    N, L, b = B.nodes(m)
    b.inputs["Base Color"].default_value = (0.82, 0.93, 1.0, 1)
    b.inputs["Transmission Weight"].default_value = 1.0
    b.inputs["IOR"].default_value = 1.31
    b.inputs["Roughness"].default_value = 0.22
    nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 60; nz.inputs["Detail"].default_value = 6
    bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.1
    L.new(nz.outputs["Fac"], bump.inputs["Height"]); L.new(bump.outputs["Normal"], b.inputs["Normal"])
    vol = N.new("ShaderNodeVolumeAbsorption"); vol.inputs["Color"].default_value = (0.7, 0.88, 1.0, 1)
    vol.inputs["Density"].default_value = 14
    L.new(vol.outputs[0], N["Material Output"].inputs["Volume"])
    return m
