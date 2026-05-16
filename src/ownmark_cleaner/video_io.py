from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2


@dataclass(frozen=True)
class VideoInfo:
    width: int
    height: int
    fps: float
    total_frames: int


def check_ffmpeg() -> None:
    """Exit early if FFmpeg is not available in PATH."""
    if shutil.which("ffmpeg") is None:
        print("Error: FFmpeg not found. Install FFmpeg and make sure it is in PATH.")
        sys.exit(1)


def open_video(path: Path | str) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {path}")
    return cap


def get_video_info(cap: cv2.VideoCapture) -> VideoInfo:
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps or fps <= 0:
        fps = 25.0

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if width <= 0 or height <= 0:
        raise RuntimeError("Invalid video dimensions.")

    return VideoInfo(width=width, height=height, fps=fps, total_frames=total_frames)


def build_ffmpeg_rawvideo_cmd(
    *,
    width: int,
    height: int,
    fps: float,
    input_path: Path,
    output_path: Path,
    crf: int,
    preset: str,
    audio: str,
) -> list[str]:
    """Build FFmpeg command that reads raw BGR frames from stdin."""
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "rawvideo",
        "-vcodec",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-s",
        f"{width}x{height}",
        "-r",
        f"{fps:.6f}",
        "-i",
        "-",
    ]

    if audio != "none":
        cmd += ["-i", str(input_path)]

    cmd += ["-map", "0:v:0"]

    if audio != "none":
        cmd += ["-map", "1:a?"]

    cmd += [
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-crf",
        str(crf),
        "-pix_fmt",
        "yuv420p",
    ]

    if audio == "copy":
        cmd += ["-c:a", "copy"]
    elif audio == "aac":
        cmd += ["-c:a", "aac", "-b:a", "192k"]

    cmd += ["-shortest", str(output_path)]
    return cmd


def start_ffmpeg_pipe(cmd: list[str]) -> subprocess.Popen:
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)
