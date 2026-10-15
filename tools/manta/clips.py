"""
Giant manta ray animation clips, as pure functions of time (no Blender needed).

Each clip is (duration_s, loop, fn). fn(t) returns {bone: (rx, ry, rz)} in radians, Euler XYZ in the bone's rest frame.
Rest-frame convention (verified by probe in build_manta.py):
  wing bones (along +/-Y): local X is flap, +angle = wing tip up on BOTH sides
  body and lobes (along +X): local X is pitch (+ = nose up), local Y is the bone axis (roll), local Z is yaw
  tail bones (along -X): local X is up/down bend (+ = tip up), local Z is sideways sway

Loop clips are periodic in their duration, so the exporter can add one repeated key at the end for a seamless loop.
"""
import math

WING_BONES = [("wing_L1", "wing_R1"), ("wing_L2", "wing_R2"), ("wing_L3", "wing_R3")]
TAIL_BONES = ["tail1", "tail2", "tail3"]
ALL_BONES = ["root", "body", "head_L", "head_R", "wing_L1", "wing_L2", "wing_L3", "wing_R1", "wing_R2", "wing_R3",
             "tail1", "tail2", "tail3"]


def _rest():
    return {b: (0.0, 0.0, 0.0) for b in ALL_BONES}


def _ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def _wave_wings(pose, phase, amp, lag=0.6, amp_gain=(1.0, 1.15, 0.9)):
    """Travelling wave along each wing: the root leads, the tip lags and has its own amplitude."""
    for i, (l, r) in enumerate(WING_BONES):
        a = amp * amp_gain[i]
        v = a * math.sin(phase - lag * i)
        pose[l] = (v, 0.0, 0.0)
        pose[r] = (v, 0.0, 0.0)


def _tail_wave(pose, phase, sway, bend=0.0):
    for i, b in enumerate(TAIL_BONES):
        pose[b] = (bend * math.sin(phase - 0.5 * i), 0.0, sway * math.sin(phase - 0.6 * i))


def _periodic(duration):
    return 2.0 * math.pi / duration


# --- loops ---------------------------------------------------------------------

def glide_cruise(t, T=2.4):
    p = _periodic(T) * t
    pose = _rest()
    _wave_wings(pose, p, amp=0.20)
    pose["body"] = (0.02 * math.sin(p), 0.0, 0.0)
    _tail_wave(pose, p, sway=0.12, bend=0.04)
    return pose


def glide_gentle(t, T=5.0):
    p = _periodic(T) * t
    pose = _rest()
    _wave_wings(pose, p, amp=0.07, lag=0.5)
    pose["body"] = (0.01 * math.sin(p), 0.0, 0.0)
    _tail_wave(pose, p, sway=0.06, bend=0.02)
    return pose


def flap_power(t, T=1.1):
    p = _periodic(T) * t
    pose = _rest()
    _wave_wings(pose, p, amp=0.55, lag=0.5)
    pose["body"] = (0.05 * math.sin(2 * p), 0.0, 0.0)
    _tail_wave(pose, p, sway=0.20, bend=0.10)
    return pose


def feed_open(t, T=5.0):
    """Scooping: the lobes unroll forward and out, the wings cup up, the disc tilts nose-up slightly."""
    p = _periodic(T) * t
    pose = _rest()
    lobe_out = 0.30 + 0.08 * math.sin(p)
    pose["head_L"] = (0.10, 0.0, lobe_out)
    pose["head_R"] = (0.10, 0.0, -lobe_out)
    _wave_wings(pose, p, amp=0.12, lag=0.4)
    for l, r in WING_BONES:
        pose[l] = (pose[l][0] + 0.18, 0.0, 0.0)
        pose[r] = (pose[r][0] + 0.18, 0.0, 0.0)
    pose["body"] = (0.10 + 0.02 * math.sin(p), 0.0, 0.0)
    _tail_wave(pose, p, sway=0.10, bend=0.03)
    return pose


def curious_approach(t, T=4.0):
    """Head up, lobes curling and uncurling, slow wing ripple: the 'I see you' posture."""
    p = _periodic(T) * t
    pose = _rest()
    _wave_wings(pose, p, amp=0.10, lag=0.5)
    pose["body"] = (0.07, 0.0, 0.0)
    pose["head_L"] = (0.25 * math.sin(p), 0.0, 0.10)
    pose["head_R"] = (0.25 * math.sin(p), 0.0, -0.10)
    _tail_wave(pose, p, sway=0.08, bend=0.02)
    return pose


def _clip_once(t, T, build):
    pose = _rest()
    build(pose, t / T)
    return pose


