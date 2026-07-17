#!/usr/bin/env python3
"""Generate Radiance HDR (.hdr) env maps for LumenCore demos."""
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
        run = 1
        while i + run < n and plane[i + run] == plane[i] and run < 127:
            run += 1
        if run >= 4:
            out.append(128 + run)
            out.append(plane[i])
            i += run
            continue
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


def gen_dusk(width=512, height=256):
    """Low-angle sunset: cool purple-blue zenith, warm horizon band, dim ground."""
    pixels = []
    # Sun near horizon toward +X (phi ~ 0)
    sun_phi = 0.15
    sun_sy = 0.08
    for y in range(height):
        v = (y + 0.5) / float(height)
        theta = v * math.pi
        for x in range(width):
            u = (x + 0.5) / float(width)
            phi = (u - 0.5) * 2.0 * math.pi
            sy = math.cos(theta)
            # Zenith cool, horizon warm
            elev = max(sy, 0.0)
            horizon = math.exp(-((sy - 0.05) ** 2) / 0.04)
            sky_r = 0.04 + 0.08 * elev + 0.55 * horizon
            sky_g = 0.05 + 0.12 * elev + 0.22 * horizon
            sky_b = 0.12 + 0.35 * elev + 0.08 * horizon
            # Soft sun disk
            dphi = abs(((phi - sun_phi + math.pi) % (2.0 * math.pi)) - math.pi)
            dsy = abs(sy - sun_sy)
            sun = math.exp(-(dphi * dphi) / 0.08 - (dsy * dsy) / 0.012)
            sun_boost = sun * 48.0
            ground = 0.03 * max(-sy, 0.0)
            r = sky_r + sun_boost * 1.2 + ground * 0.9
            g = sky_g + sun_boost * 0.55 + ground * 0.7
            b = sky_b + sun_boost * 0.18 + ground * 0.5
            pixels.append((r, g, b))
    return pixels


def gen_noon_factory(width=512, height=256):
    """Bright overhead skylight for factory noon (importance-sample friendly)."""
    pixels = []
    for y in range(height):
        v = (y + 0.5) / float(height)
        theta = v * math.pi
        for x in range(width):
            u = (x + 0.5) / float(width)
            phi = (u - 0.5) * 2.0 * math.pi
            sy = math.cos(theta)
            elev = max(sy, 0.0)
            # Bright zenith + soft sun near overhead
            sky = 0.35 + 1.8 * (elev ** 0.65)
            sun = 0.0
            if sy > 0.55:
                sun = 55.0 * ((sy - 0.55) / 0.45) ** 2
            # Mild warm windows on sides
            window = 0.0
            if sy > 0.2 and abs(abs(phi) - 1.2) < 0.35:
                window = 8.0 * max(0.0, 1.0 - abs(abs(phi) - 1.2) / 0.35)
            ground = 0.12 * max(-sy, 0.0)
            r = sky * 1.05 + sun * 1.15 + window * 1.05 + ground * 1.1
            g = sky * 1.05 + sun * 1.05 + window * 1.0 + ground * 1.0
            b = sky * 1.15 + sun * 0.95 + window * 0.95 + ground * 0.75
            pixels.append((r, g, b))
    return pixels


GENERATORS = {
    "studio": ("assets/env/studio.hdr", gen_studio),
    "dusk": ("assets/env/dusk.hdr", gen_dusk),
    "noon": ("assets/env/noon_factory.hdr", gen_noon_factory),
}


def main():
    mode = "studio"
    out = None
    args = sys.argv[1:]
    if args and args[0] in GENERATORS:
        mode = args[0]
        args = args[1:]
    if args:
        out = args[0]
    default_out, gen = GENERATORS[mode]
    out = out or default_out
    w, h = 512, 256
    write_hdr(out, w, h, gen(w, h))
    print("Wrote", out, "%dx%d (%s)" % (w, h, mode))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
