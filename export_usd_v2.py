"""Export the CURRENT v2 animated rig as a Quick-Look-ready USDZ for iOS AR.

The old export_usd.py opened the v1 Tripo blend (CatRig/CatBody) — that's why
the deployed character_v2.usdz was a stale, pre-v2 model. This opens the live
v2 animated blend instead.

Quick Look plays a single timeline animation, so we isolate the IDLE NLA track
(the looping breathe/tail/ear life) and export just that as a clean loop —
exactly what you want for "the cat is sitting here in my room". Scaled to the
same ~0.14 m as the GLB, Y-up for Quick Look, textures packed into the usdz.

Blender packages a .usdz automatically when the filepath ends in .usdz
(textures embedded, usdc first entry) — more robust than hand-zipping.
"""
import bpy

BLEND_IN  = r"E:\05_claude\CGmiaomiao\miaomoaguge_v2_animated.blend"
USDZ_OUT  = r"E:\05_claude\CGmiaomiao\ar\public\character_v2.usdz"  # Vite serves public/ at site root
TARGET_HEIGHT_M = 0.14

print(f"[1] open {BLEND_IN}")
bpy.ops.wm.open_mainfile(filepath=BLEND_IN)

arm = bpy.data.objects.get("CatRigV2") or next(o for o in bpy.data.objects if o.type == "ARMATURE")
print(f"  armature: {arm.name}")

# ---- Isolate the idle loop on the NLA so the USD timeline is a clean idle ----
ad = arm.animation_data
if ad and ad.nla_tracks:
    for tr in ad.nla_tracks:
        tr.mute = (tr.name != "idle")
    print("  isolated idle NLA track")
scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = 61          # idle period is 60 frames

# ---- Scale to ~0.14 m via a root empty (same approach as the GLB export) ----
hz = [(m.matrix_world @ v.co).z for m in bpy.data.objects
      if m.type == "MESH" for v in m.data.vertices]
scale = TARGET_HEIGHT_M / (max(hz) - min(hz))
root = bpy.data.objects.new("MiaoRootUSD", None)
bpy.context.collection.objects.link(root)
root.scale = (scale, scale, scale)
arm.parent = root
print(f"  rig height {max(hz)-min(hz):.3f} -> scale x{scale:.4f}")

# ---- Drop EXR helper images: Quick Look does NOT support EXR and may reject
#      the whole usdz if one is embedded (color_0C0C0C is a constant-gray
#      helper — losing it is cosmetically negligible). Match broadly by
#      file_format / name / path since the datablock name may lack ".exr". ----
for img in list(bpy.data.images):
    print(f"  image: name='{img.name}' fmt={img.file_format} path='{img.filepath}'")
for img in list(bpy.data.images):
    nm = (img.filepath or "") + " " + (img.name or "")
    if img.file_format == "OPEN_EXR" or ".exr" in nm.lower() or "0C0C0C" in nm or "0c0c0c" in nm.lower():
        try: bpy.data.images.remove(img); print(f"  dropped EXR helper: {img.name}")
        except Exception as e: print(f"  [warn] could not drop {img.name}: {e}")

# ---- Slim textures to 1024 (the saved blend still has full-size source) ----
for img in bpy.data.images:
    if max(img.size) > 1024:
        try: img.scale(1024, 1024)
        except Exception as e: print(f"  [warn] resize {img.name}: {e}")

# ---- Select root + armature + meshes (USD export honors selection) ----
for o in bpy.data.objects:
    try: o.select_set(False)
    except: pass
root.select_set(True); arm.select_set(True)
bpy.context.view_layer.objects.active = arm
for m in bpy.data.objects:
    if m.type == "MESH":
        m.select_set(True)

# ---- Export. Try the full Y-up + textures kwargs; fall back if this Blender
#      build names them differently. ----
base = dict(
    filepath=USDZ_OUT,
    selected_objects_only=True,
    export_animation=True,
    export_meshes=True,
    export_materials=True,
    export_armatures=True,
    export_shapekeys=False,
    use_instancing=False,
)
attempts = [
    # Y-up for Quick Look (ARKit). Blender's enum wants NEGATIVE_Z, not -Z.
    dict(base, convert_orientation=True,
         export_global_forward_selection="NEGATIVE_Z", export_global_up_selection="Y"),
    base,
]
ok = False
for i, kw in enumerate(attempts):
    try:
        bpy.ops.wm.usd_export(**kw)
        print(f"  USDZ exported (attempt {i+1}, {len(kw)} kwargs)")
        ok = True
        break
    except (TypeError, RuntimeError) as e:
        print(f"  [attempt {i+1} failed] {e}")
if not ok:
    raise SystemExit("USD export failed on all kwarg sets")

import os
print(f"[2] USDZ size: {os.path.getsize(USDZ_OUT)/1024/1024:.2f} MB -> {USDZ_OUT}")
print("done")
