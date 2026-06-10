"""animate_v2.py — Author animations for the new PBR rig (v2 bone names).

Bone name map vs old animate_and_export.py:
  Old Mixamo-compat → New simplified
  LeftArm/RightArm     → ArmL/ArmR
  Hips                 → Hips (same)
  Spine, Spine1..      → Spine (only one)
  Head                 → Head (same)
  EarL/EarR            → EarL/EarR (same)
  Tail1..Tail4         → Tail1..Tail4 (same)

Model differences:
  - Faces -Y (was +X)        → forward/back swings happen on world Y, not X
  - Scale ~2× larger         → translations 2× of old
  - 1 spine bone (was 4)     → simpler spine curves

Bone local axes (from rest pose, axis indices for rotation_euler):
  Head    (vertical, +Z bone direction): X=nod  Y=yaw  Z=tilt
  Spine   (vertical):                    X=lean Y=twist Z=side-bend
  Hips    (vertical):                    same as Spine
  ArmL/R  (horizontal X bone direction): X=twist Y=swing-forward-back Z=raise-up-down
  EarL/R  (mostly vertical):             X=tilt-forward/back  Y=twist  Z=tilt-sideways
  Tail1..4 (along +Y from base):         X=lift-up/down  Y=twist  Z=side-wag

(Axis-to-motion mapping may need empirical verification — first render reveals if
 axis indices are wrong, then we swap.)
"""

import bpy, math, os
from mathutils import Vector

BLEND_IN  = r"E:\05_claude\CGmiaomiao\miaomoaguge_v2_skinned.blend"
BLEND_OUT = r"E:\05_claude\CGmiaomiao\miaomoaguge_v2_animated.blend"
VERIFY_DIR = r"E:\05_claude\CGmiaomiao\verify"
os.makedirs(VERIFY_DIR, exist_ok=True)

print(f"\n[1] Open {BLEND_IN}")
bpy.ops.wm.open_mainfile(filepath=BLEND_IN)

arm = bpy.data.objects.get("CatRigV2")
if arm is None:
    arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
print(f"  Armature: {arm.name}  bones: {len(arm.data.bones)}")

bpy.context.view_layer.objects.active = arm
arm.select_set(True)

if arm.animation_data is None:
    arm.animation_data_create()

X, Y, Z = 0, 1, 2

# ---- Helpers ----
def bind_action(name):
    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    arm.animation_data.action = action
    # Blender 5 slot-based actions
    if hasattr(action, 'slots'):
        if len(action.slots) == 0:
            try: action.slots.new(id_type='OBJECT', name=arm.name)
            except: pass
        if hasattr(arm.animation_data, 'action_slot') and len(action.slots) > 0:
            try: arm.animation_data.action_slot = action.slots[0]
            except: pass
    return action

def kf_rot(bone, frame, axis, deg):
    pb = arm.pose.bones[bone]
    pb.rotation_mode = "XYZ"
    pb.rotation_euler[axis] = math.radians(deg)
    pb.keyframe_insert("rotation_euler", frame=frame, index=axis)

def kf_loc(bone, frame, axis, value):
    pb = arm.pose.bones[bone]
    pb.location[axis] = value
    pb.keyframe_insert("location", frame=frame, index=axis)

def sin_rot(bone, period, phase_deg, amp_deg, axis, samples=10, frame_offset=0, baseline=0):
    for i in range(samples + 1):
        f = frame_offset + i * (period / samples)
        t = (f - frame_offset) / period
        val_deg = baseline + amp_deg * math.sin(math.radians(phase_deg) + 2 * math.pi * t)
        kf_rot(bone, int(round(f)), axis, val_deg)

# ---- Set rotation_mode on all pose bones ----
for pb in arm.pose.bones:
    pb.rotation_mode = "XYZ"

# =====================================================================
# IDLE — 60 frames @ 24fps = 2.5s
#
# Design (mirrors original animate_and_export.py's idle, adapted for v2):
#   - Asymmetric breath: slow inhale (0→36), fast exhale (36→60)
#   - Hips Z bob 9cm peak (was 4.5cm; doubled for 2× scale)
#   - Spine micro-rotation around X for chest expansion sync with breath
#   - Head yaw (Y axis) bobble, lagged 9 frames behind body
#   - Head nod (X axis) very subtle
#   - Tail1..4 phased Z side-wag with amp decay along chain
#   - Occasional ear flicks (EarL @ ~1s, EarR @ ~2s)
# =====================================================================
print("\n[2] Author IDLE (60 frames)")
idle = bind_action("idle")
period = 60

# Reset all pose bones to rest
for pb in arm.pose.bones:
    pb.rotation_euler = (0, 0, 0)
    pb.location = (0, 0, 0)
    pb.scale = (1, 1, 1)

# ---- Arms-droop baseline (verified via probe_arm_axes_v2.py):
#      Both arms: local X = ±Y world (back-front axis).  Rotating X=-30°
#      drops the arm from horizontal outward to slight down-and-inward —
#      a stubby chibi-rest pose, still clearly visible outside the body
#      silhouette.  X=-60° tucks the arm INTO the body (Z=0.21 below body
#      bottom + X=-0.30 inside body edge), which is why arms vanished. ----
ARM_DROOP_L = -20    # X-axis rotation (drop angle)
ARM_DROOP_R = -20
ARM_OUTWARD  = 0.05  # local-Y translation (5cm along bone direction = outward)
ARM_RAISE    = 0.05  # local-Z translation (5cm up; local Z = world +Z for arm bones)

# ---- Asymmetric breath: Hips Z bob, peak at frame 36 (60% of period) ----
kf_loc("Hips", 0,      Y, 0)
kf_loc("Hips", 36,     Y, 0.11)   # peak inhale (v5: 9→11cm, livelier breath) — Hips is a vertical bone,
                                   # so local Y (bone direction) = world +Z = up
kf_loc("Hips", period, Y, 0)

# ---- Chest expansion: Spine X rotation, sync with breath ----
kf_rot("Spine", 0,      X, 0)
kf_rot("Spine", 36,     X, -3)   # lean back slightly during inhale
kf_rot("Spine", period, X, 0)

# ---- Head yaw bobble: 9-frame lag behind body breath, gentle ±5° ----
def head_y(f):
    t = (f - 9) / period
    return 7.0 * math.sin(2 * math.pi * t)   # v5: 5→7° head bobble
for f in range(0, period+1, 5):
    kf_rot("Head", f, Y, head_y(f))

# ---- Head subtle nod (X axis) + tilt (Z axis) ----
sin_rot("Head", period, 90, 2.5, X, samples=8)   # nod
sin_rot("Head", period,  0, 2.0, Z, samples=8)   # tilt

# ---- Tail rubber wag (Z axis side-wag), amplitude decay along chain ----
tail_amps   = [24.0, 20.0, 16.0, 12.0]   # v5: bigger, livelier tail rubber-wave
tail_phases = [0, 45, 90, 135]   # phase delay → rubber-band wave
for i, tb in enumerate(["Tail1","Tail2","Tail3","Tail4"]):
    sin_rot(tb, period, tail_phases[i], tail_amps[i], Z, samples=10)

# ---- Arms: droop (rotation X) + outward shift (translation along local Y)
#      both held constant across the cycle, with small breath sway on X. ----
sin_rot("ArmL", period, 0, 3.0, X, samples=8, baseline=ARM_DROOP_L)
sin_rot("ArmR", period, 0, 3.0, X, samples=8, baseline=ARM_DROOP_R)
for f in [0, period]:
    kf_loc("ArmL", f, Y, ARM_OUTWARD)
    kf_loc("ArmR", f, Y, ARM_OUTWARD)
    kf_loc("ArmL", f, Z, ARM_RAISE)
    kf_loc("ArmR", f, Z, ARM_RAISE)

# ---- Legs: tiny side-to-side weight shift, opposite phase per leg ----
sin_rot("LegL", period,   0, 2.0, Z, samples=8)
sin_rot("LegR", period, 180, 2.0, Z, samples=8)

# ---- Subtle slow weight-shift: one slow Hips roll + Spine counter-twist
#      per cycle. Breaks the perfectly-static-trunk look so idle reads as
#      a live body quietly settling its weight, not a breathing statue. ----
sin_rot("Hips",  period,  0, 4.0, Z, samples=10)   # v5: 2.5→4° weight-shift
sin_rot("Spine", period, 90, 2.0, Y, samples=10)

# ---- Ear flicks: very gentle, short ----
# EarL flicks around frame 24 (~1s)
for f, val in [(0,0), (20,0), (24,-8), (28,-2), (32,0), (period,0)]:
    kf_rot("EarL", f, X, val)
# EarR flicks around frame 50 (~2s)
for f, val in [(0,0), (46,0), (50,-7), (54,-1), (58,0), (period,0)]:
    kf_rot("EarR", f, X, val)


print(f"  idle action: {len(idle.fcurves) if hasattr(idle, 'fcurves') else 'slot-based'} curves")

# =====================================================================
# WALK — 30 frames @ 24fps = 1.25s, chibi waddle loop (simplest first)
#
# Core: legs alternate forward-back, arms counter-swing.
# Leg axes (probed): LegL/R local X = world +X, so X-rotation = forward-back.
#   -X rotation = forward (toward -Y world, character faces -Y).
#   Phase 270° starts at sin(270°)=-1 → val=-25 at f=0 → forward.
# Arm axes: ArmL Z+ = forward (-Y), ArmR Z+ = backward.  Same Z phase 270°
#   for both arms gives ArmL=back / ArmR=forward at f=0 — natural counter.
# =====================================================================
print("\n[2b] Author WALK (30 frames)")
walk = bind_action("walk")
period_walk = 30

# Reset pose bones to rest before authoring walk
for pb in arm.pose.bones:
    pb.rotation_euler = (0, 0, 0)
    pb.location = (0, 0, 0)
    pb.scale = (1, 1, 1)

# Arms baseline (same droop/outward/up as idle so character pose is consistent)
for f in [0, period_walk]:
    kf_rot("ArmL", f, X, ARM_DROOP_L)
    kf_rot("ArmR", f, X, ARM_DROOP_R)
    kf_loc("ArmL", f, Y, ARM_OUTWARD)
    kf_loc("ArmR", f, Y, ARM_OUTWARD)
    kf_loc("ArmL", f, Z, ARM_RAISE)
    kf_loc("ArmR", f, Z, ARM_RAISE)

# Leg forward-back swing (back to 25° — user's note was about position, not amp)
sin_rot("LegL", period_walk, 270, 25, X, samples=12)
sin_rot("LegR", period_walk,  90, 25, X, samples=12)

# Hips Z dip — drops body when legs are at peak swing (foot would lift),
# so feet stay on the ground.  At 25° swing, foot lifts (1-cos(25°))*0.64m
# ≈ 6cm, so Hips dips up to -6cm with |cos| timing (dip at t=0, 0.5 when
# legs are at extreme swing; back to 0 at t=0.25, 0.75 when legs at rest).
import math as _m_walk
for i in range(period_walk + 1):
    t = i / period_walk
    val = -0.06 * abs(_m_walk.cos(2 * _m_walk.pi * t))
    kf_loc("Hips", i, Y, val)

# Arm counter-swing
sin_rot("ArmL", period_walk, 270, 10, Z, samples=12)
sin_rot("ArmR", period_walk, 270, 10, Z, samples=12)

# ---- WALK POLISH: waddle + head bob + tail + ears ----

# Hips side-to-side waddle: local Z rotation = side roll for the vertical
# Hips bone.  One full rock per walk cycle, ±5°.
sin_rot("Hips", period_walk, 0, 4, Z, samples=12)   # smaller waddle — ±7° over-read as a full-body roll

