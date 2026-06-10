"""export_print_color_v2.py — FULL-COLOUR printable chibi cat.

Voxel-remesh gives a watertight target (required by colour bureaus), but the
remesh destroys UVs — so we Smart-UV the target and BAKE the original PBR
diffuse onto it (Cycles selected-to-active, COLOUR-only, sRGB, Standard view
transform). Output is the universal colour-print set + an embedded-texture GLB:

  print/miaomiao_v2_color.obj  + .mtl + miaomiao_v2_color.png   (OBJ+MTL+PNG — Shapeways/Sculpteo/JLC3DP)
  print/miaomiao_v2_color.glb                                   (texture embedded — preview / some services)

Arms are drooped to match the mono variants. NO base disc (colour powder/resin
beds don't need one, and a slab would bake untextured). Bake happens in the
~2-unit model space (so the recipe's ray distances hold); the mesh is scaled to
80 mm only at export — vertex scaling doesn't touch UVs.

Run:
  "D:\\Program Files\\Blender Foundation\\Blender 5.0\\blender.exe" --background --python export_print_color_v2.py
"""

import bpy, os, math, bmesh
from mathutils import Vector

BLEND_IN   = r"E:\05_claude\CGmiaomiao\miaomoaguge_v2_skinned.blend"
PRINT_DIR  = r"E:\05_claude\CGmiaomiao\print"
VERIFY_DIR = r"E:\05_claude\CGmiaomiao\verify"
os.makedirs(PRINT_DIR, exist_ok=True); os.makedirs(VERIFY_DIR, exist_ok=True)

TARGET_HEIGHT_MM = 100.0
ARM_DROOP_DEG    = 22.0     # keep both arms clearly visible
ARM_RAISE        = 0.09     # lift arms to shoulder height ("手太下" fix) — match mono
VOXEL            = 0.006     # ~0.3mm feature @ 100mm — crisp colour geometry
BAKE_RES         = 2048      # 2K: sweet spot for an 80mm figurine
PNG_OUT = os.path.join(PRINT_DIR, "miaomiao_v2_color.png")
OBJ_OUT = os.path.join(PRINT_DIR, "miaomiao_v2_color.obj")
GLB_OUT = os.path.join(PRINT_DIR, "miaomiao_v2_color.glb")

# ---------- prep (detach rig, bake transforms, droop arms) ----------
bpy.ops.wm.open_mainfile(filepath=BLEND_IN)
src = [o for o in bpy.data.objects if o.type == 'MESH']
print(f"[load] {len(src)} parts")
bpy.ops.object.select_all(action='DESELECT')
for m in src:
    m.select_set(True); bpy.context.view_layer.objects.active = m
    if m.parent: bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
    for mod in list(m.modifiers):
        if mod.type == 'ARMATURE': m.modifiers.remove(mod)
    m.select_set(False)
bpy.ops.object.select_all(action='DESELECT')
for m in src: m.select_set(True)
bpy.context.view_layer.objects.active = src[0]
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

body = next((m for m in src if m.get('anatomy') == 'Body'), None)
bx = (sum((body.matrix_world @ v.co).x for v in body.data.vertices)/len(body.data.vertices)) if body else 0.0
for m in src:
    if m.get('anatomy') not in ('ArmL', 'ArmR'): continue
    for v in m.data.vertices: v.co.z += ARM_RAISE   # lift to shoulder height first
    co=[v.co for v in m.data.vertices]; xs=[c.x for c in co]; zs=[c.z for c in co]
    inner_x=min(xs,key=lambda x:abs(x-bx)); outer_x=max(xs,key=lambda x:abs(x-bx))
    pv=Vector((inner_x, sum(c.y for c in co)/len(co), max(zs)))
    ang=(1.0 if outer_x>inner_x else -1.0)*math.radians(ARM_DROOP_DEG)
    c,s=math.cos(ang),math.sin(ang)
    for v in m.data.vertices:
        dx=v.co.x-pv.x; dz=v.co.z-pv.z
        v.co.x=pv.x+dx*c+dz*s; v.co.z=pv.z-dx*s+dz*c
    m.data.update()
    print(f"[droop] {m.get('anatomy')} {math.degrees(ang):+.0f}")

sources = list(src)   # textured + UV'd → bake source