# --- one-shots -------------------------------------------------------------------

def turn_left(t, T=2.4):
    """Bank into a left turn: roll the disc, the outer (right) wing lifts, the inner (left) wing dips."""
    def build(pose, u):
        bank = 0.24 * math.sin(math.pi * _ease(u))
        pose["body"] = (0.0, bank, 0.0)
        _wave_wings(pose, 2 * math.pi * u, amp=0.12, lag=0.5)
        for i, (l, r) in enumerate(WING_BONES):
            pose[l] = (pose[l][0] - 0.10 * math.sin(math.pi * _ease(u)), 0.0, 0.0)
            pose[r] = (pose[r][0] + 0.10 * math.sin(math.pi * _ease(u)), 0.0, 0.0)
    return _clip_once(t, T, build)


def turn_right(t, T=2.4):
    def build(pose, u):
        bank = -0.24 * math.sin(math.pi * _ease(u))
        pose["body"] = (0.0, bank, 0.0)
        _wave_wings(pose, 2 * math.pi * u, amp=0.12, lag=0.5)
        for i, (l, r) in enumerate(WING_BONES):
            pose[l] = (pose[l][0] + 0.10 * math.sin(math.pi * _ease(u)), 0.0, 0.0)
            pose[r] = (pose[r][0] - 0.10 * math.sin(math.pi * _ease(u)), 0.0, 0.0)
    return _clip_once(t, T, build)


def startle_burst(t, T=1.2):
    """Sudden: wings snap up, the tail whips, the lobes fold back, then settle into a fast flap."""
    def build(pose, u):
        snap = _ease(min(u / 0.25, 1.0)) * (1.0 - _ease(max((u - 0.6) / 0.4, 0.0)))
        for l, r in WING_BONES:
            pose[l] = (0.75 * snap, 0.0, 0.0)
            pose[r] = (0.75 * snap, 0.0, 0.0)
        pose["head_L"] = (-0.30 * snap, 0.0, 0.0)
        pose["head_R"] = (-0.30 * snap, 0.0, 0.0)
        whip = math.sin(2 * math.pi * 1.4 * u) * (1.0 - u)
        for i, b in enumerate(TAIL_BONES):
            pose[b] = (0.15 * whip, 0.0, 0.35 * whip * (1.0 - 0.2 * i))
        pose["body"] = (-0.08 * snap, 0.0, 0.0)
    return _clip_once(t, T, build)


def breach_rise(t, T=3.0):
    """Leap: the disc rises nose-first out of the water, wings spread and cup up, tail trails."""
    def build(pose, u):
        lift = _ease(min(u / 0.45, 1.0))
        pose["body"] = (0.55 * lift, 0.0, 0.0)  # positive local X pitches the nose up
        for l, r in WING_BONES:
            pose[l] = (0.45 * lift, 0.0, 0.0)
            pose[r] = (0.45 * lift, 0.0, 0.0)
        pose["head_L"] = (0.0, 0.0, 0.25 * lift)
        pose["head_R"] = (0.0, 0.0, -0.25 * lift)
        for i, b in enumerate(TAIL_BONES):
            pose[b] = (-0.12 * lift, 0.0, 0.0)
    return _clip_once(t, T, build)


def breach_fall(t, T=2.5):
    """Re-entry: the disc drops back, wings flutter open, then returns to a glide pose."""
    def build(pose, u):
        drop = 1.0 - _ease(min(u / 0.6, 1.0))
        pose["body"] = (0.55 * drop - 0.05 * (1 - drop), 0.0, 0.0)
        for l, r in WING_BONES:
            v = 0.45 * drop + 0.08 * math.sin(2 * math.pi * 2.0 * u) * (1 - u)
            pose[l] = (v, 0.0, 0.0)
            pose[r] = (v, 0.0, 0.0)
        pose["head_L"] = (0.0, 0.0, 0.25 * drop)
        pose["head_R"] = (0.0, 0.0, -0.25 * drop)
    return _clip_once(t, T, build)


CLIPS = {
    "glide_cruise": (2.4, True, glide_cruise),
    "glide_gentle": (5.0, True, glide_gentle),
    "flap_power": (1.1, True, flap_power),
    "feed_open": (5.0, True, feed_open),
    "curious_approach": (4.0, True, curious_approach),
    "turn_left": (2.4, False, turn_left),
    "turn_right": (2.4, False, turn_right),
    "startle_burst": (1.2, False, startle_burst),
    "breach_rise": (3.0, False, breach_rise),
    "breach_fall": (2.5, False, breach_fall),
}
