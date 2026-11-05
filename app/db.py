import json,sqlite3,threading,time,uuid,hashlib
from copy import deepcopy
from .config import DATA

def uid():return uuid.uuid4().hex
class Conflict(Exception):pass
class _Session:
    # sqlite3 连接作上下文管理器只提交不关闭；这里补 close，避免句柄泄漏
    def __init__(self,c):self.c=c;c.row_factory=sqlite3.Row
    def __enter__(self):return self.c
    def __exit__(self,exc_type,*_):
        try:
            if exc_type is None:self.c.commit()
            else:self.c.rollback()
        finally:self.c.close()
class DB:
    def __init__(self,root=DATA):
        self.root=root;self.lock=threading.RLock();root.mkdir(parents=True,exist_ok=True)
        with self.conn() as c:
            c.executescript('''PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS drafts(id TEXT PRIMARY KEY,scene TEXT,name TEXT,version INTEGER,event_rev INTEGER,data TEXT,updated REAL,deleted INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS revisions(id TEXT,draft TEXT,version INTEGER,data TEXT,created REAL);
CREATE TABLE IF NOT EXISTS mutations(id TEXT PRIMARY KEY,hash TEXT,response TEXT);
CREATE TABLE IF NOT EXISTS assets(id TEXT PRIMARY KEY,name TEXT,kind TEXT,path TEXT,origin TEXT,meta TEXT,created REAL);
CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,draft TEXT,kind TEXT,status TEXT,control TEXT,snapshot TEXT,steps TEXT,cursor INTEGER,error TEXT,result TEXT,created REAL,updated REAL);
CREATE TABLE IF NOT EXISTS attempts(id TEXT PRIMARY KEY,run TEXT,step TEXT,kind TEXT,request_status TEXT,delivery_status TEXT,remote_id TEXT,response TEXT,asset_id TEXT,error TEXT,input TEXT,created REAL);
''')
            try:c.execute('ALTER TABLE assets ADD COLUMN grp TEXT DEFAULT ""')
            except sqlite3.OperationalError:pass
    def conn(self):
        return _Session(sqlite3.connect(self.root/'studio-v1.sqlite3',timeout=30))
    def draft(self,id):
        with self.conn() as c:r=c.execute('SELECT * FROM drafts WHERE id=? AND deleted=0',(id,)).fetchone()
        if not r:raise ValueError('草稿不存在')
        d=dict(r);d['data']=json.loads(d['data']);return d
    def drafts(self):
        with self.conn() as c: ids=[r[0] for r in c.execute('SELECT id FROM drafts WHERE deleted=0 ORDER BY updated DESC')]
        return [self.draft(x) for x in ids]
    def create(self,scene,name,data=None):
        id=uid();default={'step':0,'product':{'name':'','description':'','style':'自然光 · 干净背景','skus':[]},'source':{'text':'','type':'story','complete':True,'warnings':[]},'settings':{'style':'电影写实','ratio':'16:9','targetSeconds':20,'audio':True,'resolution':'480P','maxShots':8,'maxReferences':8},'script':None,'cards':[],'shots':[],'candidates':{},'adoptions':{},'canvas':{'width':1000,'height':1000,'layers':[],'variants':[]},'exports':[],'needsReview':[]}
        with self.lock,self.conn() as c:c.execute('INSERT INTO drafts VALUES (?,?,?,?,?,?,?,0)',(id,scene,name,1,0,json.dumps(data or default,ensure_ascii=False),time.time()))
        return self.draft(id)
    def save(self,id,version,mutation,data,request_hash=None):
        digest=request_hash or hashlib.sha256(json.dumps([id,version,data],sort_keys=True).encode()).hexdigest()
        with self.lock,self.conn() as c:
            c.execute('BEGIN IMMEDIATE');m=c.execute('SELECT * FROM mutations WHERE id=?',(mutation,)).fetchone()
            if m:
                if m['hash']!=digest:raise Conflict('保存编号已用于不同内容')
                return json.loads(m['response'])
            d=self.draft(id)
            if d['version']!=version:raise Conflict('另一个页面已更新草稿。请保留本地内容并重新打开，或另存副本。')
            # Execution-owned collections cannot be overwritten by stale autosaves.
            for key in ('candidates','exports'):
                data[key]=d['data'].get(key,{} if key=='candidates' else [])
            c.execute('INSERT INTO revisions VALUES (?,?,?,?,?)',(uid(),id,version,json.dumps(d['data'],ensure_ascii=False),time.time()))
            c.execute('UPDATE drafts SET data=?,version=version+1,updated=? WHERE id=?',(json.dumps(data,ensure_ascii=False),time.time(),id))
            response={'version':version+1};c.execute('INSERT INTO mutations VALUES (?,?,?)',(mutation,digest,json.dumps(response)))
        return response
    def patch(self,id,fn):
        with self.lock,self.conn() as c:
            c.execute('BEGIN IMMEDIATE');d=self.draft(id);fn(d['data'])
            c.execute('UPDATE drafts SET data=?,event_rev=event_rev+1,updated=? WHERE id=?',(json.dumps(d['data'],ensure_ascii=False),time.time(),id))
    def asset(self,id):
        with self.conn() as c:r=c.execute('SELECT * FROM assets WHERE id=?',(id,)).fetchone()
        if not r:raise ValueError('素材不存在')
        d=dict(r);d['meta']=json.loads(d['meta']);d['url']='/media/'+id;return d
    def assets(self):
        with self.conn() as c:ids=[r[0] for r in c.execute('SELECT id FROM assets ORDER BY created DESC')]
        return [self.asset(x) for x in ids]
    def add_asset(self,name,kind,path,origin,meta):
        id=uid()
        with self.lock,self.conn() as c:c.execute('INSERT INTO assets VALUES (?,?,?,?,?,?,?,?)',(id,name,kind,str(path),origin,json.dumps(meta,ensure_ascii=False),time.time(),''))
        return self.asset(id)
    def run(self,id):
        with self.conn() as c:r=c.execute('SELECT * FROM runs WHERE id=?',(id,)).fetchone()
        if not r:raise ValueError('制作记录不存在')
        d=dict(r)
        for k in ('snapshot','steps','result'):d[k]=json.loads(d[k])
        return d
    def runs(self):
        with self.conn() as c:ids=[r[0] for r in c.execute('SELECT id FROM runs ORDER BY created DESC LIMIT 100')]
        return [self.run(x) for x in ids]
    def update_run(self,id,**kw):
        for k in ('snapshot','steps','result'):
            if k in kw:kw[k]=json.dumps(kw[k],ensure_ascii=False)
        kw['updated']=time.time()
        with self.lock,self.conn() as c:c.execute('UPDATE runs SET '+','.join(k+'=?' for k in kw)+' WHERE id=?',(*kw.values(),id))
    def attempts(self,run):
        with self.conn() as c:rows=c.execute('SELECT * FROM attempts WHERE run=? ORDER BY created',(run,)).fetchall()
        out=[]
        for row in rows:
            d=dict(row)
            for k in ('response','input'):d[k]=json.loads(d[k])
            out.append(d)
        return out
    def attempt_update(self,id,**kw):
        for k in ('response','input'):
            if k in kw:kw[k]=json.dumps(kw[k],ensure_ascii=False)
        with self.lock,self.conn() as c:c.execute('UPDATE attempts SET '+','.join(k+'=?' for k in kw)+' WHERE id=?',(*kw.values(),id))
DBASE=DB()
