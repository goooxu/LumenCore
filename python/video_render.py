"""Frame-sequence helpers and HDR AV1 encode via ffmpeg.

Renders stay as per-frame HDR AVIF (PQ / BT.2020). The muxed video keeps HDR
transfer metadata — no SDR tonemap.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Callable, Optional, Sequence


def render_frames(
    render_fn: Callable[[int, Path], None],
    frames_dir: Path | str,
    frame_count: int,
    *,
    start: int = 0,
    pattern: str = "frame_{:04d}.avif",
) -> list[Path]:
    """Call ``render_fn(frame_index, output_path)`` for each frame."""
    frames_dir = Path(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i in range(start, start + frame_count):
        out = frames_dir / pattern.format(i)
        render_fn(i, out)
        if not out.is_file():
            raise RuntimeError(f"render_fn did not write {out}")
        paths.append(out)
    return paths


def _find_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise RuntimeError(
            "ffmpeg not found on PATH; install ffmpeg (e.g. apt install ffmpeg) "
            "or rebuild the LumenCore docker image (lumencore-build:cuda13-avif-ffmpeg)."
        )
    return path


def _pick_av1_encoder(ffmpeg: str, preferred: Optional[str] = None) -> str:
    if preferred:
        return preferred
    try:
        proc = subprocess.run(
            [ffmpeg, "-hide_banner", "-encoders"],
            check=True,
            capture_output=True,
            text=True,
        )
        text = proc.stdout
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"ffmpeg -encoders failed: {exc}") from exc

    for name in ("libaom-av1", "libsvtav1", "librav1e"):
        # Encoder lines look like: " V..... libaom-av1             ..."
        if f" {name}" in text:
            return name
    raise RuntimeError(
        "No AV1 encoder found in ffmpeg (tried libaom-av1, libsvtav1, librav1e). "
        "Install ffmpeg with AV1 support."
    )


def _printf_frame_path(pattern: str, index: int) -> str:
    """Format an ffmpeg-style ``frame_%04d.avif`` pattern for one index."""
    try:
        return pattern % index
    except TypeError as exc:
        raise ValueError(
            f"pattern must be printf-style with one int field (got {pattern!r})"
        ) from exc


def _write_concat_list(
    frames_dir: Path,
    pattern: str,
    start_number: int,
    frame_count: Optional[int],
    list_path: Path,
) -> int:
    """Write an ffconcat list. AVIF is a mov-like container; image2 ``%04d`` fails."""
    paths: list[Path] = []
    if frame_count is not None:
        for i in range(start_number, start_number + frame_count):
            paths.append(frames_dir / _printf_frame_path(pattern, i))
    else:
        i = start_number
        while True:
            p = frames_dir / _printf_frame_path(pattern, i)
            if not p.is_file():
                break
            paths.append(p)
            i += 1

    if not paths:
        raise FileNotFoundError(
            f"no frames matching {frames_dir / _printf_frame_path(pattern, start_number)}"
        )
    missing = [p for p in paths if not p.is_file()]
    if missing:
        raise FileNotFoundError(f"missing frames (first): {missing[0]}")

    # Absolute paths avoid cwd surprises inside Docker.
    lines = ["ffconcat version 1.0\n"]
    for p in paths:
        # concat demuxer requires single quotes escaped as '\''
        escaped = str(p.resolve()).replace("'", r"'\''")
        lines.append(f"file '{escaped}'\n")
    list_path.write_text("".join(lines), encoding="utf-8")
    return len(paths)


def encode_hdr_av1(
    frames_dir: Path | str,
    output_path: Path | str,
    *,
    fps: float = 24.0,
    pattern: str = "frame_%04d.avif",
    crf: int = 22,
    encoder: Optional[str] = None,
    start_number: int = 0,
    frame_count: Optional[int] = None,
    extra_args: Optional[Sequence[str]] = None,
) -> Path:
    """Mux an HDR AVIF image sequence into HDR AV1 inside an MKV container.

    Color metadata is set to BT.2020 + SMPTE 2084 (PQ) to match LumenCore stills.
    Uses the concat demuxer because stock ffmpeg cannot image2-glob ``.avif``.
    """
    frames_dir = Path(frames_dir)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    concat_list = frames_dir / "_hdr_av1_concat.txt"
    n = _write_concat_list(frames_dir, pattern, start_number, frame_count, concat_list)

    ffmpeg = _find_ffmpeg()
    enc = _pick_av1_encoder(ffmpeg, encoder)

    cmd = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "concat",
        "-safe",
        "0",
        "-r",
        str(fps),
        "-i",
        str(concat_list),
        "-frames:v",
        str(n),
        "-c:v",
        enc,
        "-pix_fmt",
        "yuv420p10le",
        "-crf",
        str(crf),
        "-b:v",
        "0",
        "-color_primaries",
        "bt2020",
        "-color_trc",
        "smpte2084",
        "-colorspace",
        "bt2020nc",
        "-color_range",
        "tv",
    ]
    if enc == "libaom-av1":
        cmd.extend(["-cpu-used", "6", "-row-mt", "1"])
    elif enc == "libsvtav1":
        cmd.extend(["-preset", "8"])
    if extra_args:
        cmd.extend(extra_args)
    cmd.append(str(output_path))

    print(f"[video] encode HDR AV1 ({enc}, {n} frames @ {fps:g} fps) → {output_path}", flush=True)
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "ffmpeg HDR AV1 encode failed. Ensure ffmpeg can decode AVIF and "
            f"encode with {enc}. Command: {' '.join(cmd)}"
        ) from exc
    finally:
        try:
            concat_list.unlink(missing_ok=True)
        except OSError:
            pass

    if not output_path.is_file():
        raise RuntimeError(f"ffmpeg did not write {output_path}")
    return output_path
