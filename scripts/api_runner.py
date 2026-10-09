"""Bob: explicit API submission with conservative reservations. Python standard library."""
from pathlib import Path
import argparse,json,os,time,hashlib
from urllib.request import Request,urlopen
from contextlib import contextmanager

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,d):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    content=json.dumps(d,ensure_ascii=False,indent=2)
    (p.parent/(p.stem+'.journal-'+str(time.time_ns())+'.json')).write_text(content,encoding='utf8')
    for attempt in range(12):
        try:p.write_text(content,encoding='utf8');return
        except PermissionError:
            if attempt==11:raise
            time.sleep(.25)
@contextmanager
def locked(p):
    lock=Path(str(p)+'.lock');lock.parent.mkdir(parents=True,exist_ok=True)
    try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError:raise RuntimeError('账本已锁定；先确认没有运行任务，不自动删除锁') from None
    try:os.write(fd,str(os.getpid()).encode());os.close(fd);yield
    finally:lock.unlink(missing_ok=True)
def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['preview','init','submit','poll','settle'])
    for name in ['request','ledger','provider','key-env','key-file','name','output']:p.add_argument('--'+name)
    p.add_argument('--budget',type=float);p.add_argument('--initial-spent',type=float,default=0)
    p.add_argument('--reserve',type=float);p.add_argument('--cost',type=float);a=p.parse_args()
    if a.action=='preview':
        body=read(a.request);print(json.dumps({'model':body.get('model'),'duration':body.get('duration'),'voice':body.get('voice_setting',{}).get('voice_id'),'text_characters':len(body.get('text','')),'reference_count':sum(c.get('type')!='text' for c in body.get('content',[])),'network_request':False}));return
    if not a.ledger:raise RuntimeError('需要 --ledger')
    with locked(a.ledger):
        if a.action=='init':
            if Path(a.ledger).exists():raise RuntimeError('账本已存在，不覆盖')
            if a.budget is None or a.budget<=0 or not 0<=a.initial_spent<=a.budget:raise RuntimeError('预算或已花费用无效')
            write(a.ledger,{'budget_cny':a.budget,'initial_spent_cny':a.initial_spent,'tasks':[]});print('账本已初始化');return
        d=read(a.ledger);task=next((t for t in d['tasks'] if t['name']==a.name),None)
        if a.action=='settle':
            if task is None or a.cost is None or a.cost<0:raise RuntimeError('需已有任务和核实后的非负费用')
            task['verified_cost_cny']=a.cost;write(a.ledger,d);print('费用已登记');return
        if a.provider not in ['ark','minimax']:raise RuntimeError('provider应为ark或minimax')
        key=(Path(a.key_file).read_text(encoding='utf-8-sig').strip() if a.key_file else os.environ.get(a.key_env or ('ARK_API_KEY' if a.provider=='ark' else 'MINIMAX_API_KEY'),'').strip())
        if not key or '\n' in key:raise RuntimeError('缺少单行密钥；不会输出密钥')
        if key.startswith('Bearer '):key=key[7:]
        if a.action=='submit':
            if task:raise RuntimeError('任务名已存在，禁止重复提交；先查询或核查服务端')
            if not a.name or a.reserve is None or a.reserve<=0:raise RuntimeError('需要唯一name和正数reserve')
            body=read(a.request)
            if '请填写' in body.get('model','') or any('example.com' in str(c) for c in body.get('content',[])):raise RuntimeError('请求仍含示例占位，先填写授权模型和素材')
            if a.provider=='minimax' and (body.get('stream') or body.get('output_format','hex')!='hex' or not a.output):raise RuntimeError('本工具只支持非流式hex音频，需指定output')
            if a.provider=='minimax' and Path(a.output).exists():raise RuntimeError('输出已存在，未提交；选择新版本路径')
            used=d['initial_spent_cny']+sum(t.get('verified_cost_cny',t['reserve_cny']) for t in d['tasks'])
            if used+a.reserve>d['budget_cny']:raise RuntimeError('预算余量不足，未提交')
            task={'name':a.name,'provider':a.provider,'status':'submitting','reserve_cny':a.reserve,'created_at':time.time(),'request_sha256':hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()}
            d['tasks'].append(task);write(a.ledger,d)
            endpoint='https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks' if a.provider=='ark' else 'https://api.minimax.cn/v1/t2a_v2'
            req=Request(endpoint,data=json.dumps(body,ensure_ascii=False).encode('utf8'),method='POST')
        else:
            if not task or not task.get('id') or a.provider!='ark' or task['provider']!='ark':raise RuntimeError('poll需要已有Ark任务ID')
            req=Request('https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/'+task['id'],method='GET')
        req.add_header('Authorization','Bearer '+key);req.add_header('Content-Type','application/json')
        try:
            with urlopen(req,timeout=60) as response:r=json.load(response)
        except Exception:
            if a.action=='submit':task['status']='uncertain';write(a.ledger,d)
            raise RuntimeError('未获得确定响应；不自动重复POST。查询/核查服务端后再处理') from None
        if a.provider=='minimax':
            code=r.get('base_resp',{}).get('status_code')
            if code!=0:task.update(status='rejected',error_code=code);write(a.ledger,d);raise RuntimeError('业务错误码 '+str(code))
            audio=r.get('data',{}).get('audio')
            if not audio:task['status']='uncertain';write(a.ledger,d);raise RuntimeError('未返回音频')
            out=Path(a.output)
            if out.exists():raise RuntimeError('输出已存在，保留本次任务记录，人工处理；不会覆盖')
            out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(bytes.fromhex(audio))
            task.update(status='saved',output=str(out.resolve()),usage=r.get('extra_info',{}))
        else:
            task.update(id=r.get('id',task.get('id')),status=r.get('status','submitted' if r.get('id') else 'uncertain'),usage=r.get('usage',{}))
            if r.get('content'):task['content']=r['content']
        write(a.ledger,d);print(json.dumps({'name':a.name,'status':task['status'],'id':task.get('id')},ensure_ascii=False))
if __name__=='__main__':
    try:main()
    except Exception as e:print('停止：'+str(e));raise SystemExit(1)
