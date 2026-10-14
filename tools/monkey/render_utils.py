"""Shared helpers for preview renders of the monkey (EEVEE on software GL, or Cycles)."""
import math
import os

import bpy
from mathutils import Vector


def setup_world(strength=0.9, color=(0.62, 0.70, 0.78)):
    sc = bpy.context.scene
    w = bpy.data.worlds.new("PreviewWorld")
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (*color, 1.0)
    bg.inputs["Strength"].default_value = strength
    sc.world = w


def setup_lights(key=4.0, fill=1.2, rim=2.5):
    sc = bpy.context.scene
    for name, energy, rot, color in (
        ("Key", key, (math.radians(52), 0, math.radians(35)), (1.0, 0.95, 0.88)),
        ("Fill", fill, (math.radians(65), 0, math.radians(-120)), (0.75, 0.85, 1.0)),
        ("Rim", rim, (math.radians(115), 0, math.radians(160)), (1.0, 0.96, 0.9)),
    ):
        ld = bpy.data.lights.new(name, "SUN")
        ld.energy = energy
        ld.color = color
        ob = bpy.data.objects.new(name, ld)
        ob.rotation_euler = rot
        sc.collection.objects.link(ob)


def add_ground(size=2.0, color=(0.30, 0.34, 0.26)):
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, 0))
    g = bpy.context.active_object
    m = bpy.data.materials.new("Ground")
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*color, 1)
    m.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.95
    g.data.materials.append(m)
    g.name = "PreviewGround"
    return g


def setup_engine(size=(900, 900), engine="BLENDER_EEVEE", samples=16):
    sc = bpy.context.scene
    sc.render.engine = engine
    sc.render.resolution_x, sc.render.resolution_y = size
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = "PNG"
    if engine == "BLENDER_EEVEE":
        try:
            sc.eevee.taa_render_samples = samples
        except Exception:
            pass
    elif engine == "CYCLES":
        sc.cycles.samples = samples
        sc.cycles.device = "CPU"
        sc.cycles.use_denoising = False
    sc.view_settings.view_transform = "Standard"


def make_camera(lens=60):
    sc = bpy.context.scene
    cd = bpy.data.cameras.new("PreviewCam")
    cd.lens = lens
    cam = bpy.data.objects.new("PreviewCam", cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    return cam


def aim(cam, location, target):
    cam.location = Vector(location)
    d = Vector(target) - cam.location
    cam.rotation_mode = "QUATERNION"
    cam.rotation_quaternion = d.to_track_quat("-Z", "Y")


def render(path):
    sc = bpy.context.scene
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path
