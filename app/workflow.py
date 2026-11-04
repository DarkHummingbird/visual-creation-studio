import json,time,threading,hashlib,io,zipfile
from pathlib import Path
from .db import DBASE,uid,Conflict
from . import schemas,model_api,files,config
from .scene_presets import _scene_to_env

LABELS={'script':'整理剧本','cards':'提取人物、场景、道具','shots':'编写镜头清单','reference':'生成设定参考','frame':'生成镜头画面','video':'生成镜头视频','compose':'合成完整视频','ecom':'生成商品图','edit':'修改图片'}
class WaitUser(Exception):pass

def selected_asset(d,slot):return d.get('adoptions',{}).get(slot,'')
def candidate(d,slot,asset,auto=False):
    items=d.setdefault('candidates',{}).setdefault(slot,[])
    if asset['id'] not in items:items.append(asset['id'])
    if auto:d.setdefault('adoptions',{})[slot]=asset['id']

def preflight(d,kind,selected,options):
    data=d['data']
    if kind in ('script','oneclick'):
        src=data['source']
        if not src.get('text','').strip():raise ValueError('请先导入故事或剧本')
        if not src.get('complete',False) or len(src['text'])>200_000:raise ValueError('正文未完整导入，请先补充或按章节拆分')
    if kind in ('cards','shots') and not data.get('script'):raise ValueError('请先整理并检查剧本')
    if kind in ('frames','videos','compose') and not data.get('shots'):raise ValueError('请先建立镜头清单')
    if kind=='ecommerce':
        skus=[s for s in data['product']['skus'] if not selected or s['id'] in selected]
        if not skus:raise ValueError('请添加并选择商品款式')
        for s in skus:
            if not s.get('refs'):raise ValueError('款式“'+s['name']+'”没有绑定商品照片')
            if len(s['refs'])>3:raise ValueError('每个款式最多选择3张参考照片')
        count=int(options.get('count',1))
        if not 1<=count<=20 or len(skus)*count>20:raise ValueError('每批最多20张，请分批生成')
    if kind=='editimage':
        if not options.get('assetId') or not options.get('prompt','').strip():raise ValueError('请选择图片并填写修改要求')
    if kind not in ('compose',):
        if kind in ('script','cards','shots','oneclick'):model_api.key('DEEPSEEK_API_KEY')
        if kind in ('frames','references','videos','oneclick','ecommerce','editimage'):model_api.key('DASHSCOPE_API_KEY')

def initial_steps(d,kind,selected,options):
    data=d['data'];steps=[]
    if kind=='script' or (kind=='oneclick' and (not data.get('script') or 'script' in data.get('invalidStages',[]))):
        text=data['source']['text'];chunks=[text[i:i+18000] for i in range(0,len(text),18000)]
        for i,chunk in enumerate(chunks):steps.append({'id':'script-'+str(i),'kind':'script','part':i,'text':chunk,'start':i*18000,'end':i*18000+len(chunk),'total':len(chunks)})
    if kind=='cards' or (kind=='oneclick' and (not data.get('cards') or any(k in data.get('invalidStages',[]) for k in ('script','cards')))):steps.append({'id':'cards','kind':'cards'})
    if kind=='shots' or (kind=='oneclick' and (not data.get('shots') or any(k in data.get('invalidStages',[]) for k in ('script','cards','shots')))):steps.append({'id':'shots','kind':'shots'})
    if kind=='oneclick':steps.append({'id':'expand','kind':'expand'})
    if kind=='references':
        for c in data['cards']:
            if not selected or c['id'] in selected:steps.append({'id':'ref-'+c['id'],'kind':'reference','target':c['id']})
    if kind in ('frames','videos'):
        for s in data['shots']:
            if not selected or s['id'] in selected:steps.append({'id':kind+'-'+s['id'],'kind':'frame' if kind=='frames' else 'video','target':s['id']})
    if kind=='compose':steps.append({'id':'compose','kind':'compose'})
    if kind=='editimage':
        batch=options.get('batch') or [{'assetId':options['assetId'],'prompt':options['prompt'],'slot':options.get('slot','edit-'+options['assetId'])}]
        if len(batch)>20:raise ValueError('每批最多20张')
        for item in batch:
            DBASE.asset(item['assetId'])
            steps.append({'id':uid(),'kind':'edit','target':item['assetId'],'prompt':item['prompt'],'slot':item['slot']})
    if kind=='ecommerce':
        for sku in data['product']['skus']:
            if not selected or sku['id'] in selected:
                for n in range(int(options.get('count',1))):steps.append({'id':uid(),'kind':'ecom','target':sku['id'],'slot':options.get('slot') or 'sku-'+sku['id']+'-'+str(n),'imageType':options.get('imageType','场景图')})
    if not steps:raise ValueError('没有待制作内容')
    return steps

