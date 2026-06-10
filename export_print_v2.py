"""export_print_v2.py — Turn the v2 chibi cat into 3D-PRINTABLE solids (STL).

Produces TWO monochrome variants in one Blender run, both with the arms
drooped to a natural rest (less support, sturdier than the T-pose):

  print/miaomiao_v2_fdm.stl     FDM:   + stability base disc, voxel ~0.008  (~0.34mm feature @ 80mm)
  print/miaomiao_v2_resin.stl   resin: no base, finer voxel ~0.0045        (~0.19mm feature @ 80mm)

(Full-COLOUR printing is a separate pipeline — see export_print_color_v2.py,
which keeps UVs and bakes the diffuse onto a watertight target.)

Pipeline: open skinned blend (rest pose) → detach rig + bake transforms →
DROOP ARMS about each shoulder → per-variant: (+base) → JOIN → VOXEL REMESH
→ watertight/manifold/single-piece self-check → drop to Z=0, centre XY, scale
to mm → STL + clay renders.

Run:
  "D:\\Program Files\\Blender Foundation\\Blender 5.0\\blender.exe" --background --python export_print_v2.py
"""

import bpy, os, math, bmesh
from mathutils import Vector, Matrix

BLEND_IN   = r"E:\05_claude\CGmiaomiao\miaomoaguge_v2_skinned.blend"
PRINT_DIR  = r"E:\05_claude\CGmiaomiao\print"
VERIFY_DIR = r"E:\05_claude\CGmiaomiao\verify"
os.makedirs(PRINT_DIR, exist_ok=True)
os.makedirs(VERIFY_DIR, exist_ok=True)

# ---- Shared parameters ----
TARGET_HEIGHT_MM = 100.0    # finished height; STL coords emitted in mm
ARM_DROOP_DEG    = 22.0     # swing each arm down from horizontal about its shoulder
ARM_RAISE        = 0.09     # lift each arm up (Blender units) to shoulder height —
                            # the source arms sit low on the torso ("手太下"); this
                            # moves the attach point up so they read as shoulders.
ASCII_STL        = False

# ---- Per-variant parameters ----
VARIANTS = {
    "fdm":   dict(voxel=0.0080, base=True,  base_th=0.060, base_overlap=0.06),
    "resin": dict(voxel=0.0045, base=False, base_th=0.0,   base_overlap=0.0),
}

# =====================================================================
def load_and_prep():
    """Open blend, detach rig, bake transforms, droop arms. Returns posed meshes."""
    bpy.ops.wm.open_mainfile(filepath=BLEND_IN)
    src = [o for o in bpy.data.objects if o.type == 'MESH']
    print(f"[load] {len(src)} mesh parts")

    bpy.ops.object.select_all(action='DESELECT')
    for m in src:
        m.select_set(True); bpy.context.view_layer.objects.active = m
        if m.parent:
            bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
        for mod in list(m.modifiers):
            if mod.type == 'ARMATURE':
                m.modifiers.remove(mod)
        m.select_set(False)

    bpy.ops.object.select_all(action='DESELECT')
    for m in src:
        m.select_set(True)
    bpy.context.view_layer.objects.active = src[0]
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    # now each mesh's local coords == world coords (matrix_world ~ identity)

    droop_arms(src, math.radians(ARM_DROOP_DEG))
    return src

def droop_arms(meshes, theta):
    """Rotate each arm mesh about a world-Y axis through its shoulder pivot so
    the hand swings DOWN. Sign per side: a = sign(outward_x)*theta."""
    # body centre x to find the inner (shoulder) end of each arm
    body = next((m for m in meshes if m.get('anatomy') == 'Body'), None)
    bx = (sum((body.matrix_world @ v.co).x for v in body.data.vertices) / len(body.data.vertices)) if body else 0.0
    for m in meshes:
        a = m.get('anatomy')
        if a not in ('ArmL', 'ArmR'):
            continue
        # 1) lift the whole arm up to shoulder height
        for v in m.data.vertices:
            v.co.z += ARM_RAISE
        co = [v.co for v in m.data.vertices]
        xs = [c.x for c in co]; zs = [c.z for c in co]
        inner_x = min(xs, key=lambda x: abs(x - bx))   # shoulder side
        outer_x = max(xs, key=lambda x: abs(x - bx))   # hand side
        pivot = Vector((inner_x, sum(c.y for c in co)/len(co), max(zs)))
        sign = 1.0 if (outer_x - inner_x) > 0 else -1.0
        ang = sign * theta
        c, s = math.cos(ang), math.sin(ang)
        for v in m.data.vertices:
            dx = v.co.x - pivot.x; dz = v.co.z - pivot.z
            v.co.x = pivot.x + dx*c + dz*s
            v.co.z = pivot.z - dx*s + dz*c
        m.data.update()
        print(f"[droop] {a} pivot=({pivot.x:+.3f},{pivot.z:+.3f}) angle={math.degrees(ang):+.0f}")

