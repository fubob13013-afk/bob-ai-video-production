"""Bob: measure and align speech without silently exceeding a tempo limit."""
from pathlib import Path
import argparse,subprocess,shutil,json
def main():
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('output');p.add_argument('--seconds',type=float,required=True);p.add_argument('--lead',type=float,default=.15);p.add_argument('--tail',type=float,default=.35);p.add_argument('--max-tempo',type=float,default=1.12);a=p.parse_args()
    ff=shutil.which('ffmpeg');fp=shutil.which('ffprobe')
    if not ff or not fp:raise RuntimeError('需要可用的FFmpeg和FFprobe')
    if a.lead<0 or a.tail<0 or a.seconds<=a.lead+a.tail or not 1<=a.max_tempo<=2:raise RuntimeError('时长/留白/变速参数无效')
    if Path(a.output).exists():raise RuntimeError('输出已存在；请选择新版本文件名')
    length=float(subprocess.check_output([fp,'-v','error','-show_entries','format=duration','-of','csv=p=0',a.source]))
    tempo=max(1,length/(a.seconds-a.lead-a.tail))
    if tempo>a.max_tempo:raise RuntimeError(f'语音过长：需{tempo:.3f}倍，超过上限；改短台词或将画面至少延长到{length/a.max_tempo+a.lead+a.tail:.2f}秒')
    Path(a.output).parent.mkdir(parents=True,exist_ok=True)
    subprocess.run([ff,'-v','error','-i',a.source,'-af',f'atempo={tempo},adelay={round(a.lead*1000)}:all=1,apad','-t',str(a.seconds),'-ar','48000','-ac','2','-c:a','pcm_s16le',a.output],check=True)
    print(json.dumps({'raw_seconds':length,'picture_seconds':a.seconds,'tempo':tempo,'lead':a.lead,'minimum_tail':a.tail}))
if __name__=='__main__':
    try:main()
    except Exception as e:print('停止：'+str(e));raise SystemExit(1)
