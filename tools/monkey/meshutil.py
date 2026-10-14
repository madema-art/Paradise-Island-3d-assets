"""Small numpy <-> bpy mesh helpers shared by the monkey scripts."""
import numpy as np


def signed_volume(V, F):
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    return float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0)


def orient_outward(V, F):
    """Flip triangle winding if the mesh volume is negative (normals pointing inward)."""
    if signed_volume(V, F) < 0:
        F = F[:, ::-1].copy()
    return F


def mesh_from_arrays(bpy, name, V, F):
    V = np.ascontiguousarray(V, dtype=np.float32)
    F = np.ascontiguousarray(F, dtype=np.int32)
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(V))
    me.vertices.foreach_set("co", V.ravel())
    n = len(F)
    me.loops.add(3 * n)
    me.loops.foreach_set("vertex_index", F.ravel())
    me.polygons.add(n)
    me.polygons.foreach_set("loop_start", np.arange(0, 3 * n, 3, dtype=np.int32))
    me.polygons.foreach_set("loop_total", np.full(n, 3, dtype=np.int32))
    me.update(calc_edges=True)
    me.validate()
    return me


def arrays_from_mesh(me):
    V = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", V)
    F = np.empty(len(me.polygons) * 3, np.int32)
    me.polygons.foreach_get("vertices", F)
    return V.reshape(-1, 3).astype(np.float64), F.reshape(-1, 3).astype(np.int64)