# Head nod: X-axis, ±3°, 2× frequency (one nod per footfall, synced with
# the Hips dip which also peaks twice per cycle).
for i in range(period_walk + 1):
    t = i / period_walk
    kf_rot("Head", i, X, 4.5 * _m_walk.sin(2 * 2 * _m_walk.pi * t))   # v5: 3→4.5° head bob

# Tail counter-swing: phased Z-wag across the 4 segments (lighter than idle).
tail_amps_walk   = [18, 14, 11, 8]   # v5: livelier walk tail
tail_phases_walk = [0, 40, 80, 120]
for i, tb in enumerate(["Tail1", "Tail2", "Tail3", "Tail4"]):
    sin_rot(tb, period_walk, tail_phases_walk[i], tail_amps_walk[i], Z, samples=12)

# Ear bounce: X-axis, small, 2× frequency (bounce on each footfall).
for i in range(period_walk + 1):
    t = i / period_walk
    val = -2.0 + 4.0 * _m_walk.cos(2 * 2 * _m_walk.pi * t)   # oscillates +2..-6
    kf_rot("EarL", i, X, val)
    kf_rot("EarR", i, X, val)

print(f"  walk action authored (with waddle/head/tail/ears polish)")

# =====================================================================
# RUN — 18 frames @ 24fps = 0.75s, fast chibi sprint
#
# Same structure as walk, scaled up: bigger leg/arm swings, forward body
# lean, ears pinned back, tail streaming.
# =====================================================================
print("\n[2c] Author RUN (18 frames)")
run = bind_action("run")
period_run = 18

for pb in arm.pose.bones:
    pb.rotation_euler = (0, 0, 0)
    pb.location = (0, 0, 0)
    pb.scale = (1, 1, 1)

# Arms baseline (droop + outward + up)
for f in [0, period_run]:
    kf_rot("ArmL", f, X, ARM_DROOP_L)
    kf_rot("ArmR", f, X, ARM_DROOP_R)
    kf_loc("ArmL", f, Y, ARM_OUTWARD)
    kf_loc("ArmR", f, Y, ARM_OUTWARD)
    kf_loc("ArmL", f, Z, ARM_RAISE)
    kf_loc("ArmR", f, Z, ARM_RAISE)

# Forward lean — running posture (bigger so run clearly out-reads walk at this cam)
for f in [0, period_run]:
    kf_rot("Hips", f, X, 15)

# Leg swing — much bigger than walk (wider stride reach)
sin_rot("LegL", period_run, 270, 40, X, samples=12)
sin_rot("LegR", period_run,  90, 40, X, samples=12)

# Hips Z dip — bigger, synced to leg extremes
for i in range(period_run + 1):
    t = i / period_run
    kf_loc("Hips", i, Y, -0.09 * abs(_m_walk.cos(2 * _m_walk.pi * t)))

# Arm counter-swing — bigger
sin_rot("ArmL", period_run, 270, 20, Z, samples=12)
sin_rot("ArmR", period_run, 270, 20, Z, samples=12)

# Head leans forward (determined sprint look — bigger)
for f in [0, period_run]:
    kf_rot("Head", f, X, 11)

# Tail streaming back — gentle Z wag, less than walk
for tb in ["Tail1", "Tail2", "Tail3", "Tail4"]:
    sin_rot(tb, period_run, 0, 8, Z, samples=12)

# Ears pinned back
for f in [0, period_run]:
    kf_rot("EarL", f, X, -15)
    kf_rot("EarR", f, X, -15)

print(f"  run action authored")

# =====================================================================
# ATTACK — 36 frames one-shot (windup → strike → recover)
#   0  rest    8  windup (crouch + cock ArmR back)
#   16 strike (ArmR punches forward + body thrust)    22 hold    36 rest
# =====================================================================
print("\n[2d] Author ATTACK (36 frames)")
attack = bind_action("attack")
period_attack = 36

for pb in arm.pose.bones:
    pb.rotation_euler = (0, 0, 0)
    pb.location = (0, 0, 0)
    pb.scale = (1, 1, 1)

# Arm translations constant; ArmL X droop baseline at endpoints
for f in [0, period_attack]:
    kf_loc("ArmL", f, Y, ARM_OUTWARD); kf_loc("ArmR", f, Y, ARM_OUTWARD)
    kf_loc("ArmL", f, Z, ARM_RAISE);   kf_loc("ArmR", f, Z, ARM_RAISE)
    kf_rot("ArmL", f, X, ARM_DROOP_L)

# Hips: small crouch-back windup → a COMMITTED (not somersault) forward lunge
# → tiny snap-back. v7 stacked Hips+Spine+Head pitch into a ~70° flip; keep the
# SUM modest (the three bones compound) so it reads as a lunge, not a tumble.
for f, v in [(0,0),(8,-8),(16,14),(22,-3),(period_attack,0)]:
    kf_rot("Hips", f, X, v)
for f, v in [(0,0),(8,-6),(16,10),(22,-2),(period_attack,0)]:
    kf_rot("Spine", f, X, v)
# Hips drive DOWN+forward on the strike (a pounce goes LOW, not airborne) — the
# strike frame is the lowest point, never positive (old +0.04 floated it).
for f, v in [(0,0),(8,-0.02),(16,-0.05),(22,-0.02),(period_attack,0)]:
    kf_loc("Hips", f, Y, v)

# Right arm punch — the HERO beat, the ONLY real attack signal. Big windup back
# then a fast forward jab (Z- = forward for ArmR); the body follows the arm.
for f, v in [(0,0),(8,38),(16,-50),(22,-40),(period_attack,0)]:
    kf_rot("ArmR", f, Z, v)
# Right arm cocks back then drives up+forward with the jab (~+35° abs raise)
for f, v in [(0,ARM_DROOP_R),(8,ARM_DROOP_R+25),(16,ARM_DROOP_R+55),(22,ARM_DROOP_R+45),(period_attack,ARM_DROOP_R)]:
    kf_rot("ArmR", f, X, v)

# Left arm slight counter-swing
for f, v in [(0,0),(8,-10),(16,14),(period_attack,0)]:
    kf_rot("ArmL", f, Z, v)

# Head leads forward only a touch — small, so it doesn't faceplant into the flip
for f, v in [(0,0),(8,-8),(16,12),(22,-2),(period_attack,0)]:
    kf_rot("Head", f, X, v)

# Tail snaps with the strike
for f, v in [(0,0),(8,-28),(16,28),(period_attack,0)]:
    kf_rot("Tail1", f, Z, v)
for f, v in [(0,0),(8,-20),(16,20),(period_attack,0)]:
    kf_rot("Tail2", f, Z, v)

# Ears flatten aggressive
for f, v in [(0,0),(8,-22),(22,-18),(period_attack,0)]:
    kf_rot("EarL", f, X, v); kf_rot("EarR", f, X, v)

print(f"  attack action authored")

# =====================================================================
# HURT — 24 frames one-shot (recoil → guard → recover)
#   0 rest   3 impact (body+head whip back)   10 max recoil (arms guard up)
#   18 recover   24 rest
# =====================================================================
print("\n[2e] Author HURT (24 frames)")
hurt = bind_action("hurt")
period_hurt = 24

for pb in arm.pose.bones:
    pb.rotation_euler = (0, 0, 0)
    pb.location = (0, 0, 0)
    pb.scale = (1, 1, 1)

# Arm translations constant
for f in [0, period_hurt]:
    kf_loc("ArmL", f, Y, ARM_OUTWARD); kf_loc("ArmR", f, Y, ARM_OUTWARD)
    kf_loc("ArmL", f, Z, ARM_RAISE);   kf_loc("ArmR", f, Z, ARM_RAISE)

# Sharp SMALL flinch — peak EARLY (f4), fast-in/slow-out. The old -20 Hips +
# -30 Head stacked to near-horizontal ("knocked flat"); halve it to a recoil.
for f, v in [(0,0),(4,-10),(10,-9),(18,-5),(period_hurt,0)]:
    kf_rot("Hips", f, X, v)
for f, v in [(0,0),(4,-16),(10,-14),(18,-7),(period_hurt,0)]:
    kf_rot("Head", f, X, v)

# Ground-anchor the hit: a small Hips sink sells weight instead of floating
for f, v in [(0,0),(4,-0.05),(10,-0.04),(18,-0.01),(period_hurt,0)]:
    kf_loc("Hips", f, Y, v)

# Arms fly UP to guard the face (~+45° abs — bold now that the +20 cap is known
# bogus) AND swing forward (Z) so the paws cover in FRONT: a real flinch/cover.
for f, v in [(0,ARM_DROOP_L),(4,ARM_DROOP_L+65),(10,ARM_DROOP_L+65),(18,ARM_DROOP_L+30),(period_hurt,ARM_DROOP_L)]:
    kf_rot("ArmL", f, X, v)
for f, v in [(0,ARM_DROOP_R),(4,ARM_DROOP_R+65),(10,ARM_DROOP_R+65),(18,ARM_DROOP_R+30),(period_hurt,ARM_DROOP_R)]:
    kf_rot("ArmR", f, X, v)
for f, v in [(0,0),(4,18),(10,16),(18,6),(period_hurt,0)]:
    kf_rot("ArmL", f, Z, v)      # ArmL+ = forward → paw crosses in front
for f, v in [(0,0),(4,-18),(10,-16),(18,-6),(period_hurt,0)]:
    kf_rot("ArmR", f, Z, v)      # ArmR- = forward → paw crosses in front

# Ears droop back (sad), HOLDING the droop into recovery so it doesn't snap perky
for f, v in [(0,0),(4,-30),(10,-35),(18,-22),(period_hurt,0)]:
    kf_rot("EarL", f, X, v); kf_rot("EarR", f, X, v)

# Tail droops down (X axis lift = down)
for f, v in [(0,0),(10,-28),(18,-12),(period_hurt,0)]:
    kf_rot("Tail1", f, X, v)
for f, v in [(0,0),(10,-22),(18,-9),(period_hurt,0)]:
    kf_rot("Tail2", f, X, v)

print(f"  hurt action authored")

# =====================================================================
# WAVE — 52 frames one-shot: friendly greeting, GROUNDED single-arm 招手
#   The cat stays PLANTED and faces front; ONE arm (right) raises to the
#   rig's safe limit and waves side-to-side ~4×. The rest of the body
#   adds gentle, SUBORDINATE life — a small forward lean, a slight weight
#   shift toward the waving side, a happy head tilt, perky ears, a tail
#   swish — so the arm doesn't read as "floating", WITHOUT the jump +
#   46° turn the old version used (that buried the gesture; it read as
#   "yay/flailing", not "hi 👋").
#   Rig limit: arm raise X caps at +20° absolute (ARM_DROOP+40); beyond
#   that the rigid stub arm detaches from the shoulder — so the wave is a
#   raised-out arm wagging on Z, not an overhead wave.
# =====================================================================
print("\n[2f] Author WAVE — grounded single-arm greeting (52 frames)")
wave = bind_action("wave")
period_wave = 52

for pb in arm.pose.bones:
    pb.rotation_euler = (0, 0, 0)
    pb.location = (0, 0, 0)
    pb.scale = (1, 1, 1)

# Arm translation baseline (rest droop offsets, held across the clip)
for f in [0, period_wave]:
    kf_loc("ArmL", f, Y, ARM_OUTWARD); kf_loc("ArmR", f, Y, ARM_OUTWARD)
    kf_loc("ArmL", f, Z, ARM_RAISE);   kf_loc("ArmR", f, Z, ARM_RAISE)

# ---- Grounded: NO jump. A small DOWN-settle bounce in rhythm with the wave
#      so the body has planted weight (the old up-beat floated it) ----
for f, v in [(0,0),(8,-0.03),(16,0.0),(26,-0.03),(36,0.0),(44,-0.02),(period_wave,0)]:
    kf_loc("Hips", f, Y, v)

