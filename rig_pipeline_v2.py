"""rig_pipeline_v2.py — Re-rig the new PBR chibi cat GLB from scratch.

STEP 1 (this file, as of now): Import the GLB, label each root.X with its
known anatomical name (from earlier probe), print stats, save .blend, render
one verification PNG.  NO rigging surgery yet.

Source model (vs the original Tripo miaomoaguge.glb that this replaces):
  - 9 mesh parts named root.0..8 (was 14 tripo_part_*)
  - Each part has its own material with full PBR pack (diffuse + normal +
    metallic + roughness 2K textures) — was diffuse-only basecolor before
  - Scale ~2× larger (Z range 0-1.9, was 0-1.0)
  - Orientation: faces -Y, tail at +Y (was faces +X, tail at -X)
  - Closed-manifold meshes (3-9% boundary edges, was 40-58%)

Anatomical mapping (confirmed by isolated renders in verify/anatomy_root_*.png):
"""

import bpy
import os
import math
from mathutils import Vector

# ---- Paths ----
GLB_IN     = r"E:\05_claude\CGmiaomiao\_new_asset_inspect\base_basic_pbr.glb"
BLEND_OUT  = r"E:\05_claude\CGmiaomiao\miaomoaguge_v2_imported.blend"
VERIFY_DIR = r"E:\05_claude\CGmiaomiao\verify"
os.makedirs(VERIFY_DIR, exist_ok=True)

# ---- Anatomical mapping (root.X → semantic part name) ----
ANATOMY = {
    "root.0": "EarL",
    "root.1": "ArmL",
    "root.2": "LegL",
    "root.3": "Head",
    "root.4": "Body",
    "root.5": "ArmR",
    "root.6": "LegR",
    "root.7": "Tail",
    "root.8": "EarR",
}

# =====================================================================
# Step 1: Import + identify
# =====================================================================
print("\n[1] Import new PBR GLB and identify parts")
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB_IN)

meshes = sorted([o for o in bpy.data.objects if o.type == 'MESH'], key=lambda x: x.name)
print(f"  Imported {len(meshes)} mesh parts")
if len(meshes) != 9:
    print(f"  [warn] expected 9, got {len(meshes)} — new export?")

# Collect per-part stats and bbox
print(f"\n  {'mesh':10s}  {'anatomy':6s}  {'verts':>6s}  {'polys':>6s}  bbox(X,Y,Z)")
for m in meshes:
    pts = [m.matrix_world @ v.co for v in m.data.vertices]
    xs=[p.x for p in pts]; ys=[p.y for p in pts]; zs=[p.z for p in pts]
    anatomy = ANATOMY.get(m.name, "???")
    print(f"  {m.name:10s}  {anatomy:6s}  {len(m.data.vertices):>6d}  {len(m.data.polygons):>6d}  "
          f"X[{min(xs):+.2f},{max(xs):+.2f}] "
          f"Y[{min(ys):+.2f},{max(ys):+.2f}] "
          f"Z[{min(zs):+.2f},{max(zs):+.2f}]")

# Sanity check: every expected anatomy is present
missing = [k for k in ANATOMY if not any(m.name == k for m in meshes)]
if missing:
    print(f"  [warn] missing expected meshes: {missing}")
extra = [m.name for m in meshes if m.name not in ANATOMY]
if extra:
    print(f"  [warn] unrecognized meshes: {extra}")

# =====================================================================
# Step 2 (still in-step-1): Mark anatomy via a custom property on each mesh
# so downstream pipeline steps can look up part roles without re-deriving.
# =====================================================================
print("\n[2] Tag each mesh with its anatomy via custom property")
for m in meshes:
    m["anatomy"] = ANATOMY.get(m.name, "unknown")
print(f"  Tagged {len(meshes)} meshes")

