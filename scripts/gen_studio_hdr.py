#!/usr/bin/env python3
"""Generate a small studio Radiance HDR (.hdr) for LumenCore demos."""
from __future__ import print_function

import math
import struct
import sys
from pathlib import Path


def float_to_rgbe(r, g, b):
    v = max(r, g, b)
    if v < 1e-32:
        return (0, 0, 0, 0)
    e = int(math.floor(math.log(v, 2.0))) + 1
    f = math.ldexp(1.0, e - 8)
    return (
        int(min(255, max(0, int(r / f)))),
        int(min(255, max(0, int(g / f)))),
        int(min(255, max(0, int(b / f)))),
        e + 128,
    )


def rle_channel(plane):
    """Radiance new-RLE for one byte plane."""
    out = bytearray()
    n = len(plane)
    i = 0
    while i < n:
        # Find run length
        run = 1
        while i + run < n and plane[i + run] == plane[i] and run < 127:
            run += 1
        if run >= 4:
            out.append(128 + run)
            out.append(plane[i])
            i += run
            continue
        # Non-run dump: extend until a long run or 128 bytes
        j = i
        while j < n and (j - i) < 128:
            run2 = 1
            while j + run2 < n and plane[j + run2] == plane[j] and run2 < 4:
                run2 += 1
            if run2 >= 4:
                break
            j += 1
        dump = j - i
        if dump == 0:
            dump = 1
        out.append(dump)
        out.extend(plane[i : i + dump])
        i += dump
    return out


def write_hdr(path, width, height, pixels):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        f.write(b"#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n")
        f.write(("-Y %d +X %d\n" % (height, width)).encode("ascii"))
        for y in range(height):
            f.write(struct.pack("BBBB", 2, 2, (width >> 8) & 255, width & 255))
            rgbe = [float_to_rgbe(*pixels[y * width + x]) for x in range(width)]
            for c in range(4):
                plane = [rgbe[x][c] for x in range(width)]
                f.write(rle_channel(plane))


def gen_studio(width=512, height=256):
    pixels = []
    for y in range(height):
        v = (y + 0.5) / float(height)
        theta = v * math.pi
        for x in range(width):
            u = (x + 0.5) / float(width)
            phi = (u - 0.5) * 2.0 * math.pi
            sy = math.cos(theta)
            sky = 0.12 + 0.5 * max(sy, 0.0) ** 0.85
            window = 0.0
            if sy > 0.12 and abs(phi) < 0.6:
                window = 22.0 * max(0.0, 1.0 - abs(phi) / 0.6) * max(0.0, (sy - 0.12) / 0.88)
            ground = 0.06 * max(-sy, 0.0)
            r = sky * 0.9 + window * 1.1 + ground * 1.15
            g = sky * 0.95 + window * 1.0 + ground * 0.85
            b = sky * 1.1 + window * 0.95 + ground * 0.55
            pixels.append((r, g, b))
    return pixels


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "assets/env/studio.hdr"
    w, h = 512, 256
    write_hdr(out, w, h, gen_studio(w, h))
    print("Wrote", out, "%dx%d" % (w, h))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