# ---- A small eager lean-in only (the bigger held lean read as a recline) ----
for f, v in [(0,0),(10,4),(44,4),(period_wave,0)]:
    kf_rot("Hips", f, X, v)

# ---- Faint weight shift to the waving side (NOT a turn — stays facing front) ----
for f, v in [(0,0),(14,-4),(40,-4),(period_wave,0)]:
    kf_rot("Hips", f, Z, v)

# ---- Right arm: raise HIGH to ~+60° abs (verified clean — the old +20° cap
#      was bogus; the arm swings to horizontal with no shoulder detachment),
#      then a WIDE ~2.5-beat wave at ±42° on Z — a real, bold raised-hand hello ----
for f, v in [(0,ARM_DROOP_R),(8,ARM_DROOP_R+80),(44,ARM_DROOP_R+80),
             (50,ARM_DROOP_R),(period_wave,ARM_DROOP_R)]:
    kf_rot("ArmR", f, X, v)
for f, v in [(8,0),(16,44),(26,-40),(36,44),(44,0)]:
    kf_rot("ArmR", f, Z, v)

# ---- Left arm: pinned at rest droop, OUT of the way — only ONE hand waves
#      (the old sympathetic lift read as a competing second raised hand) ----
for f, v in [(0,ARM_DROOP_L),(period_wave,ARM_DROOP_L)]:
    kf_rot("ArmL", f, X, v)

# ---- Head: lift a touch (neg X = up), happy tilt toward the waving arm ----
for f, v in [(0,0),(10,-5),(40,-5),(period_wave,0)]:
    kf_rot("Head", f, X, v)
for f, v in [(0,0),(12,-10),(40,-10),(period_wave,0)]:
    kf_rot("Head", f, Z, v)

# ---- Tail: happy upward lift + gentle swish, lighter than idle ----
for f, v in [(0,0),(12,22),(44,20),(period_wave,0)]:
    kf_rot("Tail1", f, X, v)
for f, v in [(0,0),(12,16),(44,14),(period_wave,0)]:
    kf_rot("Tail2", f, X, v)
for tb, amp, ph in [("Tail1",16,0),("Tail2",13,40),("Tail3",10,80),("Tail4",8,120)]:
    sin_rot(tb, period_wave, ph, amp, Z, samples=16)

# ---- Ears: perk up and stay alert through the greeting ----
for f, v in [(0,0),(10,14),(44,12),(period_wave,0)]:
    kf_rot("EarL", f, X, v); kf_rot("EarR", f, X, v)

print(f"  wave action authored (grounded single-arm greeting)")

# =====================================================================
# HAPPY (撒娇) — 48 frames one-shot: affectionate wiggle
#   body sways L-R, head counter-tilts, arms raised wiggling, butt
#   bounces, tail swishes big.
# =====================================================================
print("\n[2g] Author HAPPY (48 frames)")
happy = bind_action("happy")
period_happy = 48

for pb in arm.pose.bones:
    pb.rotation_euler = (0, 0, 0)
    pb.location = (0, 0, 0)
    pb.scale = (1, 1, 1)

# Arm translations baseline
for f in [0, period_happy]:
    kf_loc("ArmL", f, Y, ARM_OUTWARD); kf_loc("ArmR", f, Y, ARM_OUTWARD)
    kf_loc("ArmL", f, Z, ARM_RAISE);   kf_loc("ArmR", f, Z, ARM_RAISE)

# Body sway (Hips Z roll) — 2 sways across the cycle
for i in range(period_happy + 1):
    t = i / period_happy
    kf_rot("Hips", i, Z, 12.0 * math.sin(2 * 2 * math.pi * t))   # v5: 9→12° bouncier sway
# Head counter-tilt (opposite to body) + happy nod
for i in range(period_happy + 1):
    t = i / period_happy
    kf_rot("Head", i, Z, -14.0 * math.sin(2 * 2 * math.pi * t))   # v5: 11→14°
sin_rot("Head", period_happy, 90, 5, X, samples=12)
# Butt bounce — 2 bouncier little hops
for i in range(period_happy + 1):
    t = i / period_happy
    kf_loc("Hips", i, Y, abs(math.sin(2 * 2 * math.pi * t)) * 0.11)   # bigger happy bounce
# Arms raised GENTLY toward the chest (~+28° abs) with a soft wiggle — a cute
# paws-up 撒娇, NOT flailing overhead (+50° read as 太夸张/over-the-top).
for f, v in [(0,ARM_DROOP_L),(12,ARM_DROOP_L+48),(36,ARM_DROOP_L+48),(period_happy,ARM_DROOP_L)]:
    kf_rot("ArmL", f, X, v)
for f, v in [(0,ARM_DROOP_R),(12,ARM_DROOP_R+48),(36,ARM_DROOP_R+48),(period_happy,ARM_DROOP_R)]:
    kf_rot("ArmR", f, X, v)
sin_rot("ArmL", period_happy,   0, 10, Z, samples=12)   # softer arm wiggle
sin_rot("ArmR", period_happy, 180, 10, Z, samples=12)
# Tail big happy swish (phased)
for tb, amp, ph in [("Tail1",28,0),("Tail2",24,40),("Tail3",20,80),("Tail4",16,120)]:
    sin_rot(tb, period_happy, ph, amp, Z, samples=14)
# Ears perk + wiggle
for f, v in [(0,0),(10,10),(24,4),(38,10),(period_happy,0)]:
    kf_rot("EarL", f, X, v); kf_rot("EarR", f, X, v)

print(f"  happy action authored")

# =====================================================================
# JUMP — 40 frames one-shot: full squash-and-stretch
#   0-8 crouch (anticipation)  8-14 launch  14-22 airborne
#   22-32 land (absorb)  32-40 recover
# Every part is coordinated: Hips arc, Spine compress/stretch, legs,
# arms swing, head dip/up, tail trail, ears flap.
# =====================================================================
print("\n[2h] Author JUMP (40 frames)")
jump = bind_action("jump")
period_jump = 40

for pb in arm.pose.bones:
    pb.rotation_euler = (0, 0, 0)
    pb.location = (0, 0, 0)
    pb.scale = (1, 1, 1)

for f in [0, period_jump]:
    kf_loc("ArmL", f, Y, ARM_OUTWARD); kf_loc("ArmR", f, Y, ARM_OUTWARD)
    kf_loc("ArmL", f, Z, ARM_RAISE);   kf_loc("ArmR", f, Z, ARM_RAISE)

# Hips Z — the jump arc (crouch down, launch, peak, fall, land dip, recover)
for f, v in [(0,0),(8,-0.16),(14,0.06),(19,0.34),(24,0.05),(30,-0.14),(34,0.02),(period_jump,0)]:
    kf_loc("Hips", f, Y, v)   # deeper crouch + land-dip so the arc reads as a real jump, not a hover
# Hips X — forward lean in crouch & landing, back during launch/air
for f, v in [(0,0),(8,13),(14,-9),(19,-5),(30,15),(period_jump,0)]:
    kf_rot("Hips", f, X, v)
# Spine — compress (crouch/land), stretch (launch/airborne)
for f, v in [(0,0),(8,11),(14,-9),(19,-7),(30,13),(period_jump,0)]:
    kf_rot("Spine", f, X, v)
# Legs — moderate bend/tuck (avoid clipping the body)
for leg in ("LegL", "LegR"):
    for f, v in [(0,0),(8,14),(14,-4),(19,12),(24,-5),(30,15),(34,4),(period_jump,0)]:
        kf_rot(leg, f, X, v)
# Arms — moderate raise (full body-arc carries the amplitude, not the arms)
for arm_b, droop in [("ArmL", ARM_DROOP_L), ("ArmR", ARM_DROOP_R)]:
    for f, dv in [(0,0),(8,-20),(14,38),(19,44),(24,24),(30,10),(period_jump,0)]:
        kf_rot(arm_b, f, X, droop + dv)
# Head — dip in crouch, up in air, dip on land
for f, v in [(0,0),(8,16),(14,-11),(19,-15),(24,-4),(30,16),(period_jump,0)]:
    kf_rot("Head", f, X, v)
# Tail — trails the body (X lift)
for f, v in [(0,0),(8,-30),(14,22),(19,36),(24,14),(30,-26),(period_jump,0)]:
    kf_rot("Tail1", f, X, v)
for f, v in [(0,0),(8,-22),(14,15),(19,27),(24,10),(30,-19),(period_jump,0)]:
    kf_rot("Tail2", f, X, v)
for f, v in [(0,0),(8,-15),(14,9),(19,18),(24,7),(30,-12),(period_jump,0)]:
    kf_rot("Tail3", f, X, v)
# Ears — flap up on launch, down on land
for f, v in [(0,0),(8,16),(14,-22),(19,-24),(30,20),(period_jump,0)]:
    kf_rot("EarL", f, X, v); kf_rot("EarR", f, X, v)

print(f"  jump action authored")

# =====================================================================
# SPIN — 36 frames one-shot: happy 360° twirl
#   windup → full yaw spin (with intermediate keys so the quaternion
#   takes the long way) → little hop → settle. Arms out, head up.
# =====================================================================
print("\n[2i] Author SPIN (36 frames)")
spin = bind_action("spin")
period_spin = 36

for pb in arm.pose.bones:
    pb.rotation_euler = (0, 0, 0)
    pb.location = (0, 0, 0)
    pb.scale = (1, 1, 1)

for f in [0, period_spin]:
    kf_loc("ArmL", f, Y, ARM_OUTWARD); kf_loc("ArmR", f, Y, ARM_OUTWARD)
    kf_loc("ArmL", f, Z, ARM_RAISE);   kf_loc("ArmR", f, Z, ARM_RAISE)

# Hips Y — full 360° yaw. Intermediate 90° keys so quaternion interp
# goes the long way (2-keyframe 0→360 would interpolate to no rotation).
for f, v in [(0,0),(4,-20),(10,90),(18,180),(26,270),(32,360),(period_spin,360)]:
    kf_rot("Hips", f, Y, v)
# Little hop through the spin
for f, v in [(0,0),(6,0.04),(18,0.13),(30,0.04),(period_spin,0)]:
    kf_loc("Hips", f, Y, v)
# Arms fling out and up during the spin
for arm_b, droop in [("ArmL", ARM_DROOP_L), ("ArmR", ARM_DROOP_R)]:
    for f, dv in [(0,0),(6,10),(10,45),(26,45),(32,12),(period_spin,0)]:
        kf_rot(arm_b, f, X, droop + dv)
# Head up + happy tilt
for f, v in [(0,0),(8,-12),(26,-12),(period_spin,0)]:
    kf_rot("Head", f, X, v)
for f, v in [(0,0),(10,12),(26,-12),(period_spin,0)]:
    kf_rot("Head", f, Z, v)
# Tail flails out (centrifugal)
for tb, amp in [("Tail1",30),("Tail2",26),("Tail3",22),("Tail4",18)]:
    for f, v in [(0,0),(6,-amp),(18,amp),(30,-amp),(period_spin,0)]:
        kf_rot(tb, f, Z, v)
# Ears flap out
for f, v in [(0,0),(8,14),(26,14),(period_spin,0)]:
    kf_rot("EarL", f, X, v); kf_rot("EarR", f, X, v)

print(f"  spin action authored")