def world_bbox(objs):
    pts = []
    for o in objs:
        pts.extend(o.matrix_world @ v.co for v in o.data.vertices)
    xs=[p.x for p in pts]; ys=[p.y for p in pts]; zs=[p.z for p in pts]
    return Vector((min(xs),min(ys),min(zs))), Vector((max(xs),max(ys),max(zs)))

def dup_mesh(o):
    d = o.data.copy(); n = bpy.data.objects.new(o.name + "_c", d)
    bpy.context.collection.objects.link(n); n.matrix_world = o.matrix_world.copy()
    return n

def add_base(objs, bmin, bmax, base_th, overlap):
    foot = []
    for o in objs:
        for v in o.data.vertices:
            p = o.matrix_world @ v.co
            if p.z < bmin.z + 0.22:
                foot.append(p)
    if foot:
        fx=[p.x for p in foot]; fy=[p.y for p in foot]
        cx=(min(fx)+max(fx))/2; cy=(min(fy)+max(fy))/2
        rad=0.5*max(max(fx)-min(fx), max(fy)-min(fy))+0.09   # roomier plinth for stability
    else:
        cx=(bmin.x+bmax.x)/2; cy=(bmin.y+bmax.y)/2; rad=0.5*max(bmax.x-bmin.x,bmax.y-bmin.y)
    top_z = bmin.z + overlap
    bpy.ops.mesh.primitive_cylinder_add(vertices=72, radius=rad, depth=base_th,
                                        location=(cx, cy, top_z - base_th/2))
    d = bpy.context.active_object; d.name = "PrintBase"
    print(f"[base] r={rad:.2f} center=({cx:+.2f},{cy:+.2f}) top_z={top_z:+.2f}")
    return d

def selfcheck(mesh):
    bm = bmesh.new(); bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    nm = sum(1 for e in bm.edges if not e.is_manifold)
    op = sum(1 for e in bm.edges if len(e.link_faces) < 2)
    bm.to_mesh(mesh); bm.free()
    # islands
    bm = bmesh.new(); bm.from_mesh(mesh); bm.verts.ensure_lookup_table()
    seen=set(); islands=0
    for sv in bm.verts:
        if sv.index in seen: continue
        islands+=1; stack=[sv]; seen.add(sv.index)
        while stack:
            v=stack.pop()
            for e in v.link_edges:
                ov=e.other_vert(v)
                if ov.index not in seen: seen.add(ov.index); stack.append(ov)
    bm.free()
    return nm, op, islands

def build_variant(name, posed, cfg):
    print(f"\n===== variant: {name}  (voxel={cfg['voxel']}, base={cfg['base']}) =====")
    parts = [dup_mesh(o) for o in posed]
    bmin, bmax = world_bbox(parts)
    if cfg["base"]:
        parts.append(add_base(parts, bmin, bmax, cfg["base_th"], cfg["base_overlap"]))

    bpy.ops.object.select_all(action='DESELECT')
    for o in parts: o.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    obj = bpy.context.active_object; obj.name = f"print_{name}"

    bpy.context.view_layer.objects.active = obj
    obj.data.remesh_voxel_size = cfg["voxel"]
    obj.data.remesh_voxel_adaptivity = 0.0
    obj.data.use_remesh_fix_poles = True
    obj.data.use_remesh_preserve_volume = True
    bpy.ops.object.voxel_remesh()
    nm, op, islands = selfcheck(obj.data)
    watertight = (nm == 0 and op == 0)
    print(f"[mesh] verts={len(obj.data.vertices)} tris={len(obj.data.polygons)} "
          f"non-manifold={nm} open={op} pieces={islands} watertight={watertight}")

    # orient + scale to mm
    pts=[obj.matrix_world @ v.co for v in obj.data.vertices]
    xs=[p.x for p in pts]; ys=[p.y for p in pts]; zs=[p.z for p in pts]
    scale = TARGET_HEIGHT_MM / (max(zs)-min(zs))
    cx=(min(xs)+max(xs))/2; cy=(min(ys)+max(ys))/2; cz=min(zs)
    for v in obj.data.vertices:
        v.co = Vector(((v.co.x-cx)*scale, (v.co.y-cy)*scale, (v.co.z-cz)*scale))
    obj.data.update()
    fp=[obj.matrix_world @ v.co for v in obj.data.vertices]
    dimX=max(p.x for p in fp)-min(p.x for p in fp)
    dimY=max(p.y for p in fp)-min(p.y for p in fp)
    dimZ=max(p.z for p in fp)-min(p.z for p in fp)
    print(f"[size] {dimX:.1f} x {dimY:.1f} x {dimZ:.1f} mm")

    out = os.path.join(PRINT_DIR, f"miaomiao_v2_{name}.stl")
    bpy.ops.object.select_all(action='DESELECT'); obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    try:
        bpy.ops.wm.stl_export(filepath=out, ascii_format=ASCII_STL,
                              apply_modifiers=True, export_selected_objects=True, global_scale=1.0)
    except Exception as e:
        print(f"  wm.stl_export failed ({e}); legacy path")
        bpy.ops.export_mesh.stl(filepath=out, ascii=ASCII_STL,
                                use_mesh_modifiers=True, use_selection=True, global_scale=1.0)
    print(f"[stl] {out}  ({os.path.getsize(out)/1024:.0f} KB)")
    return obj, (dimX, dimY, dimZ), watertight, islands

