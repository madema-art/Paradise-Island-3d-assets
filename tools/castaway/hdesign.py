"""
Anatomy + skeleton definition for the Paradise Island castaway (2.00 m, lanky, lean adult male).

One source of truth: every SDF primitive is bound to the bone it deforms with, so skin weights can be derived from the
primitives that built each surface point (same method as the monkey).

Blender world axes in metres. The castaway faces -Y (+Z in glTF), +X is his LEFT, +Z is up.
P(x, f, z): lateral (+ = left), forward distance, height.
Rest pose: relaxed A-pose, arms abducted 30 degrees, palms facing the thighs, fingers softly curled.
"""
import numpy as np

from hsdf import Ellipsoid, FrameEllipsoid, Loft, RoundCone, Sphere, ellipsoid_between, frame_from, unit

SIDES = ((1.0, "L"), (-1.0, "R"))
EYE_R = 0.0121          # eyeball radius
LID_R = 0.0140          # eyelid skin shell radius around the eyeball centre
HEIGHT = 2.0
MOUTH_Z = 1.7945        # mouth line (stomion)
LIP_SQUEEZE = 0.00225   # sculpted slit half-height, closed again by a warp before skinning


def P(x, f, z):
    return np.array([x, -f, z], float)


class Design:
    def __init__(self):
        self.bones = {}
        self.ops = []
        self.lm = {}   # landmarks used by other stages

    def bone(self, name, parent, head, tail, deform=True):
        assert name not in self.bones, name
        self.bones[name] = dict(parent=parent, head=np.asarray(head, float), tail=np.asarray(tail, float), deform=deform)

    def add(self, prim, bone, k=0.0, T=0.006, name=""):
        prim.bone, prim.T, prim.name = bone, T, name or bone
        self.ops.append(("add", prim, k))
        return prim

    def sub(self, prim, k=0.0, name=""):
        prim.bone, prim.T, prim.name = None, 0.0, name or "carve"
        self.ops.append(("sub", prim, k))
        return prim

    def prims(self):
        return [p for op, p, _ in self.ops if op == "add"]


def curl(d, toward, deg):
    """Rotate direction d toward unit vector `toward` (assumed perpendicular to d) by deg."""
    a = np.radians(deg)
    return unit(d * np.cos(a) + toward * np.sin(a))


def mesh_bounds(D, margin=0.03):
    lo = np.full(3, np.inf)
    hi = np.full(3, -np.inf)
    for op, p, k in D.ops:
        if op != "add":
            continue
        a, b = p.bounds()
        lo, hi = np.minimum(lo, a), np.maximum(hi, b)
    lo[2] = max(lo[2], -0.004)    # nothing below the sole plane
    return lo - margin, hi + margin