# =====================================================================
# BACKFLIP — 48 frames one-shot: full 360° backward somersault
#   0-8 deep crouch  8-14 explosive launch  14-38 airborne full flip
#   38-44 land absorb  44-48 recover
# The flip is Hips X rotation 0→-360°; intermediate 90° keys force the
# quaternion to interpolate the long way (a bare 0→-360 collapses to no
# rotation). Hips is the root, so the whole character rotates; limb
# rotations below are relative to the flipping body (tuck).
# =====================================================================
print("\n[2j] Author BACKFLIP (48 frames)")
backflip = bind_action("backflip")
period_bf = 48

for pb in arm.pose.bones:
    pb.rotation_euler = (0, 0, 0)
    pb.location = (0, 0, 0)
    pb.scale = (1, 1, 1)

for f in [0, period_bf]:
    kf_loc("ArmL", f, Y, ARM_OUTWARD); kf_loc("ArmR", f, Y, ARM_OUTWARD)
    kf_loc("ArmL", f, Z, ARM_RAISE);   kf_loc("ArmR", f, Z, ARM_RAISE)

# ---- Centred flip. Rotating the root Hips bone alone pivots the whole
#      cat about the low hip point, so it swings around like a clock hand
#      instead of tumbling. We rotate about the body's vertical centre by
#      adding a per-frame counter-translation that cancels the circular
#      motion of that centre, leaving only the jump arc. For an X-rotation
#      of θ about a pivot r above the hip head:
#          Hips.locY = arc + r·(1−cosθ),  Hips.locZ = −r·sinθ
_bf_allz = []
for _m in [o for o in bpy.data.objects if o.type == 'MESH']:
    _bf_allz += [(_m.matrix_world @ _v.co).z for _v in _m.data.vertices]
r_flip = (min(_bf_allz) + max(_bf_allz)) / 2.0 - arm.data.bones["Hips"].head_local.z
print(f"  flip pivot raised by r_flip = {r_flip:.3f} (hip head -> body centre)")

def _lerp_kf(keys, fr):
    if fr <= keys[0][0]:  return keys[0][1]
    if fr >= keys[-1][0]: return keys[-1][1]
    for _i in range(len(keys) - 1):
        f0, v0 = keys[_i]; f1, v1 = keys[_i + 1]
        if f0 <= fr <= f1:
            return v0 + (v1 - v0) * (fr - f0) / (f1 - f0)
    return keys[-1][1]

bf_arc   = [(0,0),(8,-0.12),(14,0.10),(24,0.46),(34,0.12),(40,-0.10),(44,0.02),(period_bf,0)]
bf_theta = [(0,0),(14,0),(38,-360),(period_bf,-360)]   # flat → 360° backward flip
for f in range(period_bf + 1):
    th  = math.radians(_lerp_kf(bf_theta, f))
    arc = _lerp_kf(bf_arc, f)
    kf_rot("Hips", f, X, math.degrees(th))
    kf_loc("Hips", f, Y, arc + r_flip * (1 - math.cos(th)))
    kf_loc("Hips", f, Z, -r_flip * math.sin(th))
# Spine — coil in crouch, extend on launch
for f, v in [(0,0),(8,12),(14,-8),(38,-4),(42,10),(period_bf,0)]:
    kf_rot("Spine", f, X, v)

# Legs — tuck in fast and hold tight through the airborne flip so the
# body reads as a compact tumbling ball
for leg in ("LegL", "LegR"):
    for f, v in [(0,0),(8,20),(16,36),(34,36),(40,12),(44,20),(period_bf,0)]:
        kf_rot(leg, f, X, v)
# Arms — moderate tuck (the flip rotation itself is the big amplitude)
for ab, droop in [("ArmL", ARM_DROOP_L), ("ArmR", ARM_DROOP_R)]:
    for f, dv in [(0,0),(8,-20),(14,32),(22,28),(32,28),(38,14),(42,-5),(period_bf,0)]:
        kf_rot(ab, f, X, droop + dv)
# Head — tuck chin during the flip, look up on landing
for f, v in [(0,0),(8,15),(22,26),(32,22),(38,-10),(period_bf,0)]:
    kf_rot("Head", f, X, v)
# Tail — whips around with the flip
for f, v in [(0,0),(8,-26),(22,42),(32,42),(38,-20),(period_bf,0)]:
    kf_rot("Tail1", f, X, v)
for f, v in [(0,0),(8,-19),(22,32),(32,32),(38,-14),(period_bf,0)]:
    kf_rot("Tail2", f, X, v)
for f, v in [(0,0),(8,-12),(22,22),(32,22),(38,-9),(period_bf,0)]:
    kf_rot("Tail3", f, X, v)
# Ears — flatten during the spin, pop up on landing
for f, v in [(0,0),(14,-26),(32,-26),(40,16),(period_bf,0)]:
    kf_rot("EarL", f, X, v); kf_rot("EarR", f, X, v)

print(f"  backflip action authored")

# =====================================================================
# TWIRL — 48 frames one-shot: COMPOUND leap + airborne 360° spin
#   The leap (Hips Y translation) and the yaw spin (Hips Y rotation) run
#   simultaneously — two independent channels on the root bone. Crouch
#   anticipation, limbs fling out during the spin (tail flares
#   centrifugally), landing absorb.
# =====================================================================
print("\n[2k] Author TWIRL (48 frames)")
twirl = bind_action("twirl")
period_tw = 48

for pb in arm.pose.bones:
    pb.rotation_euler = (0, 0, 0)
    pb.location = (0, 0, 0)
    pb.scale = (1, 1, 1)

for f in [0, period_tw]:
    kf_loc("ArmL", f, Y, ARM_OUTWARD); kf_loc("ArmR", f, Y, ARM_OUTWARD)
    kf_loc("ArmL", f, Z, ARM_RAISE);   kf_loc("ArmR", f, Z, ARM_RAISE)

# Hips Y translation — high leap arc
for f, v in [(0,0),(8,-0.10),(14,0.08),(24,0.20),(34,0.08),(40,-0.06),(44,0.01),(period_tw,0)]:
    kf_loc("Hips", f, Y, v)   # modest hop (was a 0.52 flight that read as floating/tumbling)
# Hips Y rotation — full 360° yaw spin during the airborne phase
# (intermediate ~90° keys force the quaternion to take the long way)
for f, v in [(0,0),(8,-14),(14,40),(21,130),(28,230),(35,330),(40,360),(period_tw,360)]:
    kf_rot("Hips", f, Y, v)
# Hips X — forward lean in crouch, back on launch, forward on land
for f, v in [(0,0),(8,5),(14,-3),(40,5),(period_tw,0)]:
    kf_rot("Hips", f, X, v)   # gentle pitch (the old +12/+13 nose-dived on launch/land)
# Spine — coil then stretch
for f, v in [(0,0),(8,11),(14,-9),(24,-6),(40,12),(period_tw,0)]:
    kf_rot("Spine", f, X, v)
# Legs — moderate bend/tuck (rigid stub legs clip the body past ~20°)
for leg in ("LegL", "LegR"):
    for f, v in [(0,0),(8,14),(14,-4),(24,18),(34,-5),(40,15),(44,5),(period_tw,0)]:
        kf_rot(leg, f, X, v)
# Arms — moderate raise (rigid stub arms clip head/body past ~+20° absolute,
# i.e. droop+~40); body-level leap+spin carry the "big" amplitude instead
for ab, droop in [("ArmL", ARM_DROOP_L), ("ArmR", ARM_DROOP_R)]:
    for f, dv in [(0,0),(8,-18),(14,32),(24,38),(34,22),(40,10),(period_tw,0)]:
        kf_rot(ab, f, X, droop + dv)
# Head — dip in crouch, up while airborne
for f, v in [(0,0),(8,15),(14,-12),(24,-15),(40,15),(period_tw,0)]:
    kf_rot("Head", f, X, v)
# Tail — flares out centrifugally during the spin
for tb, amp in [("Tail1",34),("Tail2",28),("Tail3",23),("Tail4",18)]:
    for f, v in [(0,0),(10,-amp),(24,amp),(38,-amp),(period_tw,0)]:
        kf_rot(tb, f, Z, v)
# Ears — flatten during the spin, pop up on landing
for f, v in [(0,0),(14,-22),(34,-22),(40,14),(period_tw,0)]:
    kf_rot("EarL", f, X, v); kf_rot("EarR", f, X, v)

print(f"  twirl action authored")

# =====================================================================
# LOOKAROUND — 60 frames one-shot: curious head sweep (ambient "life" clip)
#   Pure head / ear / spine motion — no legs or arms past safe range.
#   The behaviour engine fires this autonomously while idling so the
#   sprite never feels frozen between scripted moves.
# =====================================================================
print("\n[2l] Author LOOKAROUND (60 frames)")
lookaround = bind_action("lookaround")
period_la = 60

for pb in arm.pose.bones:
    pb.rotation_euler = (0, 0, 0)
    pb.location = (0, 0, 0)
    pb.scale = (1, 1, 1)

for f in [0, period_la]:
    kf_rot("ArmL", f, X, ARM_DROOP_L); kf_rot("ArmR", f, X, ARM_DROOP_R)
    kf_loc("ArmL", f, Y, ARM_OUTWARD); kf_loc("ArmR", f, Y, ARM_OUTWARD)
    kf_loc("ArmL", f, Z, ARM_RAISE);   kf_loc("ArmR", f, Z, ARM_RAISE)

# Head yaw: settle-left, hold, sweep-right, hold, return (v5: 28→34° bigger sweep)
for f, v in [(0,0),(12,22),(24,22),(38,-22),(50,-22),(period_la,0)]:
    kf_rot("Head", f, Y, v)   # ±22 (the ±34 yaw + ±11 tilt compounded into a craned profile at the extreme)
# Curious head tilt toward each look direction
for f, v in [(0,0),(13,6),(24,6),(39,-6),(50,-6),(period_la,0)]:
    kf_rot("Head", f, Z, v)
# Small inquisitive nod as the head settles on each side
for f, v in [(0,0),(15,5),(24,1),(41,5),(50,1),(period_la,0)]:
    kf_rot("Head", f, X, v)
# Spine twists gently with the gaze
for f, v in [(0,0),(15,8),(24,8),(41,-8),(50,-8),(period_la,0)]:
    kf_rot("Spine", f, Y, v)
# Ears perk alert through the whole look
for f, v in [(0,0),(10,10),(50,10),(period_la,0)]:
    kf_rot("EarL", f, X, v); kf_rot("EarR", f, X, v)
# Tail slow curious sway, phased along the chain (v5: livelier)
for i, tb in enumerate(["Tail1","Tail2","Tail3","Tail4"]):
    sin_rot(tb, period_la, i*40, 18 - i*2, Z, samples=12)

print(f"  lookaround action authored")

# =====================================================================
# GROOM — 72 frames one-shot: washes its face with the right paw.
#   Raises ArmR to the face (proven-safe raise; wave uses X=55), the
#   head bows to meet it, 4 small synced lick bobs, then lowers.
# =====================================================================
print("\n[2m] Author GROOM (72 frames)")
groom = bind_action("groom")
period_gr = 72

for pb in arm.pose.bones:
    pb.rotation_euler = (0, 0, 0)
    pb.location = (0, 0, 0)
    pb.scale = (1, 1, 1)

for f in [0, period_gr]:
    kf_loc("ArmL", f, Y, ARM_OUTWARD); kf_loc("ArmR", f, Y, ARM_OUTWARD)
    kf_loc("ArmL", f, Z, ARM_RAISE);   kf_loc("ArmR", f, Z, ARM_RAISE)
    kf_rot("ArmL", f, X, ARM_DROOP_L)

# Right paw lifts to the face, holds, lowers
for f, v in [(0,ARM_DROOP_R),(14,50),(58,50),(period_gr,ARM_DROOP_R)]:
    kf_rot("ArmR", f, X, v)
# Right paw tucks inward toward the muzzle
for f, v in [(0,0),(14,-12),(58,-12),(period_gr,0)]:
    kf_rot("ArmR", f, Z, v)
