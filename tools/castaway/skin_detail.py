"""Crease / wrinkle / anatomical line definitions (world polylines) used to carve the skin normal map.

Each class is (name, depth_m, sigma_m, polylines). Polylines are lists of 3D points in model space (P helper).
"""
import numpy as np

from hdesign import MOUTH_Z, P

SIDES = ((1.0, "L"), (-1.0, "R"))


def arc(a, b, bulge, n=14, axis=(0, 0, 1)):
    """Polyline from a to b with a sideways bulge along `axis` (parabolic)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    t = np.linspace(0, 1, n)[:, None]
    base = a + (b - a) * t
    return base + np.asarray(axis, float) * bulge * (4 * t * (1 - t))


def resample(poly, step=0.0008):
    poly = np.asarray(poly, float)
    out = [poly[0]]
    for a, b in zip(poly[:-1], poly[1:]):
        L = np.linalg.norm(b - a)
        k = max(int(np.ceil(L / step)), 1)
        for j in range(1, k + 1):
            out.append(a + (b - a) * j / k)
    return np.array(out)


def face_classes():
    cls = []
    # forehead lines: four gentle horizontal furrows, deeper at the centre (weathered, expressive)
    fore = []
    for z, w, d in ((1.9375, 0.050, 0.00055), (1.9505, 0.052, 0.00060), (1.9635, 0.048, 0.00050), (1.9760, 0.040, 0.00035)):
        pts = []
        for x in np.linspace(-w, w, 24):
            f = 0.090 - 0.0044 * (x / w) ** 2 * 6 - 0.0012 * (z - 1.9375) * 100
            pts.append(P(x, max(f, 0.05), z + 0.0012 * (x / w) ** 2 * 3))
        fore.append(pts)
    cls.append(("forehead_lines", 0.00050, 0.0014, fore))
    # glabellar furrows (between the brows) + nasion
    gl = []
    for s, t in SIDES:
        gl.append([P(s * 0.0045, 0.0955, 1.904), P(s * 0.0042, 0.0975, 1.9035 + 0.0055), P(s * 0.0050, 0.0955, 1.9035 + 0.0125)])
    cls.append(("glabella", 0.00055, 0.0010, gl))
    # crow's feet (outer canthus), under-eye bags and lid creases
    cf, bags, lids = [], [], []
    for s, t in SIDES:
        ec = np.array([s * 0.032, -0.070, 1.877])
        outer = P(s * 0.0485, 0.070, 1.878)
        for ang, ln in ((24, 0.019), (2, 0.021), (-20, 0.017)):
            a = np.radians(ang)
            end = outer + np.array([s * np.cos(a) * ln * 0.55, np.sin(0) * 0, np.sin(a) * ln])
            end = P(s * (0.0485 + np.cos(a) * ln * 0.55), 0.064 - 0.0012, 1.878 + np.sin(a) * ln)
            cf.append(arc(P(s * 0.0485, 0.0700, 1.878), end, 0.0, 8))
        bags.append(arc(P(s * 0.019, 0.083, 1.8645), P(s * 0.0455, 0.0705, 1.8645), -0.0030, 16))
        bags.append(arc(P(s * 0.020, 0.085, 1.8575), P(s * 0.0440, 0.0725, 1.8575), -0.0035, 16))
        lids.append(arc(P(s * 0.0165, 0.084, 1.8945), P(s * 0.0480, 0.0715, 1.8925), 0.0028, 16))
    cls.append(("crows_feet", 0.00040, 0.0009, cf))
    cls.append(("eye_bags", 0.00055, 0.0013, bags))
    cls.append(("lid_creases", 0.00060, 0.0008, lids))
    # nasolabial folds: nose wing -> past the mouth corner
    nl = []
    for s, t in SIDES:
        nl.append(arc(P(s * 0.0225, 0.0925, 1.8285), P(s * 0.0345, 0.0820, 1.7930), 0.0025, 16, axis=(s, 0, 0)))
        nl.append(arc(P(s * 0.0345, 0.0820, 1.7930), P(s * 0.0335, 0.0770, 1.7740), -0.002, 10, axis=(s, 0, 0)))
    cls.append(("nasolabial", 0.00085, 0.0020, nl))
    # lip detail: vertical lip lines and the philtrum columns
    lip = []
    for x in np.linspace(-0.018, 0.018, 13):
        lip.append([P(x, 0.0925 - 0.0008 * abs(x) * 20, MOUTH_Z + 0.0012), P(x, 0.0975 - 0.0005 * abs(x) * 20, MOUTH_Z + 0.0100)])
        lip.append([P(x, 0.0910, MOUTH_Z - 0.0012), P(x, 0.0950, MOUTH_Z - 0.0095)])
    cls.append(("lip_lines", 0.00018, 0.00045, lip))
    ph = [[P(s * 0.0042, 0.0975, 1.8135), P(s * 0.0050, 0.0985, 1.8275)] for s, t in SIDES]
    cls.append(("philtrum", 0.00060, 0.0011, ph))
    # neck creases + collarbone/sternal notch lines
    neck = []
    for z, rad in ((1.742, 0.0535), (1.722, 0.0555), (1.700, 0.0575)):
        neck.append([P(x, -0.016 + np.sqrt(max(rad ** 2 - x ** 2, 0.0)), z) for x in np.linspace(-rad * 0.95, rad * 0.95, 24)])
    cls.append(("neck_creases", 0.00040, 0.0018, neck))
    return cls


def joint_rings(rest, names_fn):
    """Small rings around finger/toe joints (skin creases)."""
    return []
