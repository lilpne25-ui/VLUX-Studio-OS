from __future__ import annotations
import json, subprocess
from pathlib import Path
from typing import Any

def probe(path: str | Path) -> dict[str, Any]:
    cmd=["ffprobe","-v","error","-print_format","json","-show_format","-show_streams",str(path)]
    try: raw=subprocess.run(cmd,capture_output=True,text=True,check=True,timeout=30)
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as e: raise ValueError(f"ffprobe_failed: {e}") from e
    try: data=json.loads(raw.stdout)
    except json.JSONDecodeError as e: raise ValueError("invalid_ffprobe_json") from e
    streams=data.get("streams",[]); video=next((s for s in streams if s.get("codec_type")=="video"),None)
    if not video: raise ValueError("video_stream_missing")
    def ratio(v):
        if not v: return None
        if isinstance(v,(int,float)): return float(v)
        if "/" in str(v):
            a,b=str(v).split("/",1); return float(a)/float(b) if float(b) else None
        return float(v)
    return {"duration_s":float(data.get("format",{}).get("duration",0) or 0),"fps":ratio(video.get("avg_frame_rate")) or ratio(video.get("r_frame_rate")),"width":video.get("width"),"height":video.get("height"),"has_audio":any(s.get("codec_type")=="audio" for s in streams),"codec":video.get("codec_name"),"path":str(path)}