# Head bows down HARD to meet the paw + cant toward it (was too shallow to read)
for f, v in [(0,0),(16,30),(58,30),(period_gr,0)]:
    kf_rot("Head", f, X, v)
for f, v in [(0,0),(16,-20),(58,-20),(period_gr,0)]:
    kf_rot("Head", f, Z, v)
# 4 lick bobs — bigger so each head-dip/paw-rise actually registers frame to frame
for i in range(20, 57):
    osc = 11.0 * math.sin(2 * math.pi * 4 * (i - 20) / 36.0)
    kf_rot("Head", i, X, 30 + osc)
    kf_rot("ArmR", i, X, 50 - osc)
# Spine curls forward over the grooming
for f, v in [(0,0),(16,7),(58,7),(period_gr,0)]:
    kf_rot("Spine", f, X, v)
# Left arm keeps a little life
for f, v in [(0,0),(22,-8),(50,6),(period_gr,0)]:
    kf_rot("ArmL", f, Z, v)
# Relaxed tail sway
for i, tb in enumerate(["Tail1","Tail2","Tail3"]):
    sin_rot(tb, period_gr, i*45, 10 - i*2, Z, samples=14)
# One ear flick mid-groom
for f, v in [(0,0),(30,0),(34,-10),(40,-2),(46,0),(period_gr,0)]:
    kf_rot("EarL", f, X, v)

print(f"  groom action authored")

# =====================================================================
# STRETCH — 64 frames one-shot: the classic cat arch.
#   anticipation crouch -> big spine arch + look up + arms reach back
#   -> hold with a tiny tremble -> release. Doubles as a yawn before
#   sleep and a wake-up stretch.
# =====================================================================
print("\n[2n] Author STRETCH (64 frames)")
stretch = bind_action("stretch")
period_st = 64

for pb in arm.pose.bones:
    pb.rotation_euler = (0, 0, 0)
    pb.location = (0, 0, 0)
    pb.scale = (1, 1, 1)

for f in [0, period_st]:
    kf_loc("ArmL", f, Y, ARM_OUTWARD); kf_loc("ArmR", f, Y, ARM_OUTWARD)
    kf_loc("ArmL", f, Z, ARM_RAISE);   kf_loc("ArmR", f, Z, ARM_RAISE)

# Hips: small dip in anticipation, lift into the arch
for f, v in [(0,0),(10,-0.04),(26,0.05),(40,0.05),(52,0),(period_st,0)]:
    kf_loc("Hips", f, Y, v)
# Spine arches back (negative X = lean/arch back) (v5: deeper arch -16→-20)
for f, v in [(0,0),(10,6),(24,-20),(40,-20),(52,4),(period_st,0)]:
    kf_rot("Spine", f, X, v)
# Head dips then looks up through the arch (v5: bigger)
for f, v in [(0,0),(10,10),(24,-24),(40,-22),(52,6),(period_st,0)]:
    kf_rot("Head", f, X, v)
# Arms reach back & up — bigger now the +40 cap is lifted (the reach IS the stretch)
for ab, droop in [("ArmL", ARM_DROOP_L), ("ArmR", ARM_DROOP_R)]:
    for f, dv in [(0,0),(10,-10),(24,58),(40,55),(52,-4),(period_st,0)]:
        kf_rot(ab, f, X, droop + dv)
# Tail lifts high (positive X = up) (v5: taller proud tail)
for f, v in [(0,0),(10,-10),(26,38),(40,36),(52,-6),(period_st,0)]:
    kf_rot("Tail1", f, X, v)
for f, v in [(0,0),(10,-8),(26,29),(40,27),(52,-4),(period_st,0)]:
    kf_rot("Tail2", f, X, v)
for f, v in [(0,0),(26,16),(40,14),(period_st,0)]:
    kf_rot("Tail3", f, X, v)
# Ears perk into the stretch
for f, v in [(0,0),(10,-6),(26,12),(40,12),(period_st,0)]:
    kf_rot("EarL", f, X, v); kf_rot("EarR", f, X, v)
# Tiny tremble while holding the stretch
for i in range(28, 39):
    kf_rot("Spine", i, Z, 2.0 * math.sin(2 * math.pi * 1.5 * (i - 28) / 10.0))

print(f"  stretch action authored")

# =====================================================================
# SLEEP — 96 frames LOOPING: dozing. Slumped, curled, slow breathing.
#   The behaviour engine swaps the base loop idle->sleep when the
#   sprite's energy runs low and nobody has interacted for a while.
# =====================================================================
print("\n[2o] Author SLEEP (96 frames, loop)")
sleep = bind_action("sleep")
period_sl = 96

for pb in arm.pose.bones:
    pb.rotation_euler = (0, 0, 0)
    pb.location = (0, 0, 0)
    pb.scale = (1, 1, 1)

for f in [0, period_sl]:
    kf_loc("ArmL", f, Y, ARM_OUTWARD); kf_loc("ArmR", f, Y, ARM_OUTWARD)
    kf_loc("ArmL", f, Z, ARM_RAISE);   kf_loc("ArmR", f, Z, ARM_RAISE)
    kf_rot("ArmL", f, X, ARM_DROOP_L); kf_rot("ArmR", f, X, ARM_DROOP_R)

# Collapse into a low, forward-folded ball. The old upright 24° head / 7° lean
# read as an AWAKE hover; tip the trunk well forward + droop the head onto the
# chest + sink the body so it sits low instead of standing as a vertical post.
for f in [0, period_sl]:
    kf_rot("Hips", f, X, 17)
# Sink low + slow READABLE breathing (Hips vertical → local Y = world up).
# Deeper sink (-0.18) + bigger breath swing (0.05) so the doze actually registers.
for i in range(period_sl + 1):
    t = i / period_sl
    kf_loc("Hips", i, Y, -0.18 + 0.05 * math.sin(2 * math.pi * t - math.pi / 2))
# Spine curled hard forward + breath swell (baseline 22 deg, was 9)
sin_rot("Spine", period_sl, -90, 3.0, X, samples=16, baseline=22)
# Head drooped onto the chest, breathing softly (baseline 46 deg, was 24)
sin_rot("Head", period_sl, -90, 2.5, X, samples=16, baseline=46)
for f in [0, period_sl]:
    kf_rot("Head", f, Z, 12)
# Ears fully relaxed down
for f in [0, period_sl]:
    kf_rot("EarL", f, X, -20); kf_rot("EarR", f, X, -19)
# Tail tucked tight + low around the body, almost no wag (calm sleep silhouette)
for f in [0, period_sl]:
    kf_rot("Tail1", f, X, -24); kf_rot("Tail2", f, X, -18)
sin_rot("Tail1", period_sl,   0, 2, Z, samples=14)
sin_rot("Tail2", period_sl,  40, 2, Z, samples=14)
sin_rot("Tail3", period_sl,  80, 2, Z, samples=14)

print(f"  sleep action authored")

# =====================================================================
# SNIFF — 48 frames one-shot: leans in and sniffs toward the viewer.
#   A short, curious "investigate" beat — fires when the engine wants a
#   brief reaction without committing to a full move.
# =====================================================================
print("\n[2p] Author SNIFF (48 frames)")
sniff = bind_action("sniff")
period_sn = 48

for pb in arm.pose.bones:
    pb.rotation_euler = (0, 0, 0)
    pb.location = (0, 0, 0)
    pb.scale = (1, 1, 1)

for f in [0, period_sn]:
    kf_loc("ArmL", f, Y, ARM_OUTWARD); kf_loc("ArmR", f, Y, ARM_OUTWARD)
    kf_loc("ArmL", f, Z, ARM_RAISE);   kf_loc("ArmR", f, Z, ARM_RAISE)
    kf_rot("ArmL", f, X, ARM_DROOP_L); kf_rot("ArmR", f, X, ARM_DROOP_R)

# Small GROUNDED lean — the old Spine+15/Hips+10 (plus Head+20) tipped the rigid
# body over and read as a side-roll/capsize at this camera. Keep it gentle.
for f, v in [(0,0),(12,7),(34,7),(period_sn,0)]:
    kf_rot("Spine", f, X, v)
for f, v in [(0,0),(12,4),(34,4),(period_sn,0)]:
    kf_rot("Hips", f, X, v)
# Head dips to a modest base, then 2-3 BIG SLOW sniffs you can actually count
for f, v in [(0,0),(12,13),(34,13),(period_sn,0)]:
    kf_rot("Head", f, X, v)
for i in range(12, 35):
    osc = 9.0 * math.sin(2 * math.pi * 2.5 * (i - 12) / 22.0)
    kf_rot("Head", i, X, 13 + osc)
# Ears prick forward
for f, v in [(0,0),(10,16),(36,16),(period_sn,0)]:
    kf_rot("EarL", f, X, v); kf_rot("EarR", f, X, v)
# Tail lifts in curiosity (smaller — +26 flared up and dominated the read)
for f, v in [(0,0),(12,13),(34,13),(period_sn,0)]:
    kf_rot("Tail1", f, X, v)
sin_rot("Tail1", period_sn,  0, 8, Z, samples=12)
sin_rot("Tail2", period_sn, 50, 6, Z, samples=12)

print(f"  sniff action authored")

# =====================================================================
# EAT — 44 frames one-shot: bows to the food, chews, looks up satisfied.
#   Triggered by the feeding interaction in the养成 (raising) system.
# =====================================================================
print("\n[2q] Author EAT (44 frames)")
eat = bind_action("eat")
period_ea = 44

for pb in arm.pose.bones:
    pb.rotation_euler = (0, 0, 0)
    pb.location = (0, 0, 0)
    pb.scale = (1, 1, 1)

for f in [0, period_ea]:
    kf_loc("ArmL", f, Y, ARM_OUTWARD); kf_loc("ArmR", f, Y, ARM_OUTWARD)
    kf_loc("ArmL", f, Z, ARM_RAISE);   kf_loc("ArmR", f, Z, ARM_RAISE)
    kf_rot("ArmL", f, X, ARM_DROOP_L); kf_rot("ArmR", f, X, ARM_DROOP_R)

# Small trunk lean only — the old Spine+14/Hips+8 stacked with Head+30 laid the
# whole body near-horizontal ("Superman nose-dive"). Crouch the HEAD, not the body.
for f, v in [(0,0),(10,5),(34,5),(40,2),(period_ea,0)]:
    kf_rot("Spine", f, X, v)
for f, v in [(0,0),(10,3),(34,3),(period_ea,0)]:
    kf_rot("Hips", f, X, v)
# Head bows toward floor-level food (modest), satisfied look-up at the end
for f, v in [(0,0),(10,22),(34,22),(40,-7),(period_ea,0)]:
    kf_rot("Head", f, X, v)
# Chewing — bigger, slower head bobs so the chews actually register as chews
for i in range(12, 34):
    osc = 13.0 * math.sin(2 * math.pi * 2.5 * (i - 12) / 22.0)
    kf_rot("Head", i, X, 22 + osc)
# Ears forward, focused on the food
for f, v in [(0,0),(10,9),(34,9),(period_ea,0)]:
    kf_rot("EarL", f, X, v); kf_rot("EarR", f, X, v)
# Content tail wag
sin_rot("Tail1", period_ea,  0, 12, Z, samples=14)
sin_rot("Tail2", period_ea, 45,  9, Z, samples=14)
sin_rot("Tail3", period_ea, 90,  6, Z, samples=14)

print(f"  eat action authored")

