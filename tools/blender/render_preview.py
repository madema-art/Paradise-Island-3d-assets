"""
Round-trip check: re-import a .glb into an empty scene, print what Blender sees,
and render a preview PNG (Cycles, CPU, so it works without a GPU or display).

  blender -b --factory-startup -P tools/blender/render_preview.py -- --glb assets/test/tropical_fish/TropicalFish.glb --out assets/test/tropical_fish/preview.png
  /opt/bpy-venv/bin/python tools/blender/render_preview.py -- --glb ... --out ...
"""
import argparse
import os
import sys

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--glb", required=True)
    p.add_argument("--out", required=True, help="preview PNG path")
    p.add_argument("--samples", type=int, default=48)
    return p.parse_args(argv)


def main():
    args = parse_args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=os.path.abspath(args.glb))

    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    verts = sum(len(o.data.vertices) for o in meshes)
    tris = sum(len(p.vertices) - 2 for o in meshes for p in o.data.polygons)
    print(f"[reimport] blender={bpy.app.version_string} mesh_objects={len(meshes)} "
          f"vertices={verts} triangles={tris}")
    print(f"[reimport] materials={[m.name for m in bpy.data.materials]}")
    print(f"[reimport] images={[(i.name, tuple(i.size)) for i in bpy.data.images]}")

    if not meshes:
        sys.exit("no mesh objects imported")

    # Frame the fish from the side
    corners = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
    center = sum(corners, Vector()) / len(corners)

    scene = bpy.context.scene
    cam_data = bpy.data.cameras.new("PreviewCam")
    cam = bpy.data.objects.new("PreviewCam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = center + Vector((0.0, -3.2, 0.5))
    direction = center - cam.location
    cam.rotation_mode = "QUATERNION"
    cam.rotation_quaternion = direction.to_track_quat("-Z", "Y")
    cam_data.lens = 70
    scene.camera = cam

    sun_data = bpy.data.lights.new("Sun", "SUN")
    sun_data.energy = 3.5
    sun = bpy.data.objects.new("Sun", sun_data)
    scene.collection.objects.link(sun)
    sun.rotation_euler = (0.9, 0.2, 0.6)

    world = bpy.data.worlds.new("Sea")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.55, 0.78, 0.92, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
    scene.world = world

    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = False  # the Ubuntu Blender 4.0 build has no OpenImageDenoiser
    scene.render.resolution_x = 800
    scene.render.resolution_y = 500
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = os.path.abspath(args.out)
    bpy.ops.render.render(write_still=True)
    print(f"[render] preview -> {scene.render.filepath}")


if __name__ == "__main__":
    main()