class Executor:
    def __init__(self):self.stop=threading.Event();self.thread=None
    def start(self):
        # No paid POST on restart without a persisted response or known remote task.
        with DBASE.conn() as c:
            c.execute("UPDATE runs SET status='PAUSED',control='PAUSE',error='服务已重启；检查原任务后点击继续' WHERE status IN ('READY','RUNNING')")
            c.execute("UPDATE attempts SET request_status='UNKNOWN',error='提交响应丢失，禁止自动重发' WHERE request_status='SUBMITTING' AND remote_id='' AND response='{}'")
        self.thread=threading.Thread(target=self.worker,daemon=True);self.thread.start()
    def submit(self,draft,p):
        d=DBASE.draft(draft)
        if p.baseVersion!=d['version']:raise Conflict('草稿已变化，请等待自动保存完成后重新开始')
        if p.kind!='compose' and not p.paidConsent:raise ValueError('请确认将调用付费模型，实际费用暂未接入')
        preflight(d,p.kind,p.selectedIds,p.options)
        steps=initial_steps(d,p.kind,p.selectedIds,p.options);digest=hashlib.sha256(json.dumps([draft,p.model_dump()],sort_keys=True).encode()).hexdigest()
        with DBASE.lock,DBASE.conn() as c:
            c.execute('BEGIN IMMEDIATE');m=c.execute('SELECT * FROM mutations WHERE id=?',(p.mutationId,)).fetchone()
            if m:
                if m['hash']!=digest:raise Conflict('同一请求编号对应不同制作内容')
                return DBASE.run(json.loads(m['response'])['id'])
            active=c.execute("SELECT id FROM runs WHERE status IN ('READY','RUNNING') LIMIT 1").fetchone()
            if active:raise Conflict('已有制作正在执行，请返回当前制作或暂停后续步骤')
            id=uid();snapshot={'draftVersion':d['version'],'data':d['data'],'options':p.options,'selectedIds':p.selectedIds,'cost':{'implemented':False,'actual':None},'auto':p.kind=='oneclick'}
            c.execute('INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',(id,draft,p.kind,'READY','CONTINUE',json.dumps(snapshot,ensure_ascii=False),json.dumps(steps,ensure_ascii=False),0,'','{}',time.time(),time.time()))
            c.execute('INSERT INTO mutations VALUES (?,?,?)',(p.mutationId,digest,json.dumps({'id':id})))
        return DBASE.run(id)
    def control(self,id,action):
        with DBASE.lock,DBASE.conn() as c:
            r=DBASE.run(id)
            if action=='pause':DBASE.update_run(id,control='PAUSE')
            elif action=='end':
                DBASE.update_run(id,control='END',status='CANCELLED' if r['status'] not in ('RUNNING','READY') else r['status'])
            elif action=='resume':
                if r['status'] not in ('PAUSED','UNKNOWN','FAILED','RECOVERY_REQUIRED'):raise ValueError('当前状态不能继续')
                active=c.execute("SELECT id FROM runs WHERE status IN ('READY','RUNNING') AND id<>?",(id,)).fetchone()
                if active:raise Conflict('其他制作正在运行，请先暂停或结束')
                at=DBASE.attempts(id);current=next((a for a in at if a['step']==r['steps'][r['cursor']]['id']),None) if r['cursor']<len(r['steps']) else None
                if current and current['request_status'] in ('UNKNOWN','FAILED') and not current['remote_id']:
                    raise ValueError('原请求无可查询编号，不能自动重发。请核对平台记录后显式重新生成对应项。')
                if DBASE.draft(r['draft'])['version']!=r['snapshot']['draftVersion']:raise ValueError('草稿已修改，原计划不可继续。请结束并按最新内容开始制作；旧结果保留。')
                DBASE.update_run(id,status='READY',control='CONTINUE',error='')
            else:raise ValueError('不支持的操作')
        return DBASE.run(id)
    def worker(self):
        while not self.stop.is_set():
            with DBASE.lock,DBASE.conn() as c:
                c.execute('BEGIN IMMEDIATE')
                row=c.execute("SELECT id FROM runs WHERE status='READY' ORDER BY created LIMIT 1").fetchone()
                if row:c.execute("UPDATE runs SET status='RUNNING',updated=? WHERE id=? AND status='READY'",(time.time(),row['id']))
            if not row:self.stop.wait(.4);continue
            id=row['id']
            try:self.execute(id)
            except WaitUser as e:DBASE.update_run(id,status='PAUSED',error=str(e))
            except model_api.RequestUnknown as e:DBASE.update_run(id,status='UNKNOWN',error=str(e))
            except Exception as e:DBASE.update_run(id,status='FAILED',error=str(e)[:700])
    def execute(self,id):
        while not self.stop.is_set():
            r=DBASE.run(id)
            if r['control']!='CONTINUE':
                DBASE.update_run(id,status='CANCELLED' if r['control']=='END' else 'PAUSED');return
            if r['cursor']>=len(r['steps']):DBASE.update_run(id,status='SUCCEEDED',error='');return
            draft=DBASE.draft(r['draft'])
            if draft['version']!=r['snapshot']['draftVersion']:raise WaitUser('草稿已修改，后续制作已暂停；已生成文件保留，请按新内容重新开始。')
            step=r['steps'][r['cursor']]
            if step['kind']=='expand':self.expand(r)
            else:self.execute_step(r,step)
            # Checkpoint after file+DB completion, before advancing.
            DBASE.update_run(id,cursor=r['cursor']+1)
    def expand(self,r):
        data=DBASE.draft(r['draft'])['data'];settings=data['settings'];shots=data['shots'];used={x for s in shots for x in s['referenceIds']}
        cards=[x for x in data['cards'] if x['id'] in used and not x.get('assetId')]
        if len(shots)>int(settings.get('maxShots',8)) or len(cards)>int(settings.get('maxReferences',8)):
            raise WaitUser('分析后的镜头或参考数量超过本次制作范围。请检查清单、调整范围后从参考或镜头阶段继续。')
        warnings=data.get('script',{}).get('warnings',[])+data.get('analysisWarnings',[])
        if warnings:raise WaitUser('分析发现待确认内容：'+'；'.join(warnings)[:400]+'。请先逐步检查，再从后续阶段制作。')
        extra=[{'id':'ref-'+c['id'],'kind':'reference','target':c['id']} for c in cards]
        extra += [{'id':'frame-'+s['id'],'kind':'frame','target':s['id']} for s in shots if not selected_asset(data,'frame-'+s['id']) or s['id'] in data.get('needsReview',[])]
        extra += [{'id':'video-'+s['id'],'kind':'video','target':s['id']} for s in shots if not selected_asset(data,'video-'+s['id']) or s['id'] in data.get('needsReview',[])]
        extra += [{'id':'compose','kind':'compose'}]
        DBASE.update_run(r['id'],steps=r['steps'][:r['cursor']+1]+extra)
    def new_attempt(self,r,step,input):
        existing=next((a for a in DBASE.attempts(r['id']) if a['step']==step['id']),None)
        if existing:return existing
        id=uid()
        with DBASE.conn() as c:c.execute('INSERT INTO attempts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',(id,r['id'],step['id'],step['kind'],'READY','PENDING','','{}','','',json.dumps(input,ensure_ascii=False),time.time()))
        return next(a for a in DBASE.attempts(r['id']) if a['id']==id)
    def execute_step(self,r,step):
        data=DBASE.draft(r['draft'])['data'];kind=step['kind'];auto=r['snapshot']['auto'];settings=data['settings'];payload={'step':step,'settings':settings}
        target=None;refs=[];prompt='';schema=None
        if kind=='script':
            schema=schemas.Script
            previous=data.get('scriptParts',[])[:step['part']]
            context=json.dumps([{'synopsis':p['synopsis'],'lastScenes':p['scenes'][-2:]} for p in previous[-3:]],ensure_ascii=False)
            prompt=('将故事改编为可拍摄剧本，' if data['source']['type']=='story' else '整理已有剧本，保留人物关系、剧情和对白，不重新编造，')+f"本段为第{step['part']+1}/{step['total']}段，覆盖原文字符[{step['start']},{step['end']})。前段连续性上下文：{context}。如人物关系、事件因果不清，将问题列入warnings，不擅自补全。正文："+step['text']
        elif kind=='cards':
            schema=schemas.Cards;prompt='提取剧本中的人物、地点、关键道具参考卡。按同一人物归一别名，换衣服为不同lookVersionId，characterId保持一致。id如char_a_look1/location_a/prop_a，voice为声音文字描述，assetId为空。仅提取实际需要的内容：'+json.dumps(data['script'],ensure_ascii=False)
        elif kind=='shots':
            schema=schemas.Shots;prompt='根据剧本与参考卡编写连续镜头清单，不固定镜头数。每个referenceIds最多3张且只能用给出的卡片id；人物场景道具共占名额。speakerId用人物characterId或空。dependsOn只引用已有镜头id。清晰描述进入状态、动作与结束状态，不删改关键剧情。目标片长'+str(settings['targetSeconds'])+'秒，画风'+settings['style']+'。无法满足目标片长时在warnings说明。'+json.dumps({'script':data['script'],'cards':data['cards']},ensure_ascii=False)
        elif kind=='reference':
            target=next(c for c in data['cards'] if c['id']==step['target']);prompt=f"{target['name']}，{target['description']}。{settings['style']}，单一主体设定参考图，清晰外观，无拼图，无文字。"
        elif kind in ('frame','video'):
            target=next(s for s in data['shots'] if s['id']==step['target']);schemas.Shot.model_validate(target)
            if kind=='frame':
                cards={c['id']:c for c in data['cards']}
                for rid in target['referenceIds']:
                    card=cards.get(rid)
                    if not card or not card.get('assetId'):raise WaitUser('镜头“'+target['title']+'”缺少已采用的参考图，请先补齐')
                    refs.append(DBASE.asset(card['assetId']))
                prompt=target['prompt']+'；画风：'+settings['style']+'。只生成本镜头关键画面，保留参考中人物身份、服装和道具。'
                prompt+='参考对应：'+'；'.join(f"图{i+1}={cards[rid]['name']}，{cards[rid]['description']}" for i,rid in enumerate(target['referenceIds']))
            else:
                aid=selected_asset(data,'frame-'+target['id'])
                if not aid:raise WaitUser('镜头“'+target['title']+'”尚未采用画面')
                refs=[DBASE.asset(aid)];prompt=target['action']+'。运镜：'+target['camera']+'。'+('对白：'+target['dialogue'] if target['dialogue'] else '无对白。')
                speaker=next((c for c in data['cards'] if c.get('characterId')==target.get('speakerId') and c['kind']=='CHARACTER'),None)
                if speaker:prompt+='说话人：'+speaker['name']+'；声音：'+speaker.get('voice','')
                prompt+='。保持首帧角色、服装、场景和道具一致，不添加背景音乐。'
        elif kind=='ecom':
            target=next(s for s in data['product']['skus'] if s['id']==step['target']);refs=[DBASE.asset(x) for x in target['refs']]
            prompt=f"制作{step['imageType']}。商品：{data['product']['name']}，款式：{target['name']}。已知资料：{data['product']['description']}。风格与场景：{data['product']['style']}。严格保留参考商品的形状、颜色、材质、图案与包装，不添加未提供的功能或认证。"
            if step['imageType']=='场景图':prompt+='环境描述：'+_scene_to_env(data['product']['style'],data['product']['name'])
        elif kind=='edit':
            refs=[DBASE.asset(step['target'])];prompt=step['prompt']+'。只修改指定范围，保留其余内容。'
        elif kind=='compose':
            if data.get('needsReview'):raise WaitUser('部分镜头有上游修改，请先确认复查后再合成')
            clips=[]
            for shot in data['shots']:
                aid=selected_asset(data,'video-'+shot['id'])
                if not aid:raise WaitUser('必要镜头“'+shot['title']+'”未采用视频，不能合成完整成片')
                clips.append(DBASE.asset(aid))
            payload['sources']=[x['id'] for x in clips]
        payload.update(prompt=prompt,referenceAssetIds=[x['id'] for x in refs],schema=schema.__name__ if schema else None)
        a=self.new_attempt(r,step,payload)
        if a['delivery_status']=='STORED':return
        try:
            response=a['response']
            if kind=='compose':
                asset=files.compose(clips,settings['audio']);self.store_asset(r,step,a,asset);return
            if not response and not a['remote_id']:
                if a['request_status'] in ('UNKNOWN','SUBMITTING'):raise model_api.RequestUnknown('原请求结果不明，禁止自动重发；请核对后显式新建尝试')
                if a['request_status']=='FAILED':raise ValueError('原请求已失败，请从界面显式重新生成该项')
                DBASE.attempt_update(a['id'],request_status='SUBMITTING')
                if schema:response=model_api.text(prompt,schema.model_json_schema())
                elif kind=='video':response=model_api.video(prompt,refs[0],{'resolution':settings['resolution'],'audio':settings['audio'],'seconds':target['seconds'],'ratio':settings['ratio']})
                else:response=model_api.image(prompt,refs,settings['ratio'] if kind in ('frame','reference') else '1:1')
                task=response.get('output',{}).get('task_id','')
                DBASE.attempt_update(a['id'],response=response,remote_id=task,request_status='RUNNING' if task else 'SUCCEEDED')
            if kind=='video':
                task=a['remote_id'] or response.get('output',{}).get('task_id')
                if not task:raise ValueError('接口没有返回视频任务编号，响应已保存，未自动重发')
                while not self.stop.is_set():
                    response=model_api.query(task);DBASE.attempt_update(a['id'],response=response)
                    state=response.get('output',{}).get('task_status')
                    if state=='SUCCEEDED':break
                    if state in ('FAILED','CANCELED'):raise model_api.Rejected('远端视频任务失败：'+str(response.get('output',{}).get('message','请检查输入'))[:200])
                    if state=='UNKNOWN':raise model_api.RequestUnknown('远端任务状态不明，已保存编号，可继续查询原任务')
                    self.stop.wait(10)
                if self.stop.is_set():return
                DBASE.attempt_update(a['id'],request_status='SUCCEEDED')
                url=response['output']['video_url'];raw=model_api.download(url);asset=files.ingest(raw,'镜头视频.mp4','MODEL',{'attemptId':a['id'],'model':config.VIDEO_MODEL})
                if settings['audio'] and not asset['meta']['hasAudio']:raise ValueError('请求有声视频但文件没有音轨，结果已保留，请选择重做或无声制作')
                self.store_asset(r,step,a,asset)
            elif schema:
                raw=response['choices'][0]['message']['content'];validated=schema.model_validate_json(raw).model_dump()
                if kind=='shots':self.validate_shots(validated['shots'],data['cards'])
                self.store_text(r,step,validated)
                DBASE.attempt_update(a['id'],request_status='SUCCEEDED',delivery_status='STORED')
            else:
                choices=response.get('output',{}).get('choices',[])
                content=choices[0]['message']['content'] if choices else []
                url=next((x['image'] for x in content if 'image' in x),None)
                if not url:raise ValueError('没有返回图片URL，原始响应已保存')
                DBASE.attempt_update(a['id'],delivery_status='DOWNLOADING')
                asset=files.ingest(model_api.download(url),'生成图片.png','MODEL',{'attemptId':a['id'],'model':config.IMAGE_MODEL,'remoteUrl':url,'remoteExpiresAt':time.time()+23*3600,'references':[x['id'] for x in refs]})
                self.store_asset(r,step,a,asset)
        except model_api.RequestUnknown as e:
            DBASE.attempt_update(a['id'],request_status='UNKNOWN',error=str(e));raise
        except model_api.Rejected as e:
            DBASE.attempt_update(a['id'],request_status='FAILED',error=str(e));raise
        except Exception as e:
            # Preserve known successful remote response so delivery can resume without paying again.
            latest=next(x for x in DBASE.attempts(r['id']) if x['id']==a['id'])
            DBASE.attempt_update(a['id'],delivery_status='RECOVERY_REQUIRED' if latest['response'] else 'INVALID',error=str(e)[:700]);raise
    def validate_shots(self,shots,cards):
        ids=[s['id'] for s in shots]
        if len(set(ids))!=len(ids):raise ValueError('镜头ID重复，请重新整理镜头清单')
        cardids={c['id'] for c in cards};before=set()
        for s in shots:
            if not set(s['referenceIds'])<=cardids:raise ValueError('模型引用了不存在的参考卡，下游未开始')
            if not set(s['dependsOn'])<=before:raise ValueError('镜头依赖不合法，下游未开始')
            before.add(s['id'])
    def store_text(self,r,step,value):
        def patch(d):
            if step['kind']=='script':
                parts=d.setdefault('scriptParts',[])
                if step['part']==0:parts.clear()
                while len(parts)<=step['part']:parts.append(None)
                parts[step['part']]=value
                d['invalidStages']=[x for x in d.get('invalidStages',[]) if x!='script']
                d['script']={'schemaVersion':1,'title':parts[0]['title'],'synopsis':'\n'.join(x['synopsis'] for x in parts if x),'scenes':[s for x in parts if x for s in x['scenes']],'warnings':[w for x in parts if x for w in x['warnings']]}
                d['sourceCoverage']={'processed':step['end'],'total':len(d['source']['text']),'complete':step['part']+1==step['total']}
            elif step['kind']=='cards':
                d['cards']=value['cards'];d['invalidStages']=[x for x in d.get('invalidStages',[]) if x!='cards'];d['analysisWarnings']=value['warnings']
            else:d['shots']=value['shots'];d['invalidStages']=[x for x in d.get('invalidStages',[]) if x!='shots'];d['analysisWarnings']=d.get('analysisWarnings',[])+value['warnings'];d['needsReview']=[s['id'] for s in value['shots'] if selected_asset(d,'video-'+s['id'])]
        DBASE.patch(r['draft'],patch)
    def store_asset(self,r,step,a,asset):
        def patch(d):
            k=step['kind'];auto=r['snapshot']['auto'];slot=step.get('slot') or ('ref-' if k=='reference' else 'frame-' if k=='frame' else 'video-')+step.get('target','')
            if k=='compose':
                d['exports'].append(asset['id']);return
            candidate(d,slot,asset,auto)
            if k=='video' and auto:d['needsReview']=[x for x in d.get('needsReview',[]) if x!=step['target']]
            if k=='reference' and auto:
                for c in d['cards']:
                    if c['id']==step['target']:c['assetId']=asset['id']
        DBASE.patch(r['draft'],patch);DBASE.attempt_update(a['id'],request_status='SUCCEEDED',delivery_status='STORED',asset_id=asset['id'],error='')
ENGINE=Executor()