# =====================================================================
# Step 2.5: Reshape legs for chibi proportions — SCALE shorter + TRANSLATE
# so leg top aligns with body bottom (not body middle).
#
# Source has LegL/R Z=[0.00, 0.66~0.68], Body Z=[0.22, 0.78].
# Pure translation (any amount) couldn't satisfy "short stubby legs AND
# join at body bottom AND no broken-face joint" simultaneously, because
# legs were too LONG geometrically.  Solution: shrink Z by 60%, then
# translate so leg-top = body bottom (0.22).  Result: ~40cm leg attached
# to body's bottom edge, chibi short-stub silhouette.
# =====================================================================
LEG_Z_SCALE = 0.75        # was 0.6 (too much squish → normal map artifacts as
                          # "wavy folds" because normals baked for original shape).
                          # 0.75 keeps legs short but preserves normal-map fidelity.
LEG_TOP_TARGET = 0.42     # was 0.35 (still showed a visible seam where leg surface
                          # crossed body silhouette). 0.42 buries leg-top deeper into
                          # body's wide middle, hiding the junction.
print(f"\n[2.5] Reshape legs: scale Z×{LEG_Z_SCALE} + translate so top = {LEG_TOP_TARGET} + recalc normals")
import bmesh as _bm25
for m in meshes:
    if m.get("anatomy") in ("LegL", "LegR"):
        # 1. Scale Z (compress vertically)
        for v in m.data.vertices:
            v.co.z *= LEG_Z_SCALE
        # 2. Translate so the new max-Z equals LEG_TOP_TARGET
        max_z = max(v.co.z for v in m.data.vertices)
        delta = LEG_TOP_TARGET - max_z
        for v in m.data.vertices:
            v.co.z += delta
        m.data.update()
        # 3. Recalc face normals (vertex transform invalidated original normals)
        bm = _bm25.new()
        bm.from_mesh(m.data)
        _bm25.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(m.data)
        bm.free()
        m.data.update()
        # Mark all polygons smooth-shaded
        for poly in m.data.polygons:
            poly.use_smooth = True
        new_min = min(v.co.z for v in m.data.vertices)
        new_max = max(v.co.z for v in m.data.vertices)
        print(f"  {m.name} ({m.get('anatomy')}) → Z=[{new_min:+.3f},{new_max:+.3f}] (normals recalculated)")

# =====================================================================
# Step 3: Build simplified 13-bone armature
#
# Hierarchy (anatomical, no Mixamo compat):
#   Hips
#   ├── Spine
#   │   └── Head
#   │       ├── EarL
#   │       └── EarR
#   ├── ArmL,  ArmR
#   ├── LegL,  LegR
#   └── Tail1 → Tail2 → Tail3 → Tail4
#
# Bone positions derived directly from each anatomical part's bbox /
# centroid. Y_center is averaged from all body-front parts (faces -Y).
# =====================================================================
print("\n[3] Build simplified 13-bone armature from anatomy")

def part_bbox(name):
    """Return (min, max, centroid) Vectors for the mesh whose anatomy == name."""
    for m in meshes:
        if m.get("anatomy") == name:
            pts = [m.matrix_world @ v.co for v in m.data.vertices]
            return (
                Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
                Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))),
                sum(pts, Vector()) / len(pts),
                pts,
            )
    return None

bb = {n: part_bbox(n) for n in ANATOMY.values()}
# Sanity
missing = [n for n, b in bb.items() if b is None]
if missing:
    raise RuntimeError(f"Missing anatomical parts: {missing}")

# Y center of body trunk (parts that face -Y) for symmetric X bone alignment
body_y = sum(bb[n][2].y for n in ('Body', 'ArmL', 'ArmR', 'LegL', 'LegR')) / 5
print(f"  Body-trunk Y center = {body_y:.3f}")

# Build armature object + data
arm_data = bpy.data.armatures.new("CatRigV2Data")
arm_obj  = bpy.data.objects.new("CatRigV2", arm_data)
bpy.context.collection.objects.link(arm_obj)
bpy.context.view_layer.objects.active = arm_obj
arm_obj.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
eb = arm_data.edit_bones

def newbone(name, head_v, tail_v, parent=None):
    b = eb.new(name)
    b.head = Vector(head_v)
    b.tail = Vector(tail_v)
    if parent and parent in eb:
        b.parent = eb[parent]
    return b

