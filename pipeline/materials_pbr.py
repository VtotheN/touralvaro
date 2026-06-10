"""
materials_pbr.py — Principled BSDF builder from CC0 PBR texture directories.
Called from gen_panorama.py. Runs inside Blender's Python environment.
"""
from pathlib import Path


def build_pbr_material(name, pbr_dir, scale=1.0):
    """
    Build Principled BSDF material from a Polyhaven texture directory.
    pbr_dir must contain diff.jpg; nor_gl.jpg / rough.jpg / ao.jpg are optional.
    Returns the bpy.data.materials entry (creates if not exists, reuses if already created).
    """
    import bpy

    pbr_dir = Path(pbr_dir)

    # Reuse if already built
    if name in bpy.data.materials:
        m = bpy.data.materials[name]
        if m.use_nodes and len(m.node_tree.nodes) > 2:
            return m

    m = bpy.data.materials.new(name) if name not in bpy.data.materials else bpy.data.materials[name]
    m.use_nodes = True
    nodes = m.node_tree.nodes
    links = m.node_tree.links
    nodes.clear()

    out  = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    # UV coord → mapping node (scale controls tiling frequency)
    tex_coord = nodes.new("ShaderNodeTexCoord")
    mapping   = nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (scale, scale, scale)
    links.new(tex_coord.outputs["UV"], mapping.inputs["Vector"])

    def _load(fname, colorspace="sRGB"):
        fpath = pbr_dir / fname
        if not fpath.exists():
            return None
        tex = nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(str(fpath), check_existing=True)
        tex.image.colorspace_settings.name = colorspace
        links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
        return tex

    diff  = _load("diff.jpg",   "sRGB")
    rough = _load("rough.jpg",  "Non-Color")
    nor   = _load("nor_gl.jpg", "Non-Color")
    ao    = _load("ao.jpg",     "Non-Color")

    if diff:
        if ao:
            # Multiply AO into diffuse to add micro-shadowing
            mul = nodes.new("ShaderNodeMixRGB")
            mul.blend_type = "MULTIPLY"
            mul.inputs["Fac"].default_value = 0.75
            links.new(diff.outputs["Color"], mul.inputs["Color1"])
            links.new(ao.outputs["Color"],   mul.inputs["Color2"])
            links.new(mul.outputs["Color"],  bsdf.inputs["Base Color"])
        else:
            links.new(diff.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = (0.70, 0.67, 0.62, 1.0)

    if rough:
        links.new(rough.outputs["Color"], bsdf.inputs["Roughness"])
    else:
        bsdf.inputs["Roughness"].default_value = 0.75

    if nor:
        nmap = nodes.new("ShaderNodeNormalMap")
        nmap.inputs["Strength"].default_value = 1.0
        links.new(nor.outputs["Color"], nmap.inputs["Color"])
        links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])

    return m
