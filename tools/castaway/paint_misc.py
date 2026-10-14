"""Small procedural textures: human eye, mouth parts, loincloth weave, wood."""
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "monkey"))
from paint_textures import mix, smoothstep  # noqa: E402


def eye_texture(path, size=512):
    """Equirect: u = angle around the gaze axis, v = angle from the gaze pole (0 = pupil centre)."""
    rng = np.random.default_rng(11)
    u = (np.arange(size) + 0.5) / size
    v = (np.arange(size // 2) + 0.5) / (size // 2)
    U, Vv = np.meshgrid(u, v)
    theta = Vv * np.pi
    phi = U * 2 * np.pi
    iris_r = 29.5 / 180 * np.pi
    pupil_r = 10.5 / 180 * np.pi
    pupil = 1 - smoothstep(pupil_r - 0.012, pupil_r + 0.010, theta)
    iris = 1 - smoothstep(iris_r - 0.010, iris_r + 0.008, theta)
    limbus = smoothstep(iris_r - 0.060, iris_r - 0.004, theta) * (1 - smoothstep(iris_r, iris_r + 0.030, theta))
    fib = rng.random(size)
    fib = np.convolve(np.tile(fib, 3), np.ones(3) / 3, mode="same")[size:2 * size]
    fibres = fib[(U * size).astype(int) % size]
    fibres2 = rng.random(size)[(U * size / 5).astype(int) % size]
    spokes = 0.55 * fibres + 0.45 * fibres2
    rad = np.clip((theta - pupil_r) / (iris_r - pupil_r), 0, 1)
    inner = np.array([0.58, 0.46, 0.24])        # hazel ring around the pupil
    outer = np.array([0.30, 0.46, 0.55])        # grey-blue
    iris_col = mix(inner, outer, np.clip(rad * 1.6 - 0.15 + (spokes - 0.5) * 0.5, 0, 1))
    iris_col = iris_col * (0.8 + 0.4 * spokes[..., None]) * (1.0 - 0.35 * smoothstep(0.75, 1.0, rad))[..., None]
    collarette = np.exp(-((rad - 0.34) / 0.07) ** 2)[..., None] * np.array([0.22, 0.15, 0.05])
    iris_col = np.clip(iris_col + collarette * 0.4, 0, 1)
    # sclera: warm white, a little reddened and shaded towards the lids; fine vessels
    sclera = mix(np.array([0.84, 0.80, 0.74]), np.array([0.66, 0.50, 0.44]), smoothstep(0.30 * np.pi, 0.72 * np.pi, theta))
    vessel = (rng.random((size // 2, size)) > 0.9985).astype(float)
    sclera = sclera - 0.0 * vessel[..., None]
    col = mix(sclera, iris_col, iris)
    col = mix(col, np.array([0.06, 0.05, 0.05]), limbus * 0.75)
    col = mix(col, np.array([0.008, 0.008, 0.008]), pupil)
    Image.fromarray((np.clip(col, 0, 1) * 255 + 0.5).astype(np.uint8)).save(path)
    print(f"[misc] eye texture {size}x{size // 2} -> {path}")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "build/castaway/tex"
    os.makedirs(out, exist_ok=True)
    eye_texture(os.path.join(out, "eye_albedo.png"))