def render_clay(obj, prefix, dims):
    clay = bpy.data.materials.new("Clay"); clay.use_nodes = True
    bsdf = next((n for n in clay.node_tree.nodes if n.type=='BSDF_PRINCIPLED'), None)
    if bsdf:
        bsdf.inputs["Base Color"].default_value=(0.62,0.78,0.55,1.0)
        if "Roughness" in bsdf.inputs: bsdf.inputs["Roughness"].default_value=0.6
    obj.data.materials.clear(); obj.data.materials.append(clay)
    for o in list(bpy.data.objects):
        if o.type in ('CAMERA','LIGHT'): bpy.data.objects.remove(o, do_unlink=True)
    dimX,dimY,dimZ = dims; diag=max(dims); target=Vector((0,0,dimZ*0.5))
    sc=bpy.context.scene
    try: sc.render.engine="BLENDER_EEVEE_NEXT"
    except Exception: sc.render.engine="BLENDER_EEVEE"
    sc.render.resolution_x=600; sc.render.resolution_y=800
    sc.world=sc.world or bpy.data.worlds.new("World"); sc.world.use_nodes=True
    bg=sc.world.node_tree.nodes.get("Background")
    if bg: bg.inputs[0].default_value=(0.9,0.92,0.95,1.0)
    lt=bpy.data.lights.new("Sun",type="SUN"); lt.energy=4.0
    lo=bpy.data.objects.new("Sun",lt); bpy.context.collection.objects.link(lo)
    lo.rotation_euler=(math.radians(55),math.radians(15),math.radians(-35))
    cd=bpy.data.cameras.new("Cam"); cd.type="ORTHO"; cd.ortho_scale=diag*1.5
    co=bpy.data.objects.new("Cam",cd); bpy.context.collection.objects.link(co); sc.camera=co
    def shot(suffix, off):
        co.location=target+Vector(off)
        co.rotation_euler=(target-co.location).to_track_quat('-Z','Y').to_euler()
        sc.render.filepath=os.path.join(VERIFY_DIR, f"{prefix}_{suffix}.png")
        bpy.ops.render.render(write_still=True)
    shot("front",(0,-diag*2.2,diag*0.35))
    shot("34",(diag*1.6,-diag*1.8,diag*0.45))
    shot("side",(diag*2.2,0,diag*0.35))

# =====================================================================
print("\n==== export_print_v2 (mono FDM + resin, arms drooped) ====")
posed = load_and_prep()
results = {}
for name, cfg in VARIANTS.items():
    obj, dims, watertight, islands = build_variant(name, posed, cfg)
    render_clay(obj, f"v2_print_{name}", dims)
    results[name] = (dims, watertight, islands)
    # clean up this variant's object so the next variant starts from posed only
    bpy.data.objects.remove(obj, do_unlink=True)

print("\n==== SUMMARY ====")
for name,(dims,wt,isl) in results.items():
    print(f"  {name:6s}  {dims[0]:.0f}x{dims[1]:.0f}x{dims[2]:.0f} mm  watertight={wt}  pieces={isl}")
