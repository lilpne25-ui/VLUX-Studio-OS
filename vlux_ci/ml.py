from __future__ import annotations
import json, math, random, statistics
from pathlib import Path
from .db import FEATURE_NAMES, json_dumps, sha256_file

class Baseline:
    name="rules-v0.1"
    def score(self, row):
        # Conservative quality proxy; commercial outcomes are never inferred here.
        motion=float(row.get("motion_mean") or 0); brightness=float(row.get("brightness_mean") or 0); contrast=float(row.get("contrast_mean") or 0)
        duration=float(row.get("duration_s") or 0); black=float(row.get("black_ratio") or 0); freeze=float(row.get("freeze_ratio") or 0)
        s=0.35*min(motion/25,1)+0.25*min(contrast/70,1)+0.20*min(brightness/180,1)+0.20*(1-min(black+freeze,1))
        return max(0,min(1,s))

def load_rows(con):
    rows=[]
    for r in con.execute("SELECT v.*, a.objective_json FROM videos v JOIN analyses a ON a.id=(SELECT max(id) FROM analyses WHERE video_id=v.id)"):
        d=dict(r); d.update(json.loads(d.pop("objective_json"))); rows.append(d)
    return rows

def label_from_feedback(con, video_id):
    # Pairwise preference becomes a binary label for each variant.
    vals=[]
    for r in con.execute("SELECT * FROM feedback WHERE variant_a_id=? OR variant_b_id=?",(video_id,video_id)):
        vals.append(1.0 if (r["winner"]=="A" and r["variant_a_id"]==video_id) or (r["winner"]=="B" and r["variant_b_id"]==video_id) else 0.0 if r["winner"]!="tie" else 0.5)
    return statistics.mean(vals) if vals else None

def dataset(con):
    rows=[]
    for r in load_rows(con):
        label=label_from_feedback(con,r["id"])
        if label is not None: rows.append((r,label))
    payload=[{"id":r["id"],"file_hash":r["file_hash"],"label":y,"features":[r.get(k) for k in FEATURE_NAMES]} for r,y in rows]
    digest=__import__('hashlib').sha256(json_dumps(payload).encode()).hexdigest()
    return rows,digest

def vector(row): return [float(row.get(k) or 0) for k in FEATURE_NAMES]

def train(con, artifact_dir, seed=17, min_examples=8):
    rows,digest=dataset(con)
    episodes={r["episode"] for r,_ in rows}
    if len(rows)<min_examples or len(episodes)<2: return {"status":"NO_TRAINING_INSUFFICIENT_DATA","examples":len(rows),"episodes":len(episodes),"dataset_hash":digest}
    # Group holdout: last episode lexicographically, never scene-level random split.
    holdout_ep=sorted(episodes)[-1]; train_rows=[x for x in rows if x[0]["episode"]!=holdout_ep]; test_rows=[x for x in rows if x[0]["episode"]==holdout_ep]
    if len(train_rows)<4 or len(test_rows)<2 or len({int(y>=.5) for _,y in train_rows})<2: return {"status":"NO_TRAINING_INSUFFICIENT_DATA","reason":"holdout_or_class_balance","examples":len(rows),"dataset_hash":digest}
    try:
        import numpy as np
        X=np.array([vector(r) for r,_ in train_rows],dtype=float); y=np.array([1 if z>=.5 else 0 for _,z in train_rows],dtype=float); mu=X.mean(0); sd=X.std(0); sd[sd==0]=1; X=(X-mu)/sd
        w=np.zeros(X.shape[1]); b=0.0; rng=random.Random(seed)
        for _ in range(1200):
            order=list(range(len(y))); rng.shuffle(order)
            for i in order:
                p=1/(1+math.exp(-max(-30,min(30,float(X[i]@w+b))))); err=p-y[i]; w-=0.03*(err*X[i]+0.01*w); b-=0.03*err
        def pred(r):
            z=(np.array(vector(r))-mu)/sd; return 1/(1+math.exp(-max(-30,min(30,float(z@w+b)))))
        yt=[int(y0>=.5) for _,y0 in test_rows]; yp=[int(pred(r)>=.5) for r,_ in test_rows]; acc=sum(a==b for a,b in zip(yt,yp))/len(yt)
        base=Baseline(); by=[int(base.score(r)>=.5) for r,_ in test_rows]; bacc=sum(a==b for a,b in zip(yt,by))/len(yt)
        artifact=Path(artifact_dir)/f"model-{digest[:12]}.json"; artifact.parent.mkdir(parents=True,exist_ok=True)
        artifact.write_text(json.dumps({"type":"logistic_numpy","seed":seed,"feature_names":FEATURE_NAMES,"mean":mu.tolist(),"scale":sd.tolist(),"weights":w.tolist(),"bias":b},indent=2),encoding="utf-8")
        return {"status":"TRAINED","examples":len(rows),"train_examples":len(train_rows),"holdout_examples":len(test_rows),"holdout_episode":holdout_ep,"accuracy":acc,"baseline_accuracy":bacc,"dataset_hash":digest,"artifact_path":str(artifact),"artifact_hash":sha256_file(artifact),"seed":seed}
    except Exception as e: return {"status":"TRAINING_FAILED","error":str(e),"dataset_hash":digest}

def infer(artifact, row):
    d=json.loads(Path(artifact).read_text(encoding="utf-8")); import numpy as np
    x=(np.array(vector(row))-np.array(d["mean"]))/np.array(d["scale"]); z=float(x@np.array(d["weights"])+d["bias"]); return 1/(1+math.exp(-max(-30,min(30,z))))