# ---------- build watertight target (duplicates → join → voxel remesh) ----------
def dup(o):
    d=o.data.copy(); n=bpy.data.objects.new(o.name+"_t", d)
    bpy.context.collection.objects.link(n); n.matrix_world=o.matrix_world.copy(); return n
parts=[dup(o) for o in sources]
bpy.ops.object.select_all(action='DESELECT')
for o in parts: o.select_set(True)
bpy.context.view_layer.objects.active=parts[0]
bpy.ops.object.join()
target=bpy.context.active_object; target.name="ColorTarget"
target.data.materials.clear()
target.data.remesh_voxel_size=VOXEL; target.data.remesh_voxel_adaptivity=0.0
target.data.use_remesh_fix_poles=True; target.data.use_remesh_preserve_volume=True
bpy.ops.object.voxel_remesh()
# clean + self-check
bm=bmesh.new(); bm.from_mesh(target.data)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
nm=sum(1 for e in bm.edges if not e.is_manifold); op=sum(1 for e in bm.edges if len(e.link_faces)<2)
bm.to_mesh(target.data); bm.free()
print(f"[target] verts={len(target.data.vertices)} tris={len(target.data.polygons)} non-manifold={nm} open={op} watertight={nm==0 and op==0}")

# ---------- smart UV project the target ----------
bpy.ops.object.select_all(action='DESELECT')
target.select_set(True); bpy.context.view_layer.objects.active=target
if not target.data.uv_layers: target.data.uv_layers.new(name="UVMap")
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=1.151917, island_margin=0.02, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
bpy.ops.object.mode_set(mode='OBJECT')

# ---------- blank bake image + active image-texture node on target ----------
img=bpy.data.images.new("baked_diffuse", width=BAKE_RES, height=BAKE_RES, alpha=False)
img.colorspace_settings.name='sRGB'; img.alpha_mode='NONE'; img.generated_color=(0,0,0,1)
mat=bpy.data.materials.new("ColorBake_Mat"); target.data.materials.append(mat)
mat.use_nodes=True; nt=mat.node_tree
texn=nt.nodes.new('ShaderNodeTexImage'); texn.image=img
texn.select=True; nt.nodes.active=texn

# ---------- Cycles selected-to-active diffuse COLOUR bake ----------
scene=bpy.context.scene
scene.render.engine='CYCLES'; scene.cycles.samples=4
scene.view_settings.view_transform='Standard'; scene.view_settings.look='None'
scene.view_settings.exposure=0.0; scene.view_settings.gamma=1.0
bpy.ops.object.select_all(action='DESELECT')
for sObj in sources: sObj.select_set(True)
target.select_set(True); bpy.context.view_layer.objects.active=target
bk=scene.render.bake
bk.use_selected_to_active=True; bk.cage_extrusion=0.05; bk.max_ray_distance=0.10
bk.margin=16; bk.margin_type='ADJACENT_FACES'; bk.use_cage=False
bk.use_pass_direct=False; bk.use_pass_indirect=False; bk.use_pass_color=True
print("[bake] baking diffuse colour (selected-to-active)…")
bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, use_selected_to_active=True,
                    cage_extrusion=0.05, max_ray_distance=0.10, margin=16,
                    margin_type='ADJACENT_FACES', use_clear=True,
                    target='IMAGE_TEXTURES', save_mode='INTERNAL')