body_min, body_max, body_c, _ = bb['Body']
head_min, head_max, head_c, _ = bb['Head']
earL_min, earL_max, earL_c, _ = bb['EarL']
earR_min, earR_max, earR_c, _ = bb['EarR']
armL_min, armL_max, armL_c, _ = bb['ArmL']
armR_min, armR_max, armR_c, _ = bb['ArmR']
legL_min, legL_max, legL_c, _ = bb['LegL']
legR_min, legR_max, legR_c, _ = bb['LegR']
tail_min, tail_max, tail_c, tail_pts = bb['Tail']


# ---- Hips: lower body — bottom to ~70% up the body trunk ----
#      (Stopping at 70% leaves room for Spine to have meaningful length
#      despite the body/head Z overlap in chibi proportions.)
body_upper_z = body_min.z + 0.7 * (body_max.z - body_min.z)
hips_head = (body_c.x, body_y, body_min.z + 0.05)
hips_tail = (body_c.x, body_y, body_upper_z)
newbone("Hips", hips_head, hips_tail)

# ---- Spine: bridges body-upper → into the head bottom for breathing/bobble ----
spine_tail = (head_c.x, body_y, head_min.z + 0.10)
newbone("Spine", hips_tail, spine_tail, "Hips")

# ---- Head: from spine top up through the head ball ----
head_tail = (head_c.x, body_y, head_max.z - 0.10)
newbone("Head", spine_tail, head_tail, "Spine")

# ---- Ears (children of Head): from head-top attach point to ear tip ----
earL_attach = (-0.12, body_y, head_max.z - 0.10)
earL_tip    = (earL_c.x, earL_c.y, earL_max.z - 0.03)
newbone("EarL", earL_attach, earL_tip, "Head")

earR_attach = (+0.12, body_y, head_max.z - 0.10)
earR_tip    = (earR_c.x, earR_c.y, earR_max.z - 0.03)
newbone("EarR", earR_attach, earR_tip, "Head")

# ---- Arms (children of Spine): SHOULDER PIVOT to hand
#      Bone HEAD = top-inner corner of arm mesh = anatomical shoulder
#      Bone TAIL = outer-mid (hand area).
#      Putting head at shoulder (not mid-arm) makes arm rotations PIVOT
#      from the shoulder (correct), instead of swinging around mid-arm
#      (wrong — arm appears to "swing around its middle" rather than
#       "drop from shoulder").  ----
armL_head = (armL_max.x, body_y, armL_max.z + 0.03)   # raised shoulder (was -0.02 below arm top, now +3cm above)
armL_tail = (armL_min.x, body_y, armL_c.z)
newbone("ArmL", armL_head, armL_tail, "Spine")

armR_head = (armR_min.x, body_y, armR_max.z + 0.03)
armR_tail = (armR_max.x, body_y, armR_c.z)
newbone("ArmR", armR_head, armR_tail, "Spine")

# ---- Legs (children of Hips): hip→foot vertical ----
legL_head = (legL_c.x, body_y, legL_max.z)
legL_tail = (legL_c.x, body_y, legL_min.z + 0.02)
newbone("LegL", legL_head, legL_tail, "Hips")

legR_head = (legR_c.x, body_y, legR_max.z)
legR_tail = (legR_c.x, body_y, legR_min.z + 0.02)
newbone("LegR", legR_head, legR_tail, "Hips")

