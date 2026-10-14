"""Secondary motion for the hair / beard / maro chains: damped springs driven by the primary solved poses (baked into the clips)."""
import numpy as np

from kin import unit
from pose_lib import RIG

CHAINS = {
    # name: (bones in order, omega, zeta, gravity blend, kind)
    "hair_back_L": (["hair_back_L_1", "hair_back_L_2"], 13.0, 0.55, 0.55, "hair"),
    "hair_back_M": (["hair_back_M_1", "hair_back_M_2"], 12.0, 0.55, 0.55, "hair"),
    "hair_back_R": (["hair_back_R_1", "hair_back_R_2"], 13.0, 0.55, 0.55, "hair"),
    "hair_side_L": (["hair_side_L"], 14.0, 0.55, 0.50, "hair"),
    "hair_side_R": (["hair_side_R"], 14.0, 0.55, 0.50, "hair"),
    "beard_C": (["beard_C_1", "beard_C_2"], 12.0, 0.60, 0.55, "beard"),
    "beard_L": (["beard_L_1"], 14.0, 0.60, 0.40, "beard"),
    "beard_R": (["beard_R_1"], 14.0, 0.60, 0.40, "beard"),
    "cloth_front": (["cloth_front_1", "cloth_front_2"], 10.0, 0.62, 0.75, "cloth_front"),
    "cloth_back": (["cloth_back_1", "cloth_back_2"], 10.0, 0.62, 0.75, "cloth_back"),
    "cloth_knot": (["cloth_knot_1", "cloth_knot_2"], 9.0, 0.55, 0.80, "cloth_knot"),
}


def _align(a, b):
    """Minimal rotation taking unit a to unit b."""
    v = np.cross(a, b)
    c = float(a @ b)
    if c < -0.999999:
        ax = unit(np.cross(a, [1, 0, 0]) if abs(a[0]) < 0.9 else np.cross(a, [0, 1, 0]))
        return 2 * np.outer(ax, ax) - np.eye(3)
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + vx @ vx / (1.0 + c)


def simulate(sols, loop, fps=30, floor=0.012):
    """sols: list of Solved (one per frame). Returns list of dict bone -> 3x3 delta for the secondary bones."""
    sk = RIG.sk
    n = len(sols)
    out = [dict() for _ in range(n)]
    dt = 1.0 / fps
    sub = 4
    for cname, (bones, omega, zeta, gblend, kind) in CHAINS.items():
        if bones[0] not in sk.idx:
            continue
        # per-frame parent frames and rest tips
        state = {}
        reps = 3 if loop else 1
        seqs = {}
        for rep in range(reps):
            for f in range(n):
                sol = sols[f]
                prev_tip_frame = None
                Qp_cur = None
                for bi, bn in enumerate(bones):
                    i = sk.i(bn)
                    par = sk.parent[i]
                    if bi == 0:
                        Qp = sol.Q[par]
                        H = sol.Hw[i]
                    else:
                        Qp = Qp_cur
                        H = Hcur
                    L = sk.length[i]
                    a_rest = sk.axis_rest[i]
                    a_world = Qp @ a_rest
                    T_follow = H + a_world * L
                    T_down = H + np.array([0, 0, -1.0]) * L
                    T = (1 - gblend) * T_follow + gblend * T_down
                    # extra drives for the cloth flaps: legs pushing forward / back
                    if kind.startswith("cloth"):
                        push = np.zeros(3)
                        thL = sol.Rw[sk.i("thigh_L")][:, 1]
                        thR = sol.Rw[sk.i("thigh_R")][:, 1]
                        fwdL, fwdR = -thL[1], -thR[1]           # forward component of the thigh axis (pointing down = 0)
                        fl_f = max(0.0, max(fwdL, fwdR)) if False else max(0.0, max(fwdL, fwdR) + 0.0)
                        # the axis points from hip to knee; hip flexion lifts the knee forward -> axis y becomes negative
                        up_front = max(0.0, max(-thL[1], -thR[1]))
                        up_back = max(0.0, max(thL[1], thR[1]))
                        if kind == "cloth_front":
                            push = np.array([0, -1.0, 0.45]) * up_front * L * 1.1
                        elif kind == "cloth_back":
                            push = np.array([0, 1.0, 0.45]) * up_back * L * 1.1
                        else:
                            push = np.array([1.0, 0, 0.3]) * (up_front + up_back) * L * 0.3
                        T = T + push
                    key = (cname, bn)
                    if key not in state:
                        state[key] = [T.copy(), np.zeros(3)]
                    x, v = state[key]
                    h = dt / sub
                    for _ in range(sub):
                        acc = -omega ** 2 * (x - T) - 2 * zeta * omega * v
                        v = v + acc * h
                        x = x + v * h
                    if x[2] < floor:                        # the floor: hair and cloth lie on it instead of sinking through
                        x = np.array([x[0], x[1], floor])
                        v = np.array([v[0], v[1], max(v[2], 0.0)])
                    # keep the segment length (pendulum constraint)
                    d = x - H
                    nd = np.linalg.norm(d)
                    x = H + d / max(nd, 1e-9) * L
                    state[key] = [x, v]
                    d_new = unit(x - H)
                    Ral = _align(unit(a_world), d_new)
                    Qb = Ral @ Qp
                    D = Qp.T @ Qb
                    if rep == reps - 1:
                        out[f][bn] = D
                    Qp_cur = Qb
                    Hcur = H + d_new * L
    return out
