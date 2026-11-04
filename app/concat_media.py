# Adapted from 64johnlee/qwen-showrunner (MIT), Copyright (c) 2026 John Lee.
# Commit c91b03acc6e02b2fdc38e7d350e870ee809c258b.
# Changes: timeout, faststart, input-path validation, guaranteed cleanup.
from pathlib import Path
import subprocess

def _run(args):
    proc = subprocess.run(args, capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        raise RuntimeError("本地FFmpeg合成失败；原始视频保留，可只重试合成")

def concat_scenes(scenes: list[Path], dest: Path) -> Path:
    listing = dest.with_suffix(".concat.txt")
    paths = [p.resolve().as_posix() for p in scenes]
    if any("\x27" in p or "\n" in p for p in paths):
        raise ValueError("合成临时路径含不支持的字符")
    listing.write_text("".join("file \x27" + p + "\x27\n" for p in paths), encoding="utf-8")
    try:
        try:
            _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", "-movflags", "+faststart", str(dest)])
        except RuntimeError:
            _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart", str(dest)])
    finally:
        listing.unlink(missing_ok=True)
    return dest

