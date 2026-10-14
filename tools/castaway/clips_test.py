import numpy as np
import clipkit as CK
import params as PR
from clipkit import clip, keys, smooth


@clip("test_pose", group="test", seconds=2.0, loop=True, desc="pipeline test")
def test_pose(t):
    p = PR.base()
    ph = t / 2.0
    s = np.sin(ph * 2 * np.pi)
    p = PR.update(p, sp=[10 * s, 0, 8 * s], hd=[0, 0, 25 * s], armL=[60 * (0.5 + 0.5 * s), 20, 0, 60 * (0.5 + 0.5 * s), 0, 0],
                  armR=[-30 * s, 10, 0, 20, 0, 0], pel=[0, 0, -0.05 * (0.5 + 0.5 * s), 0, 0, 0])
    p["face"][0] = 15 * (0.5 + 0.5 * s)
    p["face"][11] = 1.0 if s > 0.9 else 0.0
    p["face"][12] = 1.0 if s > 0.9 else 0.0
    return p, dict(arm_mode=("fk", "fk"))
