"""
Render key poses of the manta from the saved .blend, for review (not a shipped asset).

  /opt/bpy-venv/bin/python tools/manta/render_poses.py -- --blend assets/manta/Manta.blend --out assets/manta/previews

Cycles CPU, low samples, no denoise (the headless build has no denoiser). One PNG per pose, named clip_time.png.
"""
import argparse
import math
import os
import sys

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

FPS = 30
POSES = [
    ("glide_cruise", 0.0), ("glide_cruise", 1.2),
    ("flap_power", 0.28), ("flap_power", 0.82),
    ("feed_open", 2.5),
    ("curious_approach", 1.0),
    ("turn_left", 1.2),
    ("startle_burst", 0.25),
    ("breach_rise", 1.5), ("breach_rise", 2.9),
    ("breach_fall", 0.8),
]


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--blend", default="assets/manta/Manta.blend")
    p.add_argument("--out", default="assets/manta/previews")
    return p.parse_args(argv)


def setup_camera(scene, target, loc, name):
    cam_data = bpy.data.cameras.new(name)
    cam_data.lens = 35
    cam = bpy.data.objects.new(name, cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = loc
    direction = Vector(target) - Vector(loc)
    cam.rotation_mode = "QUATERNION"
    cam.rotation_quaternion = direction.to_track_quat("-Z", "Y")
    scene.camera = cam
    return cam


def main():
    a = args()
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(a.blend))
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = False
    scene.render.resolution_x = 960
    scene.render.resolution_y = 540
    scene.render.image_settings.file_format = "PNG"
    world = bpy.data.worlds.new("sea")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.10, 0.30, 0.42, 1.0)
    bg.inputs["Strength"].default_value = 0.9
    scene.world = world

    sun_data = bpy.data.lights.new("sun", "SUN")
    sun_data.energy = 4.0
    sun = bpy.data.objects.new("sun", sun_data)
    bpy.context.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(-30))

    arm = bpy.data.objects["MantaRig"]
    os.makedirs(os.path.abspath(a.out), exist_ok=True)
    cam = setup_camera(scene, (0.0, 0.0, 0.1), (5.4, -6.2, 3.6), "cam_hero")
    top = setup_camera(scene, (0.0, 0.0, 0.0), (0.0, 0.01, 13.5), "cam_top")

    for clip, t in POSES:
        act = bpy.data.actions[clip]
        arm.animation_data.action = act
        scene.frame_set(int(round(t * FPS)))
        bpy.context.view_layer.update()
        for camera, tag in ((cam, "hero"), (top, "top")):
            scene.camera = camera
            scene.render.filepath = os.path.join(os.path.abspath(a.out), f"{clip}_{t:.2f}_{tag}.png")
            bpy.ops.render.render(write_still=True)
        print("rendered", clip, t)


if __name__ == "__main__":
    main()
