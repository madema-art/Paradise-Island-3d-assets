"""Verify the numpy kinematics against Blender's pose evaluation (joint head/tail positions)."""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy  # noqa: E402

import hdesign  # noqa: E402
import rig_build  # noqa: E402
from pose_lib import *  # noqa: E402,F401,F403
from pose_lib import RIG  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
D_ = hdesign.build()
rig = rig_build.build_armature(D_)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode="POSE")

p = Pose()
p.root_pos = np.array([0.3, -0.2, 0.0])
p.root_yaw = 35.0
p.pelvis_off = np.array([0.0, 0.02, -0.1])
spine(p, 25, 8, -20)
head(p, -12, 5, 30)
add_fk(p, "jaw", 18)
p.tr["lip_corner_L"] = np.array([0.004, 0.0, 0.006])
grip(p, "L", "fist")
grip(p, "R", "open", spread=8)
arm_ik(p, "L", RIG.wrist_rest["L"] + np.array([-0.15, -0.35, 0.28]), hand_dirs=((0, -1, 0), (0, 0, 1)))
arm_ik(p, "R", RIG.wrist_rest["R"] + np.array([0.1, -0.2, 0.2]), hand_rel=(20, 10, 30), twist=15)
foot_at(p, "L", (0.10, -0.25), yaw=10, pitch=15, pivot="ball", lift=0.03)
foot_at(p, "R", (-0.10, 0.02), yaw=-5, pivot="flat")
p.toes["L"] = -20
sol = solve(p)
q = sol.quats()
sk = RIG.sk
for i, n in enumerate(sk.names):
    pb = rig.pose.bones[n]
    pb.rotation_quaternion = q[i]
    pb.location = sol.T[i]
bpy.context.view_layer.update()
worst = 0.0
worst_name = ""
for i, n in enumerate(sk.names):
    pb = rig.pose.bones[n]
    h = np.array(pb.head)
    t = np.array(pb.tail)
    e = max(np.linalg.norm(h - sol.Hw[i]), np.linalg.norm(t - sol.Tw[i]))
    if e > worst:
        worst, worst_name = e, n
print(f"[test] worst joint error {worst * 1000:.4f} mm at {worst_name}; IK report {p.report}")
