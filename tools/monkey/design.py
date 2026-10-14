"""
Anatomy + skeleton definition for the Paradise Island monkey (long-tailed-macaque-like).

One source of truth: every SDF primitive is bound to the bone it deforms with, so skin
weights can later be derived straight from the primitives that built each surface point.

Coordinates are Blender world axes in metres. The monkey faces -Y (so it faces +Z after the
glTF Y-up conversion), +X is its left, +Z is up. P(x, f, z) takes x lateral (+left),
f forward distance, z height, and returns the Blender-space point.
"""
import numpy as np

from sdf import Ellipsoid, RoundCone, Sphere

SIDES = ((1.0, "L"), (-1.0, "R"))
EYE_R = 0.0082   # eyeball radius (metres)


def P(x, f, z):
    return np.array([x, -f, z], float)


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


class Design:
    def __init__(self):
        self.bones = {}        # name -> dict(parent, head, tail, deform)
        self.ops = []          # (op, prim, k)
        self.digit_bones = {}  # group -> [bone names]

    def bone(self, name, parent, head, tail, deform=True):
        assert name not in self.bones, name
        self.bones[name] = dict(parent=parent, head=np.asarray(head, float),
                                tail=np.asarray(tail, float), deform=deform)

    def add(self, prim, bone, k=0.0, T=0.004, name=""):
        prim.bone, prim.T, prim.name = bone, T, name or bone
        self.ops.append(("add", prim, k))
        return prim

    def sub(self, prim, k=0.0, name=""):
        prim.bone, prim.T, prim.name = None, 0.0, name or "carve"
        self.ops.append(("sub", prim, k))
        return prim

    def prims(self):
        return [p for op, p, _ in self.ops if op == "add"]


def curl_dir(d, down_deg):
    """Rotate direction d toward -Z by down_deg degrees."""
    d = unit(d)
    down = np.array([0.0, 0.0, -1.0])
    perp = down - d * (d @ down)
    n = np.linalg.norm(perp)
    if n < 1e-6:
        return d
    perp /= n
    a = np.radians(down_deg)
    return unit(d * np.cos(a) + perp * np.sin(a))


def digit(D, prefix, parent, base, direction, lens, radii, curls, tag, first_index=1, k=0.004, T=0.0028):
    """Create bones prefix_<i>_<tag> + capsules. Returns list of bone names."""
    pos = np.asarray(base, float)
    d = unit(direction)
    prev = parent
    out = []
    for i, ln in enumerate(lens):
        d_i = curl_dir(d, curls[i])
        end = pos + d_i * ln
        bname = f"{prefix}_{first_index + i}_{tag}"
        D.bone(bname, prev, pos, end)
        D.add(RoundCone(pos, end, radii[i], radii[i + 1]), bname, k=(k if i == 0 else 0.0), T=T)
        out.append(bname)
        prev, pos, d = bname, end, d_i
    return out


def yaw_dir(deg, side, forward=-1.0):
    """Direction in the XY plane yawed laterally (positive = outward for the given side)."""
    a = np.radians(deg)
    return np.array([side * np.sin(a), forward * np.cos(a), 0.0])