# =====================================================================
# NEW v5 CLIPS — more "busy cat" idle variety + readable signature moves.
# All authored within the rigid-rig conventions (translation + rotation
# only; glTF drops bone scale). Each uses anticipation → hold → settle and
# secondary tail/ear motion so it reads as alive, not a pose swap.
# Axis cheat-sheet (empirical): Head X=nod(+down) Y=yaw Z=tilt · Spine/Hips
# X=lean(+fwd/down) Y=yaw Z=side-roll · Hips locY=world-up · Arm X=droop/raise
# (baseline ARM_DROOP) Z=swing(ArmR− / ArmL+ = forward) · Leg X=swing(−fwd)
# · Tail X=lift(+up) Z=side-wag · Ear X=tilt(−back/flatten,+perk).
# =====================================================================

def _arm_baseline(act_end):
    """Pin arms to the chibi rest droop at both ends so they don't snap to
    a horizontal T-pose (rest = 0)."""
    for f in [0, act_end]:
        kf_rot("ArmL", f, X, ARM_DROOP_L); kf_rot("ArmR", f, X, ARM_DROOP_R)
        kf_loc("ArmL", f, Y, ARM_OUTWARD); kf_loc("ArmR", f, Y, ARM_OUTWARD)
        kf_loc("ArmL", f, Z, ARM_RAISE);   kf_loc("ArmR", f, Z, ARM_RAISE)

def _reset_pose():
    for pb in arm.pose.bones:
        pb.rotation_euler = (0, 0, 0); pb.location = (0, 0, 0); pb.scale = (1, 1, 1)

# ---- HEADTILT (44f) — the curious "?" head-cock, very readable ----
print("\n[2p] Author HEADTILT (44 frames)")
headtilt = bind_action("headtilt"); period_ht = 44
_reset_pose(); _arm_baseline(period_ht)
for f, v in [(0,0),(6,-5),(14,25),(32,25),(period_ht,0)]: kf_rot("Head", f, Z, v)  # pre-dip then big tilt
for f, v in [(0,0),(14,-7),(32,-7),(period_ht,0)]:        kf_rot("Head", f, X, v)  # look up a touch
for f, v in [(0,0),(14,-5),(32,-5),(period_ht,0)]:        kf_rot("Hips", f, Z, v)  # body counter-lean
for f, v in [(0,0),(14,11),(32,11),(period_ht,0)]:        kf_rot("EarL", f, X, v)  # near ear perks
for f, v in [(0,0),(14,4),(32,4),(period_ht,0)]:          kf_rot("EarR", f, X, v)
sin_rot("Tail1", period_ht, 0, 10, Z, samples=12)
sin_rot("Tail2", period_ht, 45, 8, Z, samples=12)
print("  headtilt authored")

# ---- SIT (50f) — settle onto haunches, tail curled, holds at the end ----
print("\n[2q] Author SIT (50 frames)")
sit = bind_action("sit"); period_si = 50
_reset_pose(); _arm_baseline(period_si)
for f, v in [(0,0),(6,0.02),(20,-0.17),(26,-0.20),(32,-0.18),(period_si,-0.18)]:
    kf_loc("Hips", f, Y, v)                                                        # DROP & hold — the sink IS the gesture (was a faint -0.13; deeper but capped to avoid foot-clip in-app)
for leg in ("LegL","LegR"):
    for f, v in [(0,0),(26,-28),(period_si,-26)]: kf_rot(leg, f, X, v)             # haunches fold forward
for leg, s in (("LegL",1),("LegR",-1)):
    for f, v in [(0,0),(26,22*s),(period_si,20*s)]: kf_rot(leg, f, Z, v)           # + splay OUTWARD so rigid stubs read as haunches-down, not dangling
for f, v in [(0,0),(26,-8),(period_si,-7)]:  kf_rot("Spine", f, X, v)              # lean torso back over the rear
for f, v in [(0,0),(14,7),(26,-3),(period_si,-2)]: kf_rot("Head", f, X, v)         # nod then up
for f, v in [(0,0),(22,-4),(30,3),(period_si,0)]:  kf_rot("Hips", f, X, v)          # rear settle bob
for tb, amp in [("Tail1",22),("Tail2",30),("Tail3",37),("Tail4",42)]:
    for f, v in [(0,0),(30,amp),(period_si,amp)]: kf_rot(tb, f, Z, v)               # tail curls round
print("  sit authored")

# ---- LICKPAW (56f) — raise paw, dip head, a few lick bobs, lower ----
print("\n[2r] Author LICKPAW (56 frames)")
lickpaw = bind_action("lickpaw"); period_lp = 56
_reset_pose(); _arm_baseline(period_lp)
for f, v in [(0,ARM_DROOP_R),(14,ARM_DROOP_R+75),(46,ARM_DROOP_R+75),(period_lp,ARM_DROOP_R)]:
    kf_rot("ArmR", f, X, v)                                                         # right paw up HIGH to the mouth (~+55° abs)
for f, v in [(0,0),(14,-18),(46,-18),(period_lp,0)]: kf_rot("ArmR", f, Z, v)        # paw to centreline
_hk = [(0,0),(14,16)]
for _i, _f in enumerate(range(18, 45, 6)): _hk.append((_f, 12 if _i % 2 == 0 else 20))
_hk += [(50,4),(period_lp,0)]
for f, v in _hk: kf_rot("Head", f, X, v)                                            # dip + lick bobs
for f, v in [(0,0),(14,5),(46,5),(period_lp,0)]: kf_rot("Hips", f, Z, v)            # lean toward paw
sin_rot("Tail1", period_lp, 0, 8, Z, samples=14)
sin_rot("Tail2", period_lp, 50, 6, Z, samples=14)
print("  lickpaw authored")

# ---- POUNCE (42f) — stalk-crouch + the iconic butt-wiggle, spring, land ----
print("\n[2s] Author POUNCE (42 frames)")
pounce = bind_action("pounce"); period_po = 42
_reset_pose(); _arm_baseline(period_po)
for f, v in [(0,0),(8,-0.16),(18,-0.17),(24,0.12),(28,0.0),(period_po,0)]:
    kf_loc("Hips", f, Y, v)                                                          # crouch LOW & HOLD → brief fast spring → LAND at 0 (old -0.10 crouch was too shallow to spring from)
for f, v in [(0,0),(8,14),(18,14),(24,20),(34,-4),(period_po,0)]: kf_rot("Hips", f, X, v)  # coil low → forward thrust
for f, v in [(8,0),(11,13),(14,-13),(17,8),(18,0)]: kf_rot("Hips", f, Z, v)         # ★ BIG butt wiggle (was ±5, invisible)
for leg in ("LegL","LegR"):
    for f, v in [(0,0),(8,22),(18,24),(24,-16),(30,4),(period_po,0)]: kf_rot(leg, f, X, v)  # tuck hard on the spring, plant on the land
for f, v in [(0,0),(8,8),(18,10),(24,4),(34,-6),(period_po,0)]: kf_rot("Head", f, X, v)  # locked on target
for f, v in [(0,0),(8,12),(18,12),(24,-14),(period_po,0)]:
    kf_rot("EarL", f, X, v); kf_rot("EarR", f, X, v)                                 # forward then pinned
for f, v in [(0,0),(8,-18),(18,-18),(24,26),(30,16),(period_po,0)]: kf_rot("Tail1", f, X, v)
for f, v in [(0,0),(8,-14),(18,-14),(24,20),(30,12),(period_po,0)]: kf_rot("Tail2", f, X, v)
print("  pounce authored")

# ---- PLAYBOW (52f) — front-down "let's play" bow, hold, pop up ----
print("\n[2t] Author PLAYBOW (52 frames)")
playbow = bind_action("playbow"); period_pb = 52
_reset_pose(); _arm_baseline(period_pb)
for f, v in [(0,0),(8,-4),(18,-20),(38,-20),(44,6),(period_pb,0)]:  kf_rot("Hips", f, X, v)   # rear tips up HARD (fore/aft contrast for the bow)
for f, v in [(0,0),(8,-5),(18,32),(38,32),(44,-6),(period_pb,0)]:   kf_rot("Spine", f, X, v)  # front dives down
for f, v in [(0,0),(18,24),(28,14),(38,22),(44,-8),(period_pb,0)]:  kf_rot("Head", f, X, v)   # head to floor, peek up
for f, v in [(0,0),(18,-0.03),(44,0.06),(48,-0.02),(period_pb,0)]:  kf_loc("Hips", f, Y, v)   # little end hop
for f, v in [(0,ARM_DROOP_L),(18,ARM_DROOP_L+10),(38,ARM_DROOP_L+10),(period_pb,ARM_DROOP_L)]: kf_rot("ArmL", f, X, v)
for f, v in [(0,ARM_DROOP_R),(18,ARM_DROOP_R+10),(38,ARM_DROOP_R+10),(period_pb,ARM_DROOP_R)]: kf_rot("ArmR", f, X, v)
for f, v in [(0,0),(18,18),(38,18),(period_pb,0)]:  kf_rot("ArmL", f, Z, v)         # paws reach forward
for f, v in [(0,0),(18,-18),(38,-18),(period_pb,0)]: kf_rot("ArmR", f, Z, v)
for f, v in [(0,0),(18,34),(38,34),(44,10),(period_pb,0)]: kf_rot("Tail1", f, X, v) # tail held high
for f, v in [(0,0),(18,28),(38,28),(44,8),(period_pb,0)]:  kf_rot("Tail2", f, X, v)
for tb, amp, ph in [("Tail1",16,0),("Tail2",13,40),("Tail3",10,80),("Tail4",8,120)]:
    sin_rot(tb, period_pb, ph, amp, Z, samples=16)                                  # excited wag
for f, v in [(0,0),(18,12),(38,12),(period_pb,0)]: kf_rot("EarL", f, X, v); kf_rot("EarR", f, X, v)
print("  playbow authored")

# =====================================================================
# v6 GALGAME ADDITIONS — 5 new clips, all inside the proven-safe envelope
# (head/ear/spine/tail/hips dominant; arm lifts ≤+50 X like lickpaw/playbow).
# They pair with the v6 faces + interactions: nod=affirm, shy=blush moment,
# ponder=chat-thinking, adore=love/heart, headpat=being-petted.
# =====================================================================

# ---- NOD (30f) — two clear yes-nods; affirmation ----
print("\n[2u] Author NOD (30 frames)")
nod = bind_action("nod"); period_nd = 30
_reset_pose(); _arm_baseline(period_nd)
for f, v in [(0,0),(7,18),(13,-4),(20,16),(26,-2),(period_nd,0)]: kf_rot("Head", f, X, v)  # nod down ×2 (X+ = down)
for f, v in [(0,0),(7,5),(20,5),(period_nd,0)]: kf_rot("EarL", f, X, v); kf_rot("EarR", f, X, v)
for f, v in [(0,0),(10,0.02),(period_nd,0)]: kf_loc("Hips", f, Y, v)
sin_rot("Tail1", period_nd, 0, 8, Z, samples=8)
print("  nod authored")

