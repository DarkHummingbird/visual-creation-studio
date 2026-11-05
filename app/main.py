import asyncio,base64,io,json,os,time,zipfile,hashlib
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI,UploadFile,File,Form,Request,HTTPException
from fastapi.responses import FileResponse,JSONResponse,StreamingResponse
from fastapi.staticfiles import StaticFiles
from . import config,files,schemas,model_api
from .db import DBASE,Conflict,uid
from .workflow import ENGINE,selected_asset
from pydantic import ValidationError

@asynccontextmanager
async def lifespan(app):
    import fcntl
    lock=(config.DATA/'service.lock').open('a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise RuntimeError('已有工作台服务使用此数据目录，请打开现有页面') from None
    ENGINE.start()
    try:yield
    finally:
        ENGINE.stop.set()
        if ENGINE.thread:ENGINE.thread.join(timeout=2)
        fcntl.flock(lock,fcntl.LOCK_UN);lock.close()
app=FastAPI(title='视觉创作工作台',version='1.0.0',lifespan=lifespan)

@app.middleware('http')
async def local_only(request:Request,call_next):
    host=request.headers.get('host','').split(':')[0]
    if host not in ('127.0.0.1','localhost','testserver'):return JSONResponse({'error':'仅允许本机访问'},403)
    origin=request.headers.get('origin')
    if request.method not in ('GET','HEAD','OPTIONS') and origin and origin not in ('http://127.0.0.1:8765','http://localhost:8765','http://127.0.0.1:5173','http://localhost:5173'):
        return JSONResponse({'error':'请求来源不允许'},403)
    try:
        if int(request.headers.get('content-length','0'))>30_000_000:return JSONResponse({'error':'请求过大，文件最多20MB，图片最多16MB'},413)
    except ValueError:return JSONResponse({'error':'无效请求长度'},400)
    return await call_next(request)
@app.exception_handler(ValueError)
async def invalid(request,e):return JSONResponse({'error':str(e)},400)
@app.exception_handler(ValidationError)
async def bad_contract(request,e):return JSONResponse({'error':'阶段内容不符合固定格式，请检查必填字段、时长与参考数量','details':str(e)[:700]},422)
@app.exception_handler(Conflict)
async def conflict(request,e):return JSONResponse({'error':str(e),'code':'VERSION_CONFLICT'},409)

@app.get('/api/v1/state')
def state():
    runs=[]
    for r in DBASE.runs():
        runs.append({k:v for k,v in r.items() if k!='snapshot'})
    return {'drafts':DBASE.drafts(),'assets':[{k:v for k,v in a.items() if k!='path'} for a in DBASE.assets()],'runs':runs,'config':config.status()}
@app.get('/api/v1/health')
def health():return {'ok':True,'version':'1.0.0','workerCount':1}
@app.get('/api/v1/contracts')
def contracts():return {s.__name__:s.model_json_schema() for s in (schemas.Script,schemas.Cards,schemas.Shots)}
@app.get('/api/v1/costs')
def costs():return {'implemented':False,'actual':None,'status':'NOT_IMPLEMENTED','label':'实际费用未接入'}
@app.post('/api/v1/drafts')
def create(p:schemas.NewDraft):return DBASE.create(p.scene,p.name.strip())
@app.get('/api/v1/drafts/{id}')
def draft(id:str):return DBASE.draft(id)
@app.put('/api/v1/drafts/{id}')
def save(id:str,p:schemas.SaveDraft):
    request_hash=hashlib.sha256(json.dumps([id,p.baseVersion,p.data],sort_keys=True).encode()).hexdigest()
    with DBASE.conn() as c: prior=c.execute('SELECT * FROM mutations WHERE id=?',(p.mutationId,)).fetchone()
    if prior:
        if prior['hash']!=request_hash:raise Conflict('同一保存编号对应不同内容')
        return json.loads(prior['response'])
    # Validate contracts when users edit structured stage outputs.
    if p.data.get('script'):schemas.Script.model_validate(p.data['script'])
    if p.data.get('cards'):schemas.Cards.model_validate({'cards':p.data['cards']})
    if p.data.get('shots'):schemas.Shots.model_validate({'shots':p.data['shots']})
    old=DBASE.draft(id)['data'];new=p.data
    text=new.get('source',{}).get('text','')
    if len(text)>5000 and text!=old.get('source',{}).get('text',''):
        a=files.ingest(text.encode(),'粘贴正文.txt','SOURCE_TEXT');new['source']['textAssetId']=a['id']
    def same(k):
        # 核对/清理警告属于设计内的确认动作，不视为上游内容修改
        if k=='analysisWarnings':return True
        if k=='script':
            a={x:y for x,y in (old.get(k) or {}).items() if x!='warnings'}
            b={x:y for x,y in (new.get(k) or {}).items() if x!='warnings'}
            return a==b
        return old.get(k)==new.get(k)
    changed=any(not same(k) for k in ('source','script','cards','shots'))
    invalid=set(old.get('invalidStages',[]))
    if old.get('source',{}).get('text')!=new.get('source',{}).get('text') or old.get('source',{}).get('type')!=new.get('source',{}).get('type'):invalid.update(['script','cards','shots','media'])
    elif not same('script'):invalid.update(['cards','shots','media'])
    elif old.get('cards')!=new.get('cards'):invalid.update(['shots','media'])
    elif old.get('shots')!=new.get('shots'):invalid.add('media')
    new['invalidStages']=list(invalid)
    if changed and old.get('candidates'):
        new['needsReview']=[s['id'] for s in new.get('shots',[])]
    if len(new.get('source',{}).get('text',''))>200_000:raise ValueError('正文超过200,000字符，请拆分后处理')
    result=DBASE.save(id,p.baseVersion,p.mutationId,new,request_hash)
    if all(same(k) for k in set(old)|set(new) if k!='step'):
        for run in DBASE.runs():
            if run['draft']==id and run['status'] in ('READY','RUNNING','PAUSED'):
                snapshot=run['snapshot'];snapshot['draftVersion']=result['version'];DBASE.update_run(run['id'],snapshot=snapshot)
    return result
@app.post('/api/v1/drafts/{id}/rename')
def rename(id:str,p:dict):
    name=str(p.get('name','')).strip()
    if not name or len(name)>100:raise ValueError('名称需在1至100字之间')
    with DBASE.lock,DBASE.conn() as c:c.execute('UPDATE drafts SET name=?,updated=? WHERE id=?',(name,time.time(),id))
    return DBASE.draft(id)
@app.post('/api/v1/drafts/{id}/copy')
def copy(id:str):
    d=DBASE.draft(id);data=d['data'];data['exports']=[]
    return DBASE.create(d['scene'],d['name']+' 副本',data)
@app.delete('/api/v1/drafts/{id}')
def delete(id:str):
    if any(r['draft']==id and r['status'] in ('RUNNING','READY') for r in DBASE.runs()):raise ValueError('请先暂停或结束正在执行的制作')
    with DBASE.conn() as c:c.execute('UPDATE drafts SET deleted=1 WHERE id=?',(id,))
    return {'deleted':True,'filesPreserved':True}
@app.post('/api/v1/assets/upload')
async def upload(file:UploadFile=File(...),name:str=Form('')):
    raw=await file.read(16_000_001)
    if len(raw)>16_000_000:raise ValueError('图片超过16MB，请压缩或转换格式')
    if Path(file.filename or '').suffix.lower() not in ('.png','.jpg','.jpeg','.webp'):raise ValueError('图片仅支持PNG、JPEG、WebP')
    a=await asyncio.to_thread(files.ingest,raw,file.filename)
    if name.strip():
        with DBASE.lock,DBASE.conn() as c:c.execute('UPDATE assets SET name=? WHERE id=?',(name.strip()[:100],a['id']))
        a=DBASE.asset(a['id'])
    return {k:v for k,v in a.items() if k!='path'}
@app.post('/api/v1/assets/{id}/rename')
def asset_rename(id:str,p:dict):
    name=str(p.get('name','')).strip()
    if not name or len(name)>100:raise ValueError('名称需在1至100字之间')
    with DBASE.lock,DBASE.conn() as c:c.execute('UPDATE assets SET name=? WHERE id=?',(name,id))
    return DBASE.asset(id)
@app.post('/api/v1/assets/{id}/group')
def asset_group(id:str,p:dict):
    DBASE.asset(id)
    group=str(p.get('group','')).strip()[:50]
    with DBASE.lock,DBASE.conn() as c:c.execute('UPDATE assets SET grp=? WHERE id=?',(group,id))
    return DBASE.asset(id)
ROLES=['商品','背景','构图','品牌','其他']
@app.post('/api/v1/assets/{id}/role')
def asset_role(id:str,p:dict):
    DBASE.asset(id)
    role=str(p.get('role','')).strip()
    if role and role not in ROLES:raise ValueError('角色须为：'+'、'.join(ROLES))
    with DBASE.lock,DBASE.conn() as c:c.execute('UPDATE assets SET role=? WHERE id=?',(role,id))
    return DBASE.asset(id)
@app.post('/api/v1/import')
async def import_doc(file:UploadFile=File(...)):
    raw=await file.read(files.MAX_FILE+1)
    if len(raw)>files.MAX_FILE:raise ValueError('单个文件最多20MB，请去除图片、导出TXT或按章节拆分')
    result=await asyncio.to_thread(files.extract,raw,file.filename or '')
    original=files.ingest(raw,file.filename or '原文.txt','SOURCE')
    text=files.ingest(result['text'].encode(),'提取正文.txt','SOURCE_TEXT')
    return {**result,'fileName':file.filename,'originalAssetId':original['id'],'textAssetId':text['id']}
@app.post('/api/v1/copy-suggestions')
def copy_suggestions(p:dict):
    name=str(p.get('name','')).strip();desc=str(p.get('description','')).strip()
    if not name:raise ValueError('请先填写商品名称')
    schema={'type':'object','properties':{'suggestions':{'type':'array','items':{'type':'string'},'minItems':5,'maxItems':5}},'required':['suggestions']}
    prompt='商品名称：'+name+'\n已知资料：'+(desc or '无')+'\n请为该商品的海报生成5条中文促销短文案：每条不超过12字，风格各异（卖点型、促销型、情感型、行动号召型），适合直接放在商品图上。仅返回JSON。'
    response=model_api.text(prompt,schema)
    value=json.loads(response['choices'][0]['message']['content'])
    return {'suggestions':[str(s).strip()[:20] for s in value.get('suggestions',[]) if str(s).strip()][:5]}
@app.get('/media/{id}')
def media(id:str,download:bool=False):
    a=DBASE.asset(id);path=Path(a['path'])
    if not path.is_relative_to(config.DATA):raise ValueError('文件路径不合法')
    return FileResponse(path,filename=a['name'] if download else None,headers={'X-Content-Type-Options':'nosniff','Cache-Control':'private, max-age=3600'})
@app.post('/api/v1/drafts/{id}/runs')
def start(id:str,p:schemas.StartRun):return ENGINE.submit(id,p)
@app.get('/api/v1/runs/{id}')
def run(id:str):
    r=DBASE.run(id);r.pop('snapshot',None);r['attempts']=[{k:v for k,v in a.items() if k not in ('input','response')} for a in DBASE.attempts(id)];return r
@app.post('/api/v1/runs/{id}/{action}')
def action(id:str,action:str):return {k:v for k,v in ENGINE.control(id,action).items() if k!='snapshot'}
@app.post('/api/v1/drafts/{id}/export-canvas')
def export_canvas(id:str,p:dict):
    raw=base64.b64decode(p['data'].split(',')[-1],validate=True)
    name=str(p.get('name') or '商品排版.png').strip()[:100] or '商品排版.png'
    if not name.lower().endswith(('.png','.jpg','.webp')):name+='.png'
    a=files.ingest(raw,name,'CANVAS_EXPORT',{'draftId':id,'width':p.get('width'),'height':p.get('height')})
    if a['meta']['width']!=p.get('width') or a['meta']['height']!=p.get('height'):raise ValueError('导出尺寸与请求不符，未登记成品')
    DBASE.patch(id,lambda d:d['exports'].append(a['id']));return a
@app.get('/api/v1/drafts/{id}/export')
def export_bundle(id:str):
    d=DBASE.draft(id);ids=set()
    for x in d['data'].get('candidates',{}).values():ids.update(x)
    ids.update(d['data'].get('exports',[]))
    for c in d['data'].get('cards',[]):
        if c.get('assetId'):ids.add(c['assetId'])
    for sku in d['data'].get('product',{}).get('skus',[]):ids.update(sku.get('refs',[]))
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('创作记录.json',json.dumps(d,ensure_ascii=False,indent=2))
        for aid in ids:
            a=DBASE.asset(aid);z.write(a['path'],'素材/'+a['id']+Path(a['path']).suffix)
    return StreamingResponse(iter([buf.getvalue()]),media_type='application/zip',headers={'Content-Disposition':'attachment; filename="studio-export.zip"'})
@app.get('/api/v1/events')
async def events(request:Request):
    async def stream():
        while not await request.is_disconnected():
            yield 'data: '+json.dumps({'at':time.time()})+'\n\n';await asyncio.sleep(3)
    return StreamingResponse(stream(),media_type='text/event-stream')

DIST=config.ROOT/'frontend'/'dist'
if DIST.exists():app.mount('/assets',StaticFiles(directory=DIST/'assets'),name='assets')
@app.get('/{path:path}')
def spa(path:str):
    if path.startswith('api/'):raise HTTPException(404)
    if not (DIST/'index.html').exists():return JSONResponse({'error':'请先构建前端：npm --prefix frontend run build'},503)
    return FileResponse(DIST/'index.html')