# ---- Tail (child of Hips): 4 bones along root.7 spine ----
# Tail extends in +Y, sort verts by Y ascending (base=min Y, tip=max Y)
tail_sorted = sorted(tail_pts, key=lambda v: v.y)
n_t = len(tail_sorted)
tail_spine_pts = []
for i in range(5):
    chunk = tail_sorted[i * n_t // 5 : (i + 1) * n_t // 5]
    if not chunk:
        chunk = [tail_sorted[min(i * n_t // 5, n_t - 1)]]
    cx = sum(p.x for p in chunk) / len(chunk)
    cy = sum(p.y for p in chunk) / len(chunk)
    cz = sum(p.z for p in chunk) / len(chunk)
    tail_spine_pts.append(Vector((cx, cy, cz)))
print(f"  Tail spine pts: {[tuple(round(c,2) for c in p) for p in tail_spine_pts]}")

newbone("Tail1", tail_spine_pts[0], tail_spine_pts[1], "Hips")
newbone("Tail2", tail_spine_pts[1], tail_spine_pts[2], "Tail1")
newbone("Tail3", tail_spine_pts[2], tail_spine_pts[3], "Tail2")
newbone("Tail4", tail_spine_pts[3], tail_spine_pts[4], "Tail3")

bpy.ops.object.mode_set(mode='OBJECT')

# ---- Print bone hierarchy tree ----
def print_tree(bone, depth=0):
    h = bone.head_local; t = bone.tail_local
    print(f"  {'  '*depth}└─ {bone.name:8s} head=({h.x:+.2f},{h.y:+.2f},{h.z:+.2f}) tail=({t.x:+.2f},{t.y:+.2f},{t.z:+.2f})")
    for child in bone.children:
        print_tree(child, depth + 1)

print(f"\n  Built {len(arm_data.bones)} bones:")
for root in [b for b in arm_data.bones if b.parent is None]:
    print_tree(root)

# =====================================================================
# Step 4: Rigid skinning — bind each anatomical mesh to its bone at 100%
# =====================================================================
print("\n[4] Rigid-skin each mesh to its target bone")

# anatomy → target bone (Body → Spine so chest moves during breathing)
SKIN_MAP = {
    "EarL": "EarL", "EarR": "EarR",
    "ArmL": "ArmL", "ArmR": "ArmR",
    "LegL": "LegL", "LegR": "LegR",
    "Head": "Head",
    "Body": "Spine",
    # Tail handled separately (distribution across 4 bones)
}

def rigid_bind(mesh, bone_name):
    # Parent mesh to armature
    mesh.parent = arm_obj
    # Remove any existing armature modifiers, vertex groups
    for mod in list(mesh.modifiers):
        if mod.type == 'ARMATURE':
            mesh.modifiers.remove(mod)
    for vg in list(mesh.vertex_groups):
        mesh.vertex_groups.remove(vg)
    # Fresh armature modifier
    mod = mesh.modifiers.new("Armature", type='ARMATURE')
    mod.object = arm_obj
    # All verts → 100% target bone
    vg = mesh.vertex_groups.new(name=bone_name)
    vg.add(list(range(len(mesh.data.vertices))), 1.0, 'REPLACE')

for m in meshes:
    anatomy = m.get("anatomy")
    if anatomy == "Tail":
        continue  # handled below
    bone = SKIN_MAP.get(anatomy)
    if bone:
        rigid_bind(m, bone)
        print(f"  {m.name:8s} ({anatomy}) → 100% {bone}")
    else:
        print(f"  [warn] no bone mapping for {m.name} ({anatomy})")

# Tail: distribute verts across Tail1..Tail4 by Y position quartiles
# (base = low Y, tip = high Y; quartile 0 → Tail1 base, quartile 3 → Tail4 tip)
tail_mesh = next((m for m in meshes if m.get("anatomy") == "Tail"), None)
if tail_mesh:
    tail_mesh.parent = arm_obj
    for mod in list(tail_mesh.modifiers):
        if mod.type == 'ARMATURE':
            tail_mesh.modifiers.remove(mod)
    for vg in list(tail_mesh.vertex_groups):
        tail_mesh.vertex_groups.remove(vg)
    mod = tail_mesh.modifiers.new("Armature", type='ARMATURE')
    mod.object = arm_obj
    verts_y = [(i, (tail_mesh.matrix_world @ v.co).y) for i, v in enumerate(tail_mesh.data.vertices)]
    verts_y.sort(key=lambda p: p[1])
    n_t = len(verts_y)
    for bi, bone_name in enumerate(["Tail1", "Tail2", "Tail3", "Tail4"]):
        chunk = verts_y[bi * n_t // 4 : (bi + 1) * n_t // 4]
        indices = [p[0] for p in chunk]
        vg = tail_mesh.vertex_groups.new(name=bone_name)
        vg.add(indices, 1.0, 'REPLACE')
        print(f"  {tail_mesh.name:8s} (Tail) chunk {bi+1}/4: {len(indices)} verts → 100% {bone_name}")

# =====================================================================
# Step 5: Apply a test pose + render rest AND test for skin verification
# =====================================================================
print("\n[5] Render rest pose + test pose (EEVEE)")

# Compute scene bbox to frame camera
all_pts = []
for m in meshes:
    all_pts.extend(m.matrix_world @ v.co for v in m.data.vertices)
xs = [p.x for p in all_pts]; ys = [p.y for p in all_pts]; zs = [p.z for p in all_pts]
target = Vector((sum(xs)/len(xs), sum(ys)/len(ys), sum(zs)/len(zs)))
zr = max(zs) - min(zs)
print(f"  Scene bbox: X[{min(xs):+.2f},{max(xs):+.2f}] Y[{min(ys):+.2f},{max(ys):+.2f}] Z[{min(zs):+.2f},{max(zs):+.2f}]  Z-range={zr:.2f}")

# Remove any default camera/light
for o in list(bpy.data.objects):
    if o.type in ('CAMERA', 'LIGHT'):
        bpy.data.objects.remove(o, do_unlink=True)

# Camera: front-right-up vantage so we see the face (which is at -Y)
cam_data = bpy.data.cameras.new("Cam")
cam_data.type = "ORTHO"
cam_data.ortho_scale = zr * 1.4
cam_obj = bpy.data.objects.new("Cam", cam_data)
bpy.context.collection.objects.link(cam_obj)
# Position camera in front-right-up (face at -Y, so camera at -Y to see face)
cam_obj.location = target + Vector((zr*1.6, -zr*2.0, zr*0.3))
d = target - Vector(cam_obj.location)
cam_obj.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
bpy.context.scene.camera = cam_obj

# Sun light
light = bpy.data.lights.new("Sun", type="SUN")
light.energy = 3.0
lo = bpy.data.objects.new("Sun", light)
bpy.context.collection.objects.link(lo)
lo.location = (3, -3, 4)
lo.rotation_euler = (math.radians(50), math.radians(20), math.radians(-30))

# Scene render settings
scene = bpy.context.scene
try:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
except Exception:
    scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 600
scene.render.resolution_y = 800
scene.world = scene.world or bpy.data.worlds.new("World")
scene.world.use_nodes = True
bg = scene.world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.85, 0.95, 0.78, 1.0)

# Pose helpers
def reset_pose():
    bpy.context.view_layer.objects.active = arm_obj
    arm_obj.select_set(True)
    bpy.ops.object.mode_set(mode='POSE')
    for pb in arm_obj.pose.bones:
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = (0, 0, 0)
        pb.location = (0, 0, 0)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.context.view_layer.update()

def apply_pose(rots):
    """rots = list of (bone_name, axis_idx 0/1/2, degrees)"""
    reset_pose()
    bpy.context.view_layer.objects.active = arm_obj
    arm_obj.select_set(True)
    bpy.ops.object.mode_set(mode='POSE')
    for bn, ax, deg in rots:
        if bn in arm_obj.pose.bones:
            pb = arm_obj.pose.bones[bn]
            pb.rotation_mode = 'XYZ'
            pb.rotation_euler[ax] = math.radians(deg)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.context.view_layer.update()

# (a) Rest pose
apply_pose([])
out_rest = os.path.join(VERIFY_DIR, "v2_step3_rest.png")
scene.render.filepath = out_rest
bpy.ops.render.render(write_still=True)
print(f"  Rendered rest pose: {out_rest}")

# (b) Test pose: Head yaw (local Y = vertical) +30°, Tail1 side-wag (local Z) +20°
apply_pose([
    ("Head",  1, 30),
    ("Tail1", 2, 20),
])
out_test = os.path.join(VERIFY_DIR, "v2_step3_test.png")
scene.render.filepath = out_test
bpy.ops.render.render(write_still=True)
print(f"  Rendered test pose (Head Y+30°, Tail1 Z+20°): {out_test}")

# Reset before save
apply_pose([])

# =====================================================================
# Step 6: Save .blend
# =====================================================================
BLEND_OUT_V2 = r"E:\05_claude\CGmiaomiao\miaomoaguge_v2_skinned.blend"
print(f"\n[6] Save → {BLEND_OUT_V2}")
bpy.ops.wm.save_as_mainfile(filepath=BLEND_OUT_V2)

print("\n[step 3 complete]")