def build():
    D = Design()
    pelvis_c = P(0, 0.0, 0.232)

    # ---- spine ---------------------------------------------------------------------------
    D.bone("root", None, P(0, 0.0, 0.0), P(0, 0.07, 0.0))
    D.bone("pelvis", "root", P(0, -0.02, 0.236), P(0, 0.05, 0.245))
    D.bone("spine1", "pelvis", P(0, 0.05, 0.245), P(0, 0.12, 0.255))
    D.bone("spine2", "spine1", P(0, 0.12, 0.255), P(0, 0.19, 0.262))
    D.bone("spine3", "spine2", P(0, 0.19, 0.262), P(0, 0.26, 0.268))
    D.bone("neck1", "spine3", P(0, 0.26, 0.268), P(0, 0.31, 0.294))
    D.bone("neck2", "neck1", P(0, 0.31, 0.294), P(0, 0.345, 0.312))
    D.bone("head", "neck2", P(0, 0.345, 0.312), P(0, 0.415, 0.332))
    D.bone("jaw", "head", P(0, 0.382, 0.297), P(0, 0.452, 0.287))

    # torso masses (big blend radius so it reads as one body)
    D.add(Ellipsoid(P(0, 0.0, 0.232), (0.060, 0.074, 0.058)), "pelvis", k=0.04, T=0.007, name="pelvis")
    D.add(Ellipsoid(P(0, -0.022, 0.237), (0.05, 0.045, 0.05)), "pelvis", k=0.04, T=0.007, name="rump")
    D.add(Ellipsoid(P(0, 0.082, 0.230), (0.055, 0.070, 0.057)), "spine1", k=0.04, T=0.007, name="belly")
    D.add(Ellipsoid(P(0, 0.128, 0.244), (0.054, 0.060, 0.052)), "spine2", k=0.04, T=0.007, name="waist")
    D.add(Ellipsoid(P(0, 0.205, 0.260), (0.062, 0.092, 0.084)), "spine2", k=0.04, T=0.007, name="ribs")
    D.add(Ellipsoid(P(0, 0.255, 0.256), (0.060, 0.055, 0.082)), "spine3", k=0.04, T=0.007, name="chest")
    D.add(Ellipsoid(P(0, 0.240, 0.290), (0.045, 0.055, 0.030)), "spine3", k=0.04, T=0.007, name="withers")
    D.add(Ellipsoid(P(0, 0.262, 0.236), (0.030, 0.040, 0.040)), "spine3", k=0.03, T=0.007, name="keel")

    # neck
    D.add(RoundCone(P(0, 0.262, 0.274), P(0, 0.312, 0.296), 0.044, 0.038), "neck1", k=0.03, T=0.006)
    D.add(RoundCone(P(0, 0.312, 0.296), P(0, 0.345, 0.312), 0.038, 0.036), "neck2", k=0.03, T=0.006)

    # ---- head ------------------------------------------------------------------------------
    D.add(Ellipsoid(P(0, 0.384, 0.328), (0.0365, 0.043, 0.038)), "head", k=0.03, T=0.005, name="cranium")
    D.add(Ellipsoid(P(0, 0.364, 0.320), (0.033, 0.030, 0.034)), "head", k=0.02, T=0.005, name="occiput")
    # face plane + muzzle: long, tapering, macaque-like
    D.add(Ellipsoid(P(0, 0.4235, 0.314), (0.0212, 0.0305, 0.0245), rot=(-8, 0, 0)), "head", k=0.02, T=0.005,
          name="muzzle")
    D.add(Ellipsoid(P(0, 0.4425, 0.303), (0.0172, 0.0185, 0.0135)), "head", k=0.012, T=0.004, name="upper_lip")
    D.add(Ellipsoid(P(0, 0.4495, 0.3115), (0.0088, 0.0065, 0.0082)), "head", k=0.008, T=0.004, name="nose")
    for s, t in SIDES:
        # strong horizontal brow ridge running into the glabella
        D.add(RoundCone(P(s * 0.002, 0.4150, 0.3450), P(s * 0.031, 0.4040, 0.3430), 0.0098, 0.0085),
              "head", k=0.012, T=0.004, name=f"brow_{t}")
        D.add(Ellipsoid(P(s * 0.026, 0.402, 0.306), (0.0085, 0.016, 0.012)), "head", k=0.02, T=0.004,
              name=f"cheek_{t}")
    # lower jaw (rotates with the jaw bone), set back so the chin recedes slightly
    D.add(Ellipsoid(P(0, 0.4165, 0.2905), (0.0195, 0.0295, 0.0125)), "jaw", k=0.012, T=0.003, name="jaw")
    D.add(Ellipsoid(P(0, 0.4365, 0.2865), (0.0118, 0.0105, 0.0095)), "jaw", k=0.010, T=0.003, name="chin")
    D.add(Ellipsoid(P(0, 0.4415, 0.2975), (0.0118, 0.0065, 0.0042)), "jaw", k=0.004, T=0.003, name="lower_lip")
    for s, t in SIDES:
        D.add(Ellipsoid(P(s * 0.025, 0.394, 0.292), (0.0075, 0.016, 0.011)), "jaw", k=0.014, T=0.004,
              name=f"jaw_angle_{t}")

    # fur volume cues: cheek ruff sweeping back, crown ridge, brow tufts
    for s, t in SIDES:
        D.add(Ellipsoid(P(s * 0.034, 0.384, 0.300), (0.0095, 0.024, 0.0115), rot=(0, 0, -s * 28)), "head",
              k=0.014, T=0.004, name=f"cheek_ruff_{t}")
    D.add(Ellipsoid(P(0, 0.372, 0.3585), (0.0105, 0.022, 0.0075)), "head", k=0.012, T=0.004, name="crown")

    # ears: cupped shells (outer lobe minus inner bowl) so they read as ears, not plates
    for s, t in SIDES:
        D.bone(f"ear_{t}", "head", P(s * 0.040, 0.368, 0.326), P(s * 0.060, 0.362, 0.346))
        D.add(Ellipsoid(P(s * 0.046, 0.366, 0.330), (0.0075, 0.0165, 0.0205), rot=(0, 0, -s * 22)),
              f"ear_{t}", k=0.008, T=0.003, name=f"ear_{t}")
        D.add(Ellipsoid(P(s * 0.0465, 0.3695, 0.3335), (0.0060, 0.0115, 0.0125), rot=(0, 0, -s * 22)),
              f"ear_{t}", k=0.004, T=0.003, name=f"ear_lobe_{t}")
        D.sub(Ellipsoid(P(s * 0.0545, 0.3705, 0.3335), (0.0048, 0.0120, 0.0150), rot=(0, 0, -s * 22)),
              k=0.004, name=f"ear_bowl_{t}")

    # facial carving: snug eye sockets + under-brow hollow. Nostrils, mouth line and lip creases are
    # too small for the voxel size to carve reliably, so they live in the normal/albedo maps instead.
    for s, t in SIDES:
        D.sub(Sphere(P(s * 0.0215, 0.4195, 0.3315), 0.0095), k=0.004, name=f"socket_{t}")
        D.sub(Ellipsoid(P(s * 0.0205, 0.4285, 0.3300), (0.0100, 0.0085, 0.0085)), k=0.006, name=f"underbrow_{t}")

    # ---- arms (each side) -----------------------------------------------------------------
    for s, t in SIDES:
        shoulder = P(s * 0.062, 0.268, 0.242)
        elbow = P(s * 0.068, 0.216, 0.128)
        wrist = P(s * 0.062, 0.292, 0.032)
        knuckle = P(s * 0.060, 0.337, 0.0065)
        D.bone(f"clavicle_{t}", "spine3", P(s * 0.022, 0.252, 0.268), shoulder)
        D.bone(f"upper_arm_{t}", f"clavicle_{t}", shoulder, elbow)
        D.bone(f"forearm_{t}", f"upper_arm_{t}", elbow, wrist)
        D.bone(f"hand_{t}", f"forearm_{t}", wrist, knuckle)
        D.add(Ellipsoid(P(s * 0.050, 0.255, 0.258), (0.028, 0.040, 0.042)), f"clavicle_{t}", k=0.035, T=0.007,
              name=f"shoulder_mass_{t}")
        D.add(RoundCone(P(s * 0.025, 0.255, 0.262), shoulder, 0.030, 0.032), f"clavicle_{t}", k=0.03, T=0.006)
        D.add(RoundCone(shoulder, elbow, 0.027, 0.018), f"upper_arm_{t}", k=0.025, T=0.005)
        D.add(RoundCone(elbow, wrist, 0.0175, 0.011), f"forearm_{t}", k=0.012, T=0.004)
        D.add(Ellipsoid(elbow * 0.7 + wrist * 0.3 + np.array([0, -0.002, 0.004]), (0.0125, 0.016, 0.026),
                        rot=(-10, 0, 0)), f"forearm_{t}", k=0.016, T=0.004, name=f"forearm_mass_{t}")
        D.add(Ellipsoid(P(s * 0.0615, 0.3135, 0.0165), (0.0215, 0.0285, 0.0082), rot=(20, 0, 0)),
              f"hand_{t}", k=0.008, T=0.003, name=f"palm_{t}")

        # fingers: index, middle, ring, pinky, thumb
        fingers = [  # name, x offset from hand centre, yaw, length scale
            ("index", -0.0120, -4.0, 0.92),
            ("middle", -0.0010, 0.0, 1.00),
            ("ring", 0.0100, 6.0, 0.95),
            ("pinky", 0.0190, 14.0, 0.76),
        ]
        for fname, dx, yaw, sc in fingers:
            base = P(s * (0.0605 + dx), 0.337, 0.0065)
            digit(D, f"f_{fname}", f"hand_{t}", base, yaw_dir(yaw, s),
                  [0.022 * sc, 0.015 * sc, 0.012 * sc], [0.0058, 0.0052, 0.0046, 0.0038], [3, 5, 5], t)
        digit(D, "f_thumb", f"hand_{t}", P(s * 0.046, 0.308, 0.0185), yaw_dir(-38, s),
              [0.022, 0.017, 0.014], [0.0078, 0.0068, 0.0058, 0.0046], [4, 4, 4], t, first_index=0)

    # ---- legs (each side) -----------------------------------------------------------------
    for s, t in SIDES:
        hip = P(s * 0.046, 0.012, 0.214)
        knee = P(s * 0.064, 0.088, 0.119)
        ankle = P(s * 0.050, 0.016, 0.034)
        ball = P(s * 0.054, 0.085, 0.0075)
        D.bone(f"thigh_{t}", "pelvis", hip, knee)
        D.bone(f"shin_{t}", f"thigh_{t}", knee, ankle)
        D.bone(f"foot_{t}", f"shin_{t}", ankle, ball)
        D.add(Ellipsoid(P(s * 0.054, 0.034, 0.176), (0.031, 0.042, 0.041)), f"thigh_{t}", k=0.035, T=0.007,
              name=f"thigh_mass_{t}")
        D.add(RoundCone(hip, knee, 0.034, 0.021), f"thigh_{t}", k=0.03, T=0.006)
        D.add(RoundCone(knee, ankle, 0.0205, 0.0105), f"shin_{t}", k=0.012, T=0.004)
        D.add(Ellipsoid(P(s * 0.060, 0.068, 0.104), (0.0125, 0.016, 0.022), rot=(-25, 0, 0)), f"shin_{t}",
              k=0.016, T=0.004, name=f"calf_{t}")
        D.add(Ellipsoid(P(s * 0.050, 0.008, 0.030), (0.011, 0.014, 0.012)), f"foot_{t}", k=0.008, T=0.003,
              name=f"heel_{t}")
        D.add(Ellipsoid(P(s * 0.0535, 0.050, 0.0165), (0.015, 0.040, 0.0095), rot=(21, 0, 0)),
              f"foot_{t}", k=0.008, T=0.003, name=f"sole_{t}")
        toes = [("t_index", -0.0075, -3.0, 0.90), ("t_middle", 0.0, 0.0, 1.0),
                ("t_ring", 0.0075, 5.0, 0.92), ("t_pinky", 0.0145, 12.0, 0.72)]
        for tname, dx, yaw, sc in toes:
            base = P(s * (0.0535 + dx), 0.085, 0.0075)
            digit(D, tname, f"foot_{t}", base, yaw_dir(yaw, s),
                  [0.017 * sc, 0.012 * sc, 0.010 * sc], [0.0052, 0.0047, 0.0042, 0.0034], [3, 5, 5], t)
        digit(D, "t_hallux", f"foot_{t}", P(s * 0.0405, 0.066, 0.0105), yaw_dir(-30, s),
              [0.017, 0.017, 0.013], [0.0068, 0.0062, 0.0054, 0.0044], [3, 4, 4], t, first_index=0)

    # ---- tail ------------------------------------------------------------------------------
    pos = P(0, -0.035, 0.246)
    pitches = [20, 12, 2, -10, -24, -38, -50, -60, -66, -70]
    radii = np.linspace(0.0165, 0.0075, len(pitches) + 1)
    joints = [pos]
    prev = "pelvis"
    for i, a in enumerate(pitches):
        a_r = np.radians(a)
        end = pos + np.array([0.0, np.cos(a_r) * 0.043, np.sin(a_r) * 0.043])  # +Y is backwards
        nm = f"tail_{i + 1}"
        D.bone(nm, prev, pos, end)
        joints.append(end)
        prev, pos = nm, end
    # Catmull-Rom through the joints, sampled finely; hard union keeps the surface smooth
    pts = np.array(joints)
    ext = np.vstack([pts[0] * 2 - pts[1], pts, pts[-1] * 2 - pts[-2]])
    samples = []
    per = 6
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for j in range(per):
            u = j / per
            c = 0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u
                       + (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3)
            samples.append((i - 1 + u, c))
    samples.append((len(pitches), pts[-1]))
    for (u0, c0), (u1, c1) in zip(samples[:-1], samples[1:]):
        bone = f"tail_{min(int(u0), len(pitches) - 1) + 1}"
        r0 = np.interp(u0, np.arange(len(radii)), radii)
        r1 = np.interp(u1, np.arange(len(radii)), radii)
        D.add(RoundCone(c0, c1, r0, r1), bone, k=0.03 if u0 < 0.4 else 0.0, T=0.005, name="tail")

    # ---- eyes / prop bones (no body primitives) -------------------------------------------------
    for s, t in SIDES:
        c = P(s * 0.0215, 0.4195, 0.3315)
        D.bone(f"eye_{t}", "head", c, c + np.array([0.0, -0.012, 0.0]))
        for part in ("up", "low"):
            D.bone(f"lid_{part}_{t}", "head", c, c + np.array([0.0, -0.012, 0.0]))
    D.bone("coconut_attach", "root", P(0, 0.2, 0.15), P(0, 0.22, 0.15))
    return D


def mesh_bounds(D, margin=0.03):
    lo = np.full(3, np.inf)
    hi = np.full(3, -np.inf)
    for op, p, k in D.ops:
        a, b = p.bounds()
        lo, hi = np.minimum(lo, a), np.maximum(hi, b)
    return lo - margin, hi + margin
