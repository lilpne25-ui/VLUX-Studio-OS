from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .db import FEATURE_NAMES
from .probe import probe


def _silence_segments(path: str | Path) -> list[dict]:
    """Best-effort FFmpeg silence detection; absence is unknown, never zero."""
    try:
        p = subprocess.run(
            ["ffmpeg", "-hide_banner", "-i", str(path), "-af", "silencedetect=noise=-35dB:d=1",
             "-f", "null", "-"],
            capture_output=True, text=True, timeout=90,
        )
        starts = [float(x) for x in re.findall(r"silence_start:\s*([0-9.]+)", p.stderr)]
        ends = [float(x) for x in re.findall(r"silence_end:\s*([0-9.]+)", p.stderr)]
        return [{"start_s": s, "end_s": e, "duration_s": max(0, e - s)}
                for s, e in zip(starts, ends)]
    except (OSError, subprocess.SubprocessError, ValueError):
        return []


def analyze(path: str | Path, sample_fps: float = 4.0) -> tuple[dict, dict, list[dict]]:
    meta = probe(path)
    objective = {k: meta.get(k) for k in
                 ("duration_s", "fps", "width", "height", "has_audio", "codec")}
    estimated: dict = {
        "interpretation": "Proxies are estimated descriptors, not aesthetic judgments.",
        "motion_quality_warning": "Motion is not equivalent to quality or narrative intent.",
    }
    observations: list[dict] = []
    try:
        import cv2
        cap = cv2.VideoCapture(str(path))
        fps = meta.get("fps") or 25.0
        step = max(1, int(fps / sample_fps))
        prev = None
        vals, samples, first_motion = [], [], []
        cuts, blacks, freezes = 0, 0, 0
        static_start = None
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            pos = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
            if pos % step:
                continue
            t = pos / fps
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            mean, std = float(gray.mean()), float(gray.std())
            vals.append((mean, std))
            diff = None if prev is None else float(cv2.absdiff(gray, prev).mean())
            samples.append({"time_s": round(t, 3), "brightness": mean, "contrast": std,
                            "motion": diff})
            if mean < 8:
                blacks += 1
            if diff is not None:
                if diff > 22:
                    cuts += 1
                if diff < 1.0:
                    freezes += 1
                    if static_start is None:
                        static_start = t - step / fps
                elif static_start is not None:
                    if t - static_start >= 1.0:
                        observations.append({
                            "start_s": round(max(0, static_start), 3), "end_s": round(t, 3),
                            "severity": "review", "category": "static_visual",
                            "message": "Tramo visualmente estático; puede ser correcto si comunica con claridad.",
                            "recommendation": "Comparar contra feedback humano antes de añadir movimiento.",
                        })
                    static_start = None
                if t <= 3.0:
                    first_motion.append(diff)
            prev = gray
        cap.release()
        n = max(1, len(vals))
        duration = meta.get("duration_s") or 0
        if static_start is not None and duration - static_start >= 1.0:
            observations.append({
                "start_s": round(max(0, static_start), 3), "end_s": round(duration, 3),
                "severity": "review", "category": "static_visual",
                "message": "Tramo visualmente estático; puede ser correcto si comunica con claridad.",
                "recommendation": "Comparar contra feedback humano antes de añadir movimiento.",
            })
        avg_shot = duration / max(1, cuts + 1)
        objective.update({
            "cut_count": cuts, "avg_shot_s": avg_shot,
            "motion_mean": sum(x for x in first_motion) / max(1, len(first_motion)),
            "brightness_mean": sum(x[0] for x in vals) / n,
            "contrast_mean": sum(x[1] for x in vals) / n,
            "black_ratio": blacks / n, "freeze_ratio": freezes / max(1, n - 1),
            "first_3s_motion": sum(first_motion) / max(1, len(first_motion)),
            "first_second_motion": sum(x for x in first_motion if len(first_motion) <= 4 or x is not None)
            / max(1, min(len(first_motion), int(sample_fps))),
            "sample_count": len(samples), "timeline": samples,
        })
        if cuts == 0 and duration > 3:
            observations.append({
                "start_s": 0.0, "end_s": round(duration, 3), "severity": "info",
                "category": "visual_rhythm",
                "message": "No se detectaron cortes en el muestreo; no implica baja calidad.",
                "recommendation": "Validar intención narrativa y claridad con una comparación A/B.",
            })
    except Exception as exc:
        objective.update({k: None for k in FEATURE_NAMES if k not in objective})
        estimated["analysis_note"] = f"opencv_unavailable_or_failed:{type(exc).__name__}"

    silences = _silence_segments(path) if meta.get("has_audio") else []
    objective["silence_segments"] = silences
    objective["voice_presence"] = "audio_stream_present" if meta.get("has_audio") else "no_audio"
    for silence in silences:
        if silence["duration_s"] >= 1.5:
            observations.append({
                "start_s": silence["start_s"], "end_s": silence["end_s"],
                "severity": "review", "category": "prolonged_silence",
                "message": "Silencio prolongado detectado.",
                "recommendation": "Revisar sincronización de narración, intención dramática y CTA.",
            })
    estimated["scene_3d_note"] = (
        "La detección de objetos 3D y de intención de cámara requiere anotación humana o "
        "metadata de Blender; V0.2 sólo marca proxies visuales y no afirma realismo."
    )
    return objective, estimated, observations