# ---- SHY (46f) — head dips & turns away, ears flatten, bashful tilt + arm hug ----
print("\n[2v] Author SHY (46 frames)")
shy = bind_action("shy"); period_sh = 46
_reset_pose(); _arm_baseline(period_sh)
for f, v in [(0,0),(16,22),(34,18),(period_sh,0)]: kf_rot("Head", f, X, v)   # head dips down (v7: bigger)
for f, v in [(0,0),(16,-22),(34,-20),(period_sh,0)]: kf_rot("Head", f, Y, v) # turn away coyly but keep the blush face readable (was -34, hid the face)
for f, v in [(0,0),(16,16),(34,14),(period_sh,0)]:  kf_rot("Head", f, Z, v)  # bashful tilt
for f, v in [(0,0),(16,-22),(40,-20),(period_sh,-8)]: kf_rot("EarL", f, X, v); kf_rot("EarR", f, X, v)  # ears stay flattened LATE so the rest pose still reads timid (not perked/neutral)
for f, v in [(0,0),(16,-14),(34,-12),(period_sh,0)]: kf_rot("Spine", f, X, v) # body curls/shrinks in
for f, v in [(0,0),(16,12),(34,11),(period_sh,0)]:  kf_rot("Spine", f, Z, v)  # whole body leans away
for f, v in [(0,0),(16,14),(34,12),(period_sh,0)]:  kf_rot("Hips", f, Z, v)   # hips lean away too
for f, v in [(0,0),(16,9),(34,9),(period_sh,0)]:    kf_rot("ArmL", f, Z, v)  # arms hug inward (ArmL +Z = forward)
for f, v in [(0,0),(16,-9),(34,-9),(period_sh,0)]:  kf_rot("ArmR", f, Z, v)  # (ArmR -Z = forward)
for f, v in [(0,0),(16,-18),(period_sh,0)]: kf_rot("Tail1", f, Z, v)         # tail tucks to one side
print("  shy authored")

# ---- PONDER (48f) — looks up & aside, paw to chin, ear flick; the think pose ----
print("\n[2w] Author PONDER (48 frames)")
ponder = bind_action("ponder"); period_pn = 48
_reset_pose(); _arm_baseline(period_pn)
for f, v in [(0,0),(14,-12),(36,-11),(period_pn,0)]: kf_rot("Head", f, X, v) # mild look-up (don't crane away from the raised paw)
for f, v in [(0,0),(14,18),(36,18),(period_pn,0)]:   kf_rot("Head", f, Z, v) # tilt
for f, v in [(0,0),(14,-14),(36,-14),(period_pn,0)]: kf_rot("Head", f, Y, v) # glance aside
for f, v in [(0,0),(14,-10),(36,-9),(period_pn,0)]:  kf_rot("Spine", f, X, v) # lean back, thinking
for f, v in [(0,0),(14,9),(36,9),(period_pn,0)]:     kf_rot("Spine", f, Z, v) # weight onto one side
for f, v in [(0,0),(14,8),(36,8),(period_pn,0)]:     kf_rot("Hips", f, Z, v)  # hips shift with it
for f, v in [(0,0),(14,16),(24,8),(36,16),(period_pn,0)]: kf_rot("EarL", f, X, v)  # near ear flicks
for f, v in [(0,0),(14,7),(36,7),(period_pn,0)]:     kf_rot("EarR", f, X, v)
for f, v in [(0,ARM_DROOP_R),(14,ARM_DROOP_R+62),(36,ARM_DROOP_R+62),(period_pn,ARM_DROOP_R)]:
    kf_rot("ArmR", f, X, v)                                                  # paw raised UP to chin height (~+42° abs, now unlocked)
for f, v in [(0,0),(14,-20),(36,-20),(period_pn,0)]: kf_rot("ArmR", f, Z, v) # paw swung in to the chin centreline
sin_rot("Tail1", period_pn, 0, 7, Z, samples=12)
print("  ponder authored")

# ---- ADORE (40f) — smitten little double-bounce, head sway, fast tail, ears up ----
print("\n[2x] Author ADORE (40 frames)")
adore = bind_action("adore"); period_ad = 40
_reset_pose(); _arm_baseline(period_ad)
# Adoration = a single HELD soft-gaze pose, grounded — NOT a double bounce.
# (The old two hops floated; the whole-body Z wobble read as 'excited happy'.)
for f in [0, period_ad]: kf_loc("Hips", f, Y, 0)                                         # no hops — stay planted
for f, v in [(0,0),(12,-14),(30,-14),(period_ad,0)]: kf_rot("Head", f, X, v)             # one slow UP-tilted gaze, held (look up adoringly)
for f, v in [(0,0),(12,12),(30,12),(period_ad,0)]:   kf_rot("Head", f, Z, v)             # ONE soft head tilt, held (not a sway)
for f, v in [(0,0),(12,-6),(30,-6),(period_ad,0)]:   kf_rot("Spine", f, X, v)            # lean gently toward camera (drop the Z wiggle entirely)
for f, v in [(0,0),(12,12),(30,12),(period_ad,0)]: kf_rot("EarL", f, X, v); kf_rot("EarR", f, X, v)  # ears perk gently
for tb, amp, ph in [("Tail1",13,0),("Tail2",11,45),("Tail3",9,90),("Tail4",7,135)]:
    sin_rot(tb, period_ad, ph, amp, Z, samples=14)                                       # CALM slow wag (half the old excited amp)
# Arms = the gesture: both up to ~+40° abs and swung INWARD so the stub paws
# clasp at the chest (heart-clutch) and HELD — softer than happy/adore's old
# +55° which read 太夸张.
for f, v in [(0,ARM_DROOP_L),(12,ARM_DROOP_L+60),(30,ARM_DROOP_L+60),(period_ad,ARM_DROOP_L)]: kf_rot("ArmL", f, X, v)
for f, v in [(0,ARM_DROOP_R),(12,ARM_DROOP_R+60),(30,ARM_DROOP_R+60),(period_ad,ARM_DROOP_R)]: kf_rot("ArmR", f, X, v)
for f, v in [(0,0),(12,26),(30,26),(period_ad,0)]:  kf_rot("ArmL", f, Z, v)              # ArmL+ = swing inward/forward
for f, v in [(0,0),(12,-26),(30,-26),(period_ad,0)]: kf_rot("ArmR", f, Z, v)             # ArmR- = swing inward/forward
print("  adore authored")

# ---- HEADPAT (44f) — head presses down under the hand, ears flatten happily ----
print("\n[2y] Author HEADPAT (44 frames)")
headpat = bind_action("headpat"); period_hp = 44
_reset_pose(); _arm_baseline(period_hp)
_pk = [(0,0)]
for _i, _f in enumerate(range(8, 38, 8)): _pk.append((_f, 24 if _i % 2 == 0 else 12))
_pk += [(period_hp,0)]
for f, v in _pk: kf_rot("Head", f, X, v)                                     # press down repeatedly (v7: bigger)
for f, v in [(0,0),(8,-32),(36,-30),(period_hp,0)]: kf_rot("EarL", f, X, v); kf_rot("EarR", f, X, v)  # ears flatten HARD + held — THE 'being petted' signal
for f, v in [(0,0),(10,9),(34,9),(period_hp,0)]: kf_rot("Head", f, Z, v)      # head tilts INTO the unseen hand
for f, v in [(0,0),(8,-0.05),(36,-0.05),(period_hp,0)]: kf_loc("Hips", f, Y, v)  # sink down under the hand
for f, v in [(0,0),(8,-12),(36,-12),(period_hp,0)]:  kf_rot("Spine", f, X, v)    # whole upper body bows under the hand
for f, v in [(0,0),(10,7),(30,7),(period_hp,0)]:     kf_rot("Hips", f, X, v)     # rear settles down
sin_rot("Tail1", period_hp, 0, 12, Z, samples=12)                            # happy slow wag
sin_rot("Tail2", period_hp, 45, 9, Z, samples=12)
print("  headpat authored")

# =====================================================================
# Push all actions to NLA tracks
# =====================================================================
print("\n[3] Push 22 actions to NLA")
ad = arm.animation_data
for tr in list(ad.nla_tracks):
    ad.nla_tracks.remove(tr)

for action_name, action_obj, action_period in [
    ("idle", idle, period), ("walk", walk, period_walk), ("run", run, period_run),
    ("attack", attack, period_attack), ("hurt", hurt, period_hurt),
    ("wave", wave, period_wave), ("happy", happy, period_happy),
    ("jump", jump, period_jump), ("spin", spin, period_spin),
    ("backflip", backflip, period_bf), ("twirl", twirl, period_tw),
    ("lookaround", lookaround, period_la), ("groom", groom, period_gr),
    ("stretch", stretch, period_st), ("sleep", sleep, period_sl),
    ("sniff", sniff, period_sn), ("eat", eat, period_ea),
    # v5 additions
    ("headtilt", headtilt, period_ht), ("sit", sit, period_si),
    ("lickpaw", lickpaw, period_lp), ("pounce", pounce, period_po),
    ("playbow", playbow, period_pb),
    # v6 galgame additions
    ("nod", nod, period_nd), ("shy", shy, period_sh),
    ("ponder", ponder, period_pn), ("adore", adore, period_ad),
    ("headpat", headpat, period_hp),
]:
    tr = ad.nla_tracks.new()
    tr.name = action_name
    strip = tr.strips.new(action_obj.name, 1, action_obj)
    strip.action_frame_start = 0
    strip.action_frame_end = action_period
    tr.mute = False

ad.action = None
print(f"  Pushed {len(ad.nla_tracks)} tracks to NLA")

# =====================================================================
# Render mid-frame verification (frame 30 = mid breath)
# =====================================================================
print("\n[4] Render idle mid-frame (frame 30)")

# Reuse the v2 render setup (3/4 view, sun, EEVEE)
scene = bpy.context.scene
try:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
except Exception:
    scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 600
scene.render.resolution_y = 800

# Set up camera + light (the v2_skinned.blend may not have them)
for o in list(bpy.data.objects):
    if o.type in ('CAMERA', 'LIGHT'):
        bpy.data.objects.remove(o, do_unlink=True)

# Compute scene bbox
all_pts = []
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
for m in meshes:
    all_pts.extend(m.matrix_world @ v.co for v in m.data.vertices)
xs=[p.x for p in all_pts]; ys=[p.y for p in all_pts]; zs=[p.z for p in all_pts]
target = Vector((sum(xs)/len(xs), sum(ys)/len(ys), sum(zs)/len(zs)))
zr = max(zs) - min(zs)

cam_data = bpy.data.cameras.new("Cam"); cam_data.type = "ORTHO"
cam_data.ortho_scale = zr * 1.4
cam_obj = bpy.data.objects.new("Cam", cam_data)
bpy.context.collection.objects.link(cam_obj)
cam_obj.location = target + Vector((zr*1.6, -zr*2.0, zr*0.3))
d = target - Vector(cam_obj.location)
cam_obj.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam_obj

light = bpy.data.lights.new("Sun", type="SUN"); light.energy = 3.0
lo = bpy.data.objects.new("Sun", light); bpy.context.collection.objects.link(lo)
lo.location = (3, -3, 4); lo.rotation_euler = (math.radians(50), math.radians(20), math.radians(-30))

scene.world = scene.world or bpy.data.worlds.new("W")
scene.world.use_nodes = True
bg = scene.world.node_tree.nodes.get("Background")
if bg: bg.inputs[0].default_value = (0.85, 0.95, 0.78, 1.0)

ad.action = None  # NLA is the source of truth — mute all but the target track per render
def isolate_track(name):
    for tr in ad.nla_tracks:
        tr.mute = (tr.name != name)

# Idle verification (frame 25 = mid-blink)
isolate_track("idle")
for fr in [0, 15, 25, 45]:
    scene.frame_set(fr)
    bpy.context.view_layer.update()
    out_fr = os.path.join(VERIFY_DIR, f"v2_idle_f{fr:02d}.png")
    scene.render.filepath = out_fr
    bpy.ops.render.render(write_still=True)
    print(f"  Rendered idle frame {fr}: {out_fr}")

# Walk verification (4 phases of the walk cycle)
isolate_track("walk")
for fr in [0, 7, 15, 22]:
    scene.frame_set(fr)
    bpy.context.view_layer.update()
    out_fr = os.path.join(VERIFY_DIR, f"v2_walk_f{fr:02d}.png")
    scene.render.filepath = out_fr
    bpy.ops.render.render(write_still=True)
    print(f"  Rendered walk frame {fr}: {out_fr}")

