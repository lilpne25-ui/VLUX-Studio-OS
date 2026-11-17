from __future__ import annotations
import subprocess, tempfile
from pathlib import Path

def run(cmd,cwd): return subprocess.run(cmd,cwd=cwd,text=True,capture_output=True)
def main():
    root=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(dir=root/'data'/'synthetic') as d:
        d=Path(d); db=d/'demo.sqlite'; a=d/'a.mp4'; b=d/'b.mp4'
        for out,color in [(a,'blue'),(b,'orange')]: subprocess.run(['ffmpeg','-y','-f','lavfi','-i',f'color=c={color}:s=160x90:d=1.2','-an','-pix_fmt','yuv420p',str(out)],capture_output=True,check=True)
        base=['python','-m','vlux_ci.cli','--db',str(db)]
        for file,ep in [(a,'SYN-A'),(b,'SYN-B')]:
            r=run(base+['import',str(file),'--episode',ep,'--permission','synthetic'],root); print(r.stdout)
        for i in (1,2): print(run(base+['analyze',str(i)],root).stdout)
        print(run(base+['feedback','--a','1','--b','2','--winner','A','--clarity','4','--commercial-quality','4','--origin','synthetic-demo'],root).stdout)
        print(run(base+['baseline'],root).stdout); print(run(base+['train','--artifacts',str(d/'artifacts'),'--min-examples','8'],root).stdout)
        print('DEMO_DB='+str(db))
if __name__=='__main__': main()