# --------------------------------------------------------------------------------------------------------------------
def build():
    D = Design()
    X = np.array([1.0, 0, 0])
    Y = np.array([0, 1.0, 0])
    Z = np.array([0, 0, 1.0])
    FWD = -Y

    # ================================================================================== skeleton: trunk
    D.bone("root", None, P(0, 0, 0), P(0, 0.12, 0))
    D.bone("pelvis", "root", P(0, -0.012, 1.000), P(0, -0.005, 1.085))
    D.bone("spine1", "pelvis", P(0, -0.005, 1.085), P(0, 0.002, 1.205))
    D.bone("spine2", "spine1", P(0, 0.002, 1.205), P(0, 0.000, 1.330))
    D.bone("spine3", "spine2", P(0, 0.000, 1.330), P(0, -0.006, 1.470))
    D.bone("spine4", "spine3", P(0, -0.006, 1.470), P(0, -0.014, 1.610))
    D.bone("neck1", "spine4", P(0, -0.020, 1.625), P(0, -0.018, 1.700))
    D.bone("neck2", "neck1", P(0, -0.018, 1.700), P(0, -0.012, 1.775))
    D.bone("head", "neck2", P(0, -0.012, 1.775), P(0, 0.000, 2.000))
    D.bone("jaw", "head", P(0, -0.010, 1.838), P(0, 0.085, 1.765))

    # ---- pelvis & abdomen (lean, narrow hips, long torso)
    D.add(Ellipsoid(P(0, -0.004, 1.040), (0.160, 0.106, 0.085)), "pelvis", k=0.05, T=0.012, name="pelvis")
    for s, t in SIDES:
        D.add(Ellipsoid(P(s * 0.075, -0.066, 0.990), (0.066, 0.058, 0.078), rot=(0, s * 6, 0)), "pelvis", k=0.05, T=0.012, name=f"glute_{t}")
        D.add(Ellipsoid(P(s * 0.128, 0.004, 1.105), (0.026, 0.062, 0.050)), "pelvis", k=0.035, T=0.010, name=f"iliac_{t}")
    D.add(Ellipsoid(P(0, 0.020, 1.112), (0.136, 0.094, 0.092)), "spine1", k=0.05, T=0.012, name="lower_abdomen")
    D.add(Ellipsoid(P(0, 0.012, 1.225), (0.136, 0.092, 0.118)), "spine2", k=0.05, T=0.012, name="abdomen")
    D.add(Ellipsoid(P(0, 0.002, 1.355), (0.152, 0.106, 0.125)), "spine3", k=0.05, T=0.012, name="lower_ribcage")
    D.add(Ellipsoid(P(0, 0.002, 1.470), (0.172, 0.114, 0.118)), "spine3", k=0.05, T=0.012, name="ribcage")
    D.add(Ellipsoid(P(0, -0.003, 1.570), (0.170, 0.098, 0.075)), "spine4", k=0.05, T=0.012, name="upper_chest")
    # rectus abdominis: two long flat columns, lean-defined
    for s, t in SIDES:
        D.add(Ellipsoid(P(s * 0.076, 0.078, 1.500), (0.078, 0.038, 0.058), rot=(0, 0, s * 6)), "spine4", k=0.03, T=0.010, name=f"pec_{t}")
        D.add(Ellipsoid(P(s * 0.120, -0.056, 1.415), (0.050, 0.032, 0.120), rot=(0, s * 8, 0)), "spine3", k=0.04, T=0.010, name=f"lat_{t}")
        D.add(Ellipsoid(P(s * 0.094, -0.088, 1.520), (0.052, 0.014, 0.062), rot=(0, 0, 0)), "spine4", k=0.045, T=0.010, name=f"scapula_{t}")
        D.add(Ellipsoid(P(s * 0.032, -0.074, 1.255), (0.026, 0.017, 0.105)), "spine2", k=0.035, T=0.010, name=f"erector_{t}")
        D.add(Ellipsoid(P(s * 0.158, 0.0, 1.606), (0.064, 0.058, 0.050)), "spine4", k=0.04, T=0.010, name=f"shoulder_mass_{t}")
        D.add(Ellipsoid(P(s * 0.092, -0.026, 1.655), (0.082, 0.042, 0.022), rot=(0, s * 15, 0)), "spine4", k=0.03, T=0.008, name=f"trap_{t}")

    # ---- neck
    D.add(RoundCone(P(0, -0.020, 1.615), P(0, -0.014, 1.780), 0.061, 0.0525), "neck1", k=0.03, T=0.008, name="neck")
    for s, t in SIDES:
        D.add(RoundCone(P(s * 0.042, -0.010, 1.768), P(s * 0.020, 0.034, 1.640), 0.0125, 0.0105), "neck2", k=0.012, T=0.006, name=f"scm_{t}")
    D.add(Ellipsoid(P(0, 0.037, 1.718), (0.010, 0.012, 0.017)), "neck1", k=0.010, T=0.005, name="adams_apple")

    # ================================================================================== head & face
    D.lm.update(head_c=P(0, 0, 1.90))
    D.add(Ellipsoid(P(0, -0.003, 1.905), (0.0735, 0.1015, 0.098)), "head", k=0.03, T=0.008, name="cranium")
    D.add(Ellipsoid(P(0, 0.030, 1.808), (0.052, 0.062, 0.064)), "head", k=0.03, T=0.008, name="lower_face")
    D.add(Ellipsoid(P(0, 0.036, 1.866), (0.060, 0.060, 0.045)), "head", k=0.03, T=0.008, name="midface")
    for s, t in SIDES:
        # zygomatic arch + malar prominence (defined cheekbones on a lean face)
        D.add(RoundCone(P(s * 0.054, 0.070, 1.856), P(s * 0.062, 0.000, 1.866), 0.0125, 0.0095), "head", k=0.010, T=0.006, name=f"zygoma_{t}")
        D.add(Ellipsoid(P(s * 0.046, 0.062, 1.846), (0.014, 0.013, 0.012)), "head", k=0.010, T=0.005, name=f"malar_{t}")
        # brow ridge
        D.add(RoundCone(P(s * 0.012, 0.088, 1.893), P(s * 0.047, 0.074, 1.890), 0.0100, 0.0085), "head", k=0.010, T=0.005, name=f"brow_ridge_{t}")
        # temple hollow is carved below; frontal eminence
    D.add(Ellipsoid(P(0, 0.090, 1.892), (0.016, 0.008, 0.013)), "head", k=0.010, T=0.005, name="glabella")
    # nose: bridge, tip, wings, columella
    D.add(RoundCone(P(0, 0.086, 1.886), P(0, 0.106, 1.846), 0.0088, 0.0108), "head", k=0.008, T=0.005, name="nose_bridge")
    D.add(Ellipsoid(P(0, 0.112, 1.834), (0.0108, 0.0105, 0.0100)), "head", k=0.008, T=0.004, name="nose_tip")
    for s, t in SIDES:
        D.add(Ellipsoid(P(s * 0.0128, 0.100, 1.829), (0.0085, 0.0105, 0.0085)), "head", k=0.008, T=0.004, name=f"nostril_wing_{t}")
    D.add(Ellipsoid(P(0, 0.101, 1.823), (0.0050, 0.011, 0.0065)), "head", k=0.006, T=0.004, name="columella")
    # lips (upper on the head, lower on the jaw), mouth corners
    D.add(Ellipsoid(P(0, 0.086, 1.8055), (0.0225, 0.0135, 0.0095)), "head", k=0.008, T=0.004, name="upper_lip")
    D.add(Ellipsoid(P(0, 0.090, 1.808), (0.0070, 0.0062, 0.0040)), "head", k=0.005, T=0.003, name="cupid")
    D.add(Ellipsoid(P(0, 0.084, 1.7815), (0.0215, 0.0140, 0.0095)), "jaw", k=0.008, T=0.004, name="lower_lip")
    for s, t in SIDES:
        D.add(Sphere(P(s * 0.0225, 0.072, 1.7945), 0.0080), "head", k=0.010, T=0.005, name=f"modiolus_{t}")
    # mandible: body, ramus, chin (centres sit inside the silhouette: outer edge ~ bigonial half-width 0.054)
    for s, t in SIDES:
        D.add(RoundCone(P(s * 0.036, -0.010, 1.792), P(s * 0.014, 0.074, 1.764), 0.0210, 0.0175), "jaw", k=0.012, T=0.005, name=f"mandible_{t}")
        D.add(RoundCone(P(s * 0.034, -0.010, 1.792), P(s * 0.040, -0.016, 1.858), 0.0165, 0.0140), "jaw", k=0.012, T=0.005, name=f"ramus_{t}")
    D.add(Ellipsoid(P(0, 0.078, 1.768), (0.0195, 0.0160, 0.0160)), "jaw", k=0.008, T=0.004, name="chin")
    D.add(Ellipsoid(P(0, 0.034, 1.754), (0.032, 0.046, 0.012)), "jaw", k=0.016, T=0.006, name="submental")
    # ears
    for s, t in SIDES:
        c = P(s * 0.0775, -0.004, 1.884)
        D.add(Ellipsoid(c, (0.0058, 0.0165, 0.0315)), "head", k=0.006, T=0.004, name=f"ear_{t}")
        D.add(Ellipsoid(c + np.array([s * 0.003, -0.002, 0.003]), (0.0060, 0.0125, 0.0240)), "head", k=0.004, T=0.004, name=f"ear_rim_{t}")
        D.add(Ellipsoid(P(s * 0.080, -0.001, 1.894), (0.0110, 0.0088, 0.0120)), "head", k=0.0, T=0.003, name=f"ear_lobe_{t}")

    # ---- carves: orbital hollows, temples, eye slits, mouth, nostrils
    for s, t in SIDES:
        D.lm[f"eye_{t}"] = P(s * 0.032, 0.070, 1.877)
        D.sub(Ellipsoid(P(s * 0.034, 0.090, 1.874), (0.0190, 0.014, 0.0135)), k=0.010, name=f"orbit_{t}")
        D.sub(Ellipsoid(P(s * 0.076, 0.048, 1.905), (0.009, 0.024, 0.020)), k=0.020, name=f"temple_{t}")
        D.sub(Ellipsoid(P(s * 0.066, 0.030, 1.806), (0.009, 0.034, 0.022)), k=0.020, name=f"cheek_hollow_{t}")
    # re-add the eyelid skin shell around each eyeball, then cut the almond palpebral fissure
    for s, t in SIDES:
        ec = D.lm[f"eye_{t}"]
        D.add(Sphere(ec, LID_R), "head", k=0.004, T=0.004, name=f"lid_shell_{t}")
    for s, t in SIDES:
        ec = D.lm[f"eye_{t}"]
        slit_c = ec + np.array([0.0, -0.013, 0.0])
        D.sub(Ellipsoid(slit_c, (0.0160, 0.0120, 0.0052), rot=(0, -s * 6, 0)), k=0.0, name=f"palpebral_{t}")
    # mouth: lip slit from the cavity out through the lips + the inner oral cavity
    D.sub(Ellipsoid(P(0, 0.088, MOUTH_Z), (0.0240, 0.020, LIP_SQUEEZE)), k=0.0, name="lip_slit")
    D.sub(Ellipsoid(P(0, 0.050, MOUTH_Z), (0.0300, 0.032, 0.0170)), k=0.006, name="oral_cavity")
    D.sub(Ellipsoid(P(0, 0.100, 1.770), (0.0150, 0.0060, 0.0030)), k=0.004, name="mentolabial_sulcus")
    for s, t in SIDES:
        D.sub(Ellipsoid(P(s * 0.0072, 0.108, 1.8235), (0.0036, 0.0075, 0.0030), rot=(-25, 0, 0)), k=0.0, name=f"nostril_{t}")

    # face bones (all deform; weights are generated by distance in the skinning stage)
    for s, t in SIDES:
        ec = D.lm[f"eye_{t}"]
        D.bone(f"eye_{t}", "head", ec, ec + np.array([0.0, -0.014, 0.0]))
        D.bone(f"lid_up_{t}", "head", ec, ec + np.array([0.0, -0.014, 0.012]))
        D.bone(f"lid_low_{t}", "head", ec, ec + np.array([0.0, -0.014, -0.010]))
        D.bone(f"brow_in_{t}", "head", P(s * 0.012, 0.092, 1.908), P(s * 0.016, 0.098, 1.915))
        D.bone(f"brow_mid_{t}", "head", P(s * 0.033, 0.085, 1.911), P(s * 0.036, 0.090, 1.918))
        D.bone(f"brow_out_{t}", "head", P(s * 0.054, 0.070, 1.905), P(s * 0.057, 0.074, 1.911))
        D.bone(f"cheek_{t}", "head", P(s * 0.046, 0.058, 1.832), P(s * 0.048, 0.064, 1.836))
        D.bone(f"lip_corner_{t}", "head", P(s * 0.024, 0.080, MOUTH_Z), P(s * 0.028, 0.084, MOUTH_Z))
    D.bone("lip_up", "head", P(0, 0.090, 1.808), P(0, 0.097, 1.808))
    D.bone("lip_low", "jaw", P(0, 0.088, 1.782), P(0, 0.095, 1.782))

    # ================================================================================== arms
    for s, t in SIDES:
        S = P(s * 0.185, 0.003, 1.598)                         # glenohumeral joint
        d_up = unit(np.array([s * 0.5, 0.0, -0.866]))          # 30 deg abduction
        E = S + d_up * 0.372
        d_fore = unit(np.array([s * 0.40, -0.20, -0.88]))      # slight flexion (forward = -Y)
        W = E + d_fore * 0.288
        D.lm[f"shoulder_{t}"], D.lm[f"elbow_{t}"], D.lm[f"wrist_{t}"] = S, E, W

        D.bone(f"clavicle_{t}", "spine4", P(s * 0.022, 0.050, 1.640), P(s * 0.166, 0.016, 1.633))
        D.bone(f"upper_arm_{t}", f"clavicle_{t}", S, E)
        D.bone(f"forearm_{t}", f"upper_arm_{t}", E, W)
        D.bone(f"forearm_tw1_{t}", f"forearm_{t}", E + (W - E) * 0.33, E + (W - E) * 0.55)
        D.bone(f"forearm_tw2_{t}", f"forearm_{t}", E + (W - E) * 0.66, E + (W - E) * 0.88)

        # clavicle, deltoid, acromion
        D.add(RoundCone(P(s * 0.022, 0.050, 1.640), P(s * 0.166, 0.016, 1.633), 0.0125, 0.0125), f"clavicle_{t}", k=0.015, T=0.006, name=f"clavicle_{t}")
        D.add(Sphere(P(s * 0.190, 0.004, 1.628), 0.0260), f"clavicle_{t}", k=0.025, T=0.008, name=f"acromion_{t}")
        D.add(Ellipsoid(S + np.array([s * 0.014, 0.0, 0.002]), (0.046, 0.050, 0.060)), f"upper_arm_{t}", k=0.025, T=0.010, name=f"deltoid_{t}")
        # upper arm
        D.add(RoundCone(S + d_up * 0.01, E, 0.0510, 0.0370), f"upper_arm_{t}", k=0.035, T=0.010, name=f"upper_arm_{t}")
        fr = np.array([0.0, -1.0, 0.0])   # forward direction in blender coords
        D.add(ellipsoid_between(S + d_up * 0.07, S + d_up * 0.27, 1.05, 0.033, 0.033, hint=fr, off=fr * 0.012), f"upper_arm_{t}", k=0.02, T=0.008, name=f"biceps_{t}")
        D.add(ellipsoid_between(S + d_up * 0.06, S + d_up * 0.30, 1.0, 0.032, 0.033, hint=fr, off=-fr * 0.011), f"upper_arm_{t}", k=0.02, T=0.008, name=f"triceps_{t}")
        # elbow and forearm
        D.add(Sphere(E, 0.0310), f"forearm_{t}", k=0.02, T=0.008, name=f"elbow_{t}")
        D.add(Sphere(E - fr * 0.0 + np.array([0, 0.018, -0.0]), 0.0150), f"forearm_{t}", k=0.01, T=0.005, name=f"olecranon_{t}")
        D.add(RoundCone(E, W, 0.0385, 0.0262), f"forearm_{t}", k=0.02, T=0.010, name=f"forearm_{t}")
        D.add(ellipsoid_between(E + (W - E) * 0.04, E + (W - E) * 0.50, 1.0, 0.0365, 0.0325, hint=fr, off=fr * 0.006 + np.array([s * 0.0, 0, 0])), f"forearm_{t}", k=0.02, T=0.008, name=f"forearm_flexor_{t}")
        D.add(ellipsoid_between(E + (W - E) * 0.05, E + (W - E) * 0.55, 1.0, 0.0330, 0.0325, hint=fr, off=-fr * 0.008 + np.array([s * 0.004, 0, 0])), f"forearm_{t}", k=0.02, T=0.008, name=f"forearm_extensor_{t}")

        # ---- hand
        d = unit(W - E)                                          # finger direction (down/out)
        fw = unit(FWD - d * (FWD @ d))                            # towards the thumb (forward)
        n = unit(np.cross(d, fw))
        if n[0] * s > 0:                                          # palm normal must face the body (medial)
            n = -n
        # n is the palm normal, fw the thumb side. Flexion rotates d towards n (palm side).
        D.lm[f"hand_frame_{t}"] = (d, fw, n)
        palm_len = 0.100
        K0 = W + d * palm_len                                    # knuckle line centre
        D.bone(f"hand_{t}", f"forearm_{t}", W, K0)
        D.bone(f"attach_hand_{t}", f"hand_{t}", W + d * 0.060 + n * 0.012, W + d * 0.075 + n * 0.012, deform=False)
        D.add(ellipsoid_between(W + d * 0.005, W + d * 0.100, 1.05, 0.045, 0.0150, hint=fw, off=-n * 0.001), f"hand_{t}", k=0.012, T=0.006, name=f"palm_{t}")
        D.add(ellipsoid_between(W + d * 0.010 + fw * 0.030 + n * 0.008, W + d * 0.052 + fw * 0.030 + n * 0.008, 1.0, 0.021, 0.0165, hint=fw), f"hand_{t}", k=0.01, T=0.006, name=f"thenar_{t}")
        D.add(ellipsoid_between(W + d * 0.015 - fw * 0.030 + n * 0.006, W + d * 0.075 - fw * 0.030 + n * 0.006, 1.0, 0.014, 0.0125, hint=fw), f"hand_{t}", k=0.01, T=0.006, name=f"hypothenar_{t}")
        D.add(Sphere(W, 0.0225), f"hand_{t}", k=0.01, T=0.006, name=f"wrist_{t}")
        D.add(ellipsoid_between(W - d * 0.005 - fw * 0.0, W + d * 0.030, 1.0, 0.0245, 0.0175, hint=fw), f"hand_{t}", k=0.01, T=0.006, name=f"wrist_block_{t}")

        fingers = [  # name, fw offset, spread deg (toward thumb +), lens, radii, curls (flexion deg toward palm)
            ("index", 0.0300, 5.0, (0.0425, 0.0240, 0.0200), (0.0102, 0.0094, 0.0086, 0.0072), (20, 30, 14)),
            ("middle", 0.0105, 0.0, (0.0465, 0.0285, 0.0225), (0.0104, 0.0096, 0.0088, 0.0074), (24, 34, 16)),
            ("ring", -0.0095, -4.0, (0.0430, 0.0265, 0.0210), (0.0098, 0.0090, 0.0083, 0.0070), (28, 38, 18)),
            ("pinky", -0.0275, -9.0, (0.0345, 0.0195, 0.0185), (0.0090, 0.0080, 0.0074, 0.0064), (32, 40, 20)),
        ]
        for nm, off, spread, lens, radii, curls in fingers:
            pos = K0 + fw * off - d * (0.006 if nm in ("ring", "pinky") else 0.0)
            dd = curl(d, fw, spread)
            prev = f"hand_{t}"
            for i, ln in enumerate(lens):
                dd = curl(dd, n, curls[i])
                end = pos + dd * ln
                bn = f"f_{nm}_{i + 1}_{t}"
                D.bone(bn, prev, pos, end)
                D.add(RoundCone(pos, end, radii[i], radii[i + 1]), bn, k=(0.0045 if i == 0 else 0.0), T=0.0035, name=bn)
                prev, pos = bn, end
            # fingertip pad
            D.add(Sphere(pos - dd * 0.0035 + n * 0.0020, radii[3] * 1.0), f"f_{nm}_3_{t}", k=0.0, T=0.003, name=f"pad_{nm}_{t}")
        # thumb (3 bones: metacarpal, proximal, distal)
        pos = W + d * 0.018 + fw * 0.026 + n * 0.007
        dd = curl(curl(d, fw, 38.0), n, 14.0)
        prev = f"hand_{t}"
        for i, (ln, r0, r1, cv) in enumerate([(0.046, 0.0125, 0.0112, 6.0), (0.0345, 0.0112, 0.0102, 10.0), (0.0290, 0.0102, 0.0088, 8.0)]):
            dd = curl(dd, n, cv)
            end = pos + dd * ln
            bn = f"f_thumb_{i + 1}_{t}"
            D.bone(bn, prev, pos, end)
            D.add(RoundCone(pos, end, r0, r1), bn, k=(0.006 if i == 0 else 0.0), T=0.0045, name=bn)
            prev, pos = bn, end
        D.add(Sphere(pos - dd * 0.003 + n * 0.0015, 0.0088), f"f_thumb_3_{t}", k=0.0, T=0.003, name=f"pad_thumb_{t}")

    # ================================================================================== legs & feet
    for s, t in SIDES:
        H = P(s * 0.088, 0.000, 0.975)
        K = P(s * 0.098, 0.020, 0.525)
        A = P(s * 0.100, 0.000, 0.082)
        B = P(s * 0.104, 0.168, 0.030)
        D.lm[f"hip_{t}"], D.lm[f"knee_{t}"], D.lm[f"ankle_{t}"], D.lm[f"ball_{t}"] = H, K, A, B
        D.bone(f"thigh_{t}", "pelvis", H, K)
        D.bone(f"shin_{t}", f"thigh_{t}", K, A)
        D.bone(f"foot_{t}", f"shin_{t}", A, B)
        # thigh
        D.add(RoundCone(H, K, 0.0950, 0.0600), f"thigh_{t}", k=0.04, T=0.014, name=f"thigh_{t}")
        D.add(Ellipsoid(P(s * 0.108, 0.034, 0.775), (0.054, 0.060, 0.185)), f"thigh_{t}", k=0.03, T=0.012, name=f"quad_{t}")
        D.add(Ellipsoid(P(s * 0.084, 0.050, 0.700), (0.028, 0.034, 0.120)), f"thigh_{t}", k=0.03, T=0.010, name=f"vastus_med_{t}")
        D.add(Ellipsoid(P(s * 0.136, 0.0, 0.800), (0.030, 0.042, 0.150)), f"thigh_{t}", k=0.04, T=0.012, name=f"vastus_lat_{t}")
        D.add(Ellipsoid(P(s * 0.098, -0.030, 0.790), (0.052, 0.047, 0.170)), f"thigh_{t}", k=0.03, T=0.012, name=f"hamstring_{t}")
        D.add(Ellipsoid(P(s * 0.056, 0.004, 0.870), (0.036, 0.050, 0.135)), f"thigh_{t}", k=0.03, T=0.012, name=f"adductor_{t}")
        # knee, shin, calf
        D.add(Sphere(K, 0.0520), f"shin_{t}", k=0.02, T=0.010, name=f"knee_{t}")
        D.add(Ellipsoid(P(s * 0.098, 0.056, 0.532), (0.022, 0.014, 0.027)), f"shin_{t}", k=0.01, T=0.006, name=f"patella_{t}")
        D.add(RoundCone(K, A, 0.0530, 0.0345), f"shin_{t}", k=0.025, T=0.010, name=f"shin_{t}")
        D.add(Ellipsoid(P(s * 0.108, -0.026, 0.380), (0.034, 0.044, 0.110)), f"shin_{t}", k=0.025, T=0.010, name=f"calf_lat_{t}")
        D.add(Ellipsoid(P(s * 0.090, -0.026, 0.388), (0.031, 0.042, 0.105)), f"shin_{t}", k=0.025, T=0.010, name=f"calf_med_{t}")
        D.add(RoundCone(P(s * 0.099, 0.045, 0.500), P(s * 0.100, 0.031, 0.140), 0.0150, 0.0125), f"shin_{t}", k=0.012, T=0.006, name=f"tibia_crest_{t}")
        D.add(RoundCone(P(s * 0.100, -0.030, 0.230), P(s * 0.100, -0.040, 0.075), 0.0180, 0.0150), f"shin_{t}", k=0.01, T=0.006, name=f"achilles_{t}")
        D.add(Ellipsoid(P(s * 0.128, -0.008, 0.083), (0.0125, 0.017, 0.021)), f"foot_{t}", k=0.01, T=0.005, name=f"malleolus_lat_{t}")
        D.add(Ellipsoid(P(s * 0.073, 0.003, 0.090), (0.0120, 0.016, 0.021)), f"foot_{t}", k=0.01, T=0.005, name=f"malleolus_med_{t}")
        # foot: one lofted body (heel -> metatarsal heads), arch carved on the medial side
        st = [(-0.072, 0.0, 0.026, 0.014, 0.062), (-0.058, 0.0, 0.0315, 0.004, 0.078), (-0.030, 0.0, 0.0365, 0.001, 0.086),
              (0.000, 0.0, 0.0395, 0.003, 0.088), (0.040, 0.001, 0.0430, 0.006, 0.081), (0.080, 0.002, 0.0480, 0.005, 0.068),
              (0.120, 0.003, 0.0535, 0.002, 0.052), (0.145, 0.004, 0.0565, 0.000, 0.040), (0.166, 0.004, 0.0540, 0.001, 0.029)]
        st = [(f, s * (0.100 + xo * 0.0), w, zb, zt) for f, xo, w, zb, zt in st]
        D.add(Loft(st), f"foot_{t}", k=0.012, T=0.007, name=f"foot_body_{t}")
        D.sub(Ellipsoid(P(s * 0.080, 0.060, -0.006), (0.020, 0.050, 0.020)), k=0.02, name=f"arch_{t}")
        D.sub(Ellipsoid(P(s * 0.100, 0.0, -0.040), (0.30, 0.50, 0.04)), k=0.0, name=f"ground_{t}")   # flat sole at z=0
        # toes: hallux (2 bones) + four lesser toes (1 bone each)
        toes = [("hallux", 0.0625, 0.0145, 0.0130, (0.0330, 0.0270), 2.0),
                ("toe2", 0.0880, 0.0098, 0.0085, (0.0480,), 1.0), ("toe3", 0.1058, 0.0092, 0.0080, (0.0440,), 0.5),
                ("toe4", 0.1215, 0.0085, 0.0074, (0.0400,), -1.0), ("toe5", 0.1350, 0.0078, 0.0066, (0.0340,), -3.0)]
        for nm, xo, r0, r1, lens, yaw in toes:
            pos = P(s * xo, 0.160, r0 + 0.001)
            dd = unit(np.array([s * np.sin(np.radians(yaw)) * 0.3, -1.0, 0.0]))
            prev = f"foot_{t}"
            for i, ln in enumerate(lens):
                bn = f"{nm}_{i + 1}_{t}"
                end = pos + dd * ln
                D.bone(bn, prev, pos, end)
                D.add(RoundCone(pos, end, r0 if i == 0 else r1, r1 if i == 0 else r1 * 0.88), bn, k=(0.003 if i == 0 else 0.0), T=0.004, name=bn)
                prev, pos = bn, end

    # ================================================================================== secondary / prop bones
    # hair chains (back hair), side locks; weights are assigned to hair cards only
    for nm, x, f in (("hair_back_L", 0.040, -0.085), ("hair_back_M", 0.0, -0.100), ("hair_back_R", -0.040, -0.085)):
        D.bone(f"{nm}_1", "head", P(x, f, 1.900), P(x, f - 0.005, 1.810), deform=True)
        D.bone(f"{nm}_2", f"{nm}_1", P(x, f - 0.005, 1.810), P(x, f - 0.012, 1.690), deform=True)
    for s, t in SIDES:
        D.bone(f"hair_side_{t}", "head", P(s * 0.070, 0.010, 1.900), P(s * 0.078, 0.005, 1.790), deform=True)
    # beard chains follow the jaw
    D.bone("beard_C_1", "jaw", P(0, 0.062, 1.752), P(0, 0.075, 1.668))
    D.bone("beard_C_2", "beard_C_1", P(0, 0.075, 1.668), P(0, 0.092, 1.565))
    for s, t in SIDES:
        D.bone(f"beard_{t}_1", "jaw", P(s * 0.042, 0.030, 1.768), P(s * 0.050, 0.042, 1.690))
    # maro cloth tails
    D.bone("cloth_front_1", "pelvis", P(0, 0.095, 1.045), P(0, 0.102, 0.960))
    D.bone("cloth_front_2", "cloth_front_1", P(0, 0.102, 0.960), P(0, 0.105, 0.870))
    D.bone("cloth_back_1", "pelvis", P(0, -0.105, 1.040), P(0, -0.110, 0.950))
    D.bone("cloth_back_2", "cloth_back_1", P(0, -0.110, 0.950), P(0, -0.112, 0.860))
    D.bone("cloth_knot_1", "pelvis", P(0.150, 0.030, 1.050), P(0.158, 0.034, 0.960))
    D.bone("cloth_knot_2", "cloth_knot_1", P(0.158, 0.034, 0.960), P(0.162, 0.036, 0.875))
    # free prop bones (animated per clip so props follow the animation exactly)
    D.bone("prop_staff", "root", P(0.0, 0.30, 0.90), P(0.0, 0.30, 1.00), deform=False)
    D.bone("prop_aux", "root", P(0.0, 0.40, 0.50), P(0.0, 0.40, 0.60), deform=False)
    return D