# Run verification (4 phases of the run cycle)
isolate_track("run")
for fr in [0, 4, 9, 13]:
    scene.frame_set(fr)
    bpy.context.view_layer.update()
    out_fr = os.path.join(VERIFY_DIR, f"v2_run_f{fr:02d}.png")
    scene.render.filepath = out_fr
    bpy.ops.render.render(write_still=True)
    print(f"  Rendered run frame {fr}: {out_fr}")

# Attack verification (windup / strike / hold / recover)
isolate_track("attack")
for fr in [8, 16, 22, 30]:
    scene.frame_set(fr)
    bpy.context.view_layer.update()
    out_fr = os.path.join(VERIFY_DIR, f"v2_attack_f{fr:02d}.png")
    scene.render.filepath = out_fr
    bpy.ops.render.render(write_still=True)
    print(f"  Rendered attack frame {fr}: {out_fr}")

# Hurt verification (impact / max recoil / recover)
isolate_track("hurt")
for fr in [3, 10, 18, 22]:
    scene.frame_set(fr)
    bpy.context.view_layer.update()
    out_fr = os.path.join(VERIFY_DIR, f"v2_hurt_f{fr:02d}.png")
    scene.render.filepath = out_fr
    bpy.ops.render.render(write_still=True)
    print(f"  Rendered hurt frame {fr}: {out_fr}")

# Wave verification (crouch / airborne-turn / mid-wave / land)
isolate_track("wave")
for fr in [10, 24, 33, 46]:
    scene.frame_set(fr)
    bpy.context.view_layer.update()
    out_fr = os.path.join(VERIFY_DIR, f"v2_wave_f{fr:02d}.png")
    scene.render.filepath = out_fr
    bpy.ops.render.render(write_still=True)
    print(f"  Rendered wave frame {fr}: {out_fr}")

# Happy verification
isolate_track("happy")
for fr in [6, 18, 30, 42]:
    scene.frame_set(fr)
    bpy.context.view_layer.update()
    out_fr = os.path.join(VERIFY_DIR, f"v2_happy_f{fr:02d}.png")
    scene.render.filepath = out_fr
    bpy.ops.render.render(write_still=True)
    print(f"  Rendered happy frame {fr}: {out_fr}")

# Jump verification (crouch / launch / airborne / land)
isolate_track("jump")
for fr in [8, 14, 19, 30]:
    scene.frame_set(fr)
    bpy.context.view_layer.update()
    out_fr = os.path.join(VERIFY_DIR, f"v2_jump_f{fr:02d}.png")
    scene.render.filepath = out_fr
    bpy.ops.render.render(write_still=True)
    print(f"  Rendered jump frame {fr}: {out_fr}")

# Spin verification
isolate_track("spin")
for fr in [6, 14, 22, 30]:
    scene.frame_set(fr)
    bpy.context.view_layer.update()
    out_fr = os.path.join(VERIFY_DIR, f"v2_spin_f{fr:02d}.png")
    scene.render.filepath = out_fr
    bpy.ops.render.render(write_still=True)
    print(f"  Rendered spin frame {fr}: {out_fr}")

# Backflip verification (crouch / flipping / upside-down / land)
isolate_track("backflip")
for fr in [8, 20, 26, 40]:
    scene.frame_set(fr)
    bpy.context.view_layer.update()
    out_fr = os.path.join(VERIFY_DIR, f"v2_backflip_f{fr:02d}.png")
    scene.render.filepath = out_fr
    bpy.ops.render.render(write_still=True)
    print(f"  Rendered backflip frame {fr}: {out_fr}")

# Twirl verification (crouch / launch / airborne-spin / land)
isolate_track("twirl")
for fr in [8, 18, 28, 42]:
    scene.frame_set(fr)
    bpy.context.view_layer.update()
    out_fr = os.path.join(VERIFY_DIR, f"v2_twirl_f{fr:02d}.png")
    scene.render.filepath = out_fr
    bpy.ops.render.render(write_still=True)
    print(f"  Rendered twirl frame {fr}: {out_fr}")

# Lookaround verification
isolate_track("lookaround")
for fr in [12, 24, 44, 56]:
    scene.frame_set(fr)
    bpy.context.view_layer.update()
    out_fr = os.path.join(VERIFY_DIR, f"v2_lookaround_f{fr:02d}.png")
    scene.render.filepath = out_fr
    bpy.ops.render.render(write_still=True)
    print(f"  Rendered lookaround frame {fr}: {out_fr}")

# Groom verification
isolate_track("groom")
for fr in [16, 30, 44, 64]:
    scene.frame_set(fr)
    bpy.context.view_layer.update()
    out_fr = os.path.join(VERIFY_DIR, f"v2_groom_f{fr:02d}.png")
    scene.render.filepath = out_fr
    bpy.ops.render.render(write_still=True)
    print(f"  Rendered groom frame {fr}: {out_fr}")

# Stretch verification
isolate_track("stretch")
for fr in [10, 24, 40, 56]:
    scene.frame_set(fr)
    bpy.context.view_layer.update()
    out_fr = os.path.join(VERIFY_DIR, f"v2_stretch_f{fr:02d}.png")
    scene.render.filepath = out_fr
    bpy.ops.render.render(write_still=True)
    print(f"  Rendered stretch frame {fr}: {out_fr}")

# Sleep verification
isolate_track("sleep")
for fr in [0, 24, 48, 72]:
    scene.frame_set(fr)
    bpy.context.view_layer.update()
    out_fr = os.path.join(VERIFY_DIR, f"v2_sleep_f{fr:02d}.png")
    scene.render.filepath = out_fr
    bpy.ops.render.render(write_still=True)
    print(f"  Rendered sleep frame {fr}: {out_fr}")

# Sniff verification
isolate_track("sniff")
for fr in [12, 22, 30, 44]:
    scene.frame_set(fr)
    bpy.context.view_layer.update()
    out_fr = os.path.join(VERIFY_DIR, f"v2_sniff_f{fr:02d}.png")
    scene.render.filepath = out_fr
    bpy.ops.render.render(write_still=True)
    print(f"  Rendered sniff frame {fr}: {out_fr}")

# Eat verification
isolate_track("eat")
for fr in [10, 22, 33, 41]:
    scene.frame_set(fr)
    bpy.context.view_layer.update()
    out_fr = os.path.join(VERIFY_DIR, f"v2_eat_f{fr:02d}.png")
    scene.render.filepath = out_fr
    bpy.ops.render.render(write_still=True)
    print(f"  Rendered eat frame {fr}: {out_fr}")

# v5 new-clip verification
for _name, _frames in [
    ("headtilt", [6, 14, 32, 42]), ("sit", [10, 26, 40, 49]),
    ("lickpaw", [14, 24, 36, 50]), ("pounce", [8, 18, 24, 36]),
    ("playbow", [8, 18, 30, 46]),
    # v6 galgame additions
    ("nod", [7, 13, 20, 26]), ("shy", [16, 25, 34, 44]),
    ("ponder", [14, 24, 36, 46]), ("adore", [10, 20, 30, 38]),
    ("headpat", [8, 16, 24, 36]),
]:
    isolate_track(_name)
    for fr in _frames:
        scene.frame_set(fr)
        bpy.context.view_layer.update()
        out_fr = os.path.join(VERIFY_DIR, f"v2_{_name}_f{fr:02d}.png")
        scene.render.filepath = out_fr
        bpy.ops.render.render(write_still=True)
        print(f"  Rendered {_name} frame {fr}: {out_fr}")

# Unmute all tracks before save + export
for tr in ad.nla_tracks:
    tr.mute = False

# =====================================================================
# Save .blend
# =====================================================================
scene.frame_set(1)
print(f"\n[5] Save → {BLEND_OUT}")
bpy.ops.wm.save_as_mainfile(filepath=BLEND_OUT)

# =====================================================================
# Export GLB — scaled to a palm-sized creature + compressed for the web
# =====================================================================
GLB_OUT = r"E:\05_claude\CGmiaomiao\character_v2.glb"
print(f"\n[6] Export GLB → {GLB_OUT}")

# ---- Scale the whole rig down so the GLB is ~0.14 m tall. model-viewer
#      treats glTF units as metres, so for AR the sprite must enter the
#      room as a palm-sized creature, not a 1.9 m giant. A root Empty
#      carries the scale, leaving the skinned armature itself at unit
#      scale (clean inverse-bind matrices, no skinning risk). ----
TARGET_HEIGHT_M = 0.14
_hz = [(_m.matrix_world @ _v.co).z for _m in bpy.data.objects
       if _m.type == 'MESH' for _v in _m.data.vertices]
_glb_scale = TARGET_HEIGHT_M / (max(_hz) - min(_hz))
print(f"  rig height {max(_hz)-min(_hz):.3f} → scale x{_glb_scale:.4f} → {TARGET_HEIGHT_M} m")
root_empty = bpy.data.objects.new("MiaoRoot", None)
bpy.context.collection.objects.link(root_empty)
root_empty.scale = (_glb_scale, _glb_scale, _glb_scale)
arm.parent = root_empty

# ---- Slim the textures: 2K is overkill for a 14 cm AR creature on a
#      phone. 1K keeps it crisp at a quarter of the pixels. ----
for _img in bpy.data.images:
    if max(_img.size) > 1024:
        try:
            _img.scale(1024, 1024)
            print(f"  resized texture '{_img.name}' -> 1024^2")
        except Exception as _e:
            print(f"  [warn] could not resize {_img.name}: {_e}")

# Select root + armature + all meshes (gltf exporter exports SELECTION)
for o in bpy.data.objects:
    try: o.select_set(False)
    except: pass
root_empty.select_set(True)
arm.select_set(True)
bpy.context.view_layer.objects.active = arm
for m in bpy.data.objects:
    if m.type == 'MESH':
        m.select_set(True)

# Ensure NLA tracks are unmuted so the GLB picks up every clip
for tr in arm.animation_data.nla_tracks:
    tr.mute = False

_export_kwargs = dict(
    filepath=GLB_OUT,
    export_format="GLB",
    use_selection=True,
    export_animations=True,
    export_animation_mode="ACTIONS",
    export_yup=True,
    export_skins=True,
)
# Draco mesh compression for payload savings. NB: do NOT use WebP textures —
# Blender writes EXT_texture_webp into extensionsREQUIRED, and Google Scene
# Viewer (Android native AR) does not implement it, so a WebP GLB is REFUSED
# whole in AR (the in-page WebGL viewer decodes WebP fine, which is why it
# only failed on the AR handoff — "tapped AR, saw nothing"). AUTO keeps the
# source formats (jpg basecolor stays jpg); Scene Viewer + iOS USDZ-gen both
# accept that. Draco is supported by Scene Viewer, so it stays.
try:
    bpy.ops.export_scene.gltf(
        **_export_kwargs,
        export_image_format="AUTO",
        export_draco_mesh_compression_enable=True,
        export_draco_mesh_compression_level=6,
    )
    print(f"  GLB exported (AUTO textures, AR-safe + Draco mesh compression)")
except (TypeError, RuntimeError) as _e:
    print(f"  [warn] compression unsupported ({_e}); plain export")
    bpy.ops.export_scene.gltf(**_export_kwargs)
    print(f"  GLB exported (uncompressed)")

import os as _os_glb
print(f"  GLB size: {_os_glb.path.getsize(GLB_OUT)/1024/1024:.2f} MB")

# =====================================================================
# Copy to ar/
# =====================================================================
import shutil
AR_GLB = r"E:\05_claude\CGmiaomiao\ar\public\character_v2.glb"  # Vite serves public/ at site root
shutil.copyfile(GLB_OUT, AR_GLB)
print(f"\n[7] Copied to {AR_GLB}")

print("\n[step 4a complete: idle authored + exported + copied to ar/]")