# The image is alpha-less (alpha_mode='NONE'), so the diffuse COLOUR bake's RGB
# saves as a fully OPAQUE texture — no transparent-bake → black premultiply trap.
# self-check: fraction of texels that received colour, and their mean.
px = img.pixels[:]
n = len(px)//4
baked = 0; rs = gs = bs = 0.0; cnt = 0
step = max(1, n//20000)
for i in range(0, n, step):
    cnt += 1
    r, g, b = px[i*4], px[i*4+1], px[i*4+2]
    if r + g + b > 0.03:
        baked += 1; rs += r; gs += g; bs += b
print(f"[bake] coloured texels ~{100*baked/cnt:.1f}% of texture; "
      f"mean baked RGB=({rs/max(baked,1):.3f},{gs/max(baked,1):.3f},{bs/max(baked,1):.3f})")
if baked == 0:
    raise RuntimeError("BAKE PRODUCED NO COLOUR — check selection order / ray distance / source textures")

# Save touching ONLY filepath/format — re-assigning colorspace/alpha_mode/
# generated_color here regenerates the image buffer (→ black) and discards the
# bake. (That was the black-PNG bug; props are already set at creation.)
img.filepath_raw=PNG_OUT; img.file_format='PNG'; img.save()
print(f"[png] {PNG_OUT}  ({os.path.getsize(PNG_OUT)/1024:.0f} KB)")

# wire baked image → base color (find Principled by TYPE — localized Blender)
bsdf=next((nd for nd in nt.nodes if nd.type=='BSDF_PRINCIPLED'), None)
if bsdf is None:
    bsdf=nt.nodes.new('ShaderNodeBsdfPrincipled')
    out=next((nd for nd in nt.nodes if nd.type=='OUTPUT_MATERIAL'), None) or nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
nt.links.new(texn.outputs['Color'], bsdf.inputs['Base Color'])

# ---------- orient + scale to mm (UVs unaffected) ----------
pts=[target.matrix_world @ v.co for v in target.data.vertices]
xs=[p.x for p in pts]; ys=[p.y for p in pts]; zs=[p.z for p in pts]
scale=TARGET_HEIGHT_MM/(max(zs)-min(zs)); cx=(min(xs)+max(xs))/2; cy=(min(ys)+max(ys))/2; cz=min(zs)
for v in target.data.vertices:
    v.co=Vector(((v.co.x-cx)*scale,(v.co.y-cy)*scale,(v.co.z-cz)*scale))
target.data.update()
fp=[target.matrix_world @ v.co for v in target.data.vertices]
dimX=max(p.x for p in fp)-min(p.x for p in fp); dimY=max(p.y for p in fp)-min(p.y for p in fp); dimZ=max(p.z for p in fp)-min(p.z for p in fp)
print(f"[size] {dimX:.1f} x {dimY:.1f} x {dimZ:.1f} mm")

# ---------- export OBJ+MTL+PNG and GLB ----------
bpy.ops.object.select_all(action='DESELECT'); target.select_set(True); bpy.context.view_layer.objects.active=target
bpy.ops.wm.obj_export(filepath=OBJ_OUT, export_selected_objects=True, export_materials=True,
                      export_uv=True, export_normals=True, path_mode='AUTO',
                      forward_axis='NEGATIVE_Z', up_axis='Y')
print(f"[obj] {OBJ_OUT}")
bpy.ops.export_scene.gltf(filepath=GLB_OUT, export_format='GLB', use_selection=True,
                          export_image_format='AUTO', export_yup=True, export_apply=False)
print(f"[glb] {GLB_OUT}  ({os.path.getsize(GLB_OUT)/1024:.0f} KB)")

# ---------- textured verification render (EEVEE, baked material) ----------
for o in list(bpy.data.objects):
    if o.type in ('CAMERA','LIGHT'): bpy.data.objects.remove(o, do_unlink=True)
for sObj in sources: bpy.data.objects.remove(sObj, do_unlink=True)   # hide sources from preview
diag=max(dimX,dimY,dimZ); tgt=Vector((0,0,dimZ*0.5))
try: scene.render.engine="BLENDER_EEVEE_NEXT"
except Exception: scene.render.engine="BLENDER_EEVEE"
scene.render.resolution_x=600; scene.render.resolution_y=800
scene.view_settings.view_transform='Standard'
scene.world=scene.world or bpy.data.worlds.new("World"); scene.world.use_nodes=True
bg=scene.world.node_tree.nodes.get("Background")
if bg: bg.inputs[0].default_value=(0.9,0.92,0.95,1.0)
lt=bpy.data.lights.new("Sun",type="SUN"); lt.energy=3.5
lo=bpy.data.objects.new("Sun",lt); bpy.context.collection.objects.link(lo)
lo.rotation_euler=(math.radians(55),math.radians(15),math.radians(-35))
cd=bpy.data.cameras.new("Cam"); cd.type="ORTHO"; cd.ortho_scale=diag*1.5
co=bpy.data.objects.new("Cam",cd); bpy.context.collection.objects.link(co); scene.camera=co
def shot(suf,off):
    co.location=tgt+Vector(off); co.rotation_euler=(tgt-co.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=os.path.join(VERIFY_DIR,f"v2_print_color_{suf}.png"); bpy.ops.render.render(write_still=True)
shot("front",(0,-diag*2.2,diag*0.35))
shot("34",(diag*1.6,-diag*1.8,diag*0.45))
print("\n[done] colour print set ready.")
