import io,json,time
from pathlib import Path
from unittest.mock import Mock
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from app import db,files,workflow,main,model_api
from app.schemas import StartRun

@pytest.fixture
def setup(tmp_path,monkeypatch):
    store=db.DB(tmp_path);monkeypatch.setattr(files,'DATA',tmp_path)
    for m in [db,files,workflow,main]:monkeypatch.setattr(m,'DBASE',store)
    monkeypatch.setenv('DASHSCOPE_API_KEY','test-fixture');monkeypatch.setenv('DEEPSEEK_API_KEY','test-fixture')
    return store,workflow.Executor(),TestClient(main.app)
def pic():
    b=io.BytesIO();Image.new('RGB',(128,128),'white').save(b,format='PNG');return b.getvalue()
def card():return {'schemaVersion':1,'id':'char1','kind':'CHARACTER','name':'青','description':'短发蓝衣','voice':'轻柔','characterId':'person1','lookVersionId':'look1','assetId':''}
def shot():return {'schemaVersion':1,'id':'shot1','title':'递信','prompt':'短发蓝衣女孩递信','action':'递信','dialogue':'你好','speakerId':'person1','camera':'固定','seconds':5,'referenceIds':['char1'],'startState':'信在手中','endState':'信已递出','dependsOn':[]}
def script():return {'schemaVersion':1,'title':'信','synopsis':'递信','scenes':[{'schemaVersion':1,'title':'递信','location':'书店','time':'午后','action':'递信','dialogue':'你好'}],'warnings':[]}
def test_save_conflict_idempotency_and_export(setup):
    st,e,c=setup;d=st.create('ecommerce','杯子');data=d['data'];data['product']['name']='马克杯'
    payload={'baseVersion':1,'mutationId':'mutation-111','data':data}
    assert c.put('/api/v1/drafts/'+d['id'],json=payload).status_code==200
    assert c.put('/api/v1/drafts/'+d['id'],json=payload).json()['version']==2
    payload['mutationId']='mutation-222';assert c.put('/api/v1/drafts/'+d['id'],json=payload).status_code==409
    a=files.ingest(pic(),'杯子.png');st.patch(d['id'],lambda x:x['exports'].append(a['id']))
    r=c.get('/api/v1/drafts/'+d['id']+'/export');assert r.status_code==200 and r.content.startswith(b'PK')
    assert c.get('/api/v1/costs').json()['actual'] is None

def test_import_limits_formats(setup):
    st,e,c=setup
    r=c.post('/api/v1/import',files={'file':('a.md','你好世界'.encode(),'text/plain')});assert r.json()['text']=='你好世界'
    assert c.post('/api/v1/import',files={'file':('a.doc',b'123','application/octet-stream')}).status_code==400
    with pytest.raises(ValueError):files.extract(b'a'*20000001,'a.txt')
    r=files.extract(('a'*200001).encode(),'a.txt');assert not r['complete'] and len(r['text'])==200001
    from docx import Document
    doc=Document();doc.add_paragraph('故事');doc.add_table(rows=1,cols=1).cell(0,0).text='表格正文';buf=io.BytesIO();doc.save(buf)
    assert '表格正文' in files.extract(buf.getvalue(),'x.docx')['text']

def test_no_duplicate_unknown(setup,monkeypatch):
    st,e,c=setup;d=st.create('ecommerce','杯子');a=files.ingest(pic(),'原片.png');d['data']['product']['skus']=[{'id':'sku1','name':'白色','refs':[a['id']]}];st.patch(d['id'],lambda x:x.update(d['data']))
    request=Mock(side_effect=model_api.RequestUnknown('connection reset'));monkeypatch.setattr(model_api,'image',request)
    r=e.submit(d['id'],StartRun(kind='ecommerce',baseVersion=1,mutationId='create-run-1',paidConsent=True))
    with pytest.raises(model_api.RequestUnknown):e.execute(r['id'])
    with pytest.raises(model_api.RequestUnknown):e.execute(r['id'])
    assert request.call_count==1
    st.update_run(r['id'],status='UNKNOWN')
    with pytest.raises(ValueError):e.control(r['id'],'resume')

def test_oneclick_all_stages_and_audio(setup,monkeypatch):
    st,e,c=setup;d=st.create('drama','信');d['data']['source']['text']='女孩递信';st.patch(d['id'],lambda x:x.update(d['data']))
    def text(prompt,schema):
        name=schema['title'];value=script() if name=='Script' else {'schemaVersion':1,'cards':[card()],'warnings':[]} if name=='Cards' else {'schemaVersion':1,'shots':[shot()],'warnings':[]}
        return {'choices':[{'message':{'content':json.dumps(value,ensure_ascii=False)}}]}
    monkeypatch.setattr(model_api,'text',text)
    img=Mock(return_value={'output':{'choices':[{'message':{'content':[{'image':'https://example.test/image.png'}]}}]}});monkeypatch.setattr(model_api,'image',img)
    monkeypatch.setattr(model_api,'video',Mock(return_value={'output':{'task_id':'remote-test'}}))
    monkeypatch.setattr(model_api,'query',Mock(return_value={'output':{'task_status':'SUCCEEDED','video_url':'https://example.test/video.mp4'}}))
    evidence=Path('.work/api-smoke/2026-11-05/cup-video.mp4').read_bytes()
    monkeypatch.setattr(model_api,'download',lambda u:evidence if 'video' in u else pic())
    r=e.submit(d['id'],StartRun(kind='oneclick',mutationId='oneclick-1',baseVersion=1,paidConsent=True));e.execute(r['id'])
    out=st.draft(d['id'])['data'];assert out['exports'] and out['adoptions']['video-shot1'];assert st.asset(out['exports'][0])['meta']['hasAudio']
    assert img.call_count==2
    assert all(a['delivery_status']=='STORED' for a in st.attempts(r['id']))
    e.execute(r['id']);assert img.call_count==2

def test_delivery_retry_does_not_regenerate(setup,monkeypatch):
    st,e,c=setup;d=st.create('drama','参考');st.patch(d['id'],lambda x:x.update({'cards':[card()]}))
    img=Mock(return_value={'output':{'choices':[{'message':{'content':[{'image':'https://example.test/a.png'}]}}]}});monkeypatch.setattr(model_api,'image',img)
    dl=Mock(side_effect=[OSError('disk full'),pic()]);monkeypatch.setattr(model_api,'download',dl)
    r=e.submit(d['id'],StartRun(kind='references',mutationId='reference-1',baseVersion=1,paidConsent=True))
    with pytest.raises(OSError):e.execute(r['id'])
    e.execute(r['id']);assert img.call_count==1;assert st.draft(d['id'])['data']['candidates']['ref-char1']

def test_reference_limit_and_pause_releases_slot(setup):
    st,e,c=setup;d=st.create('drama','参考');st.patch(d['id'],lambda x:x.update({'cards':[card()]}))
    r=e.submit(d['id'],StartRun(kind='references',mutationId='run-1111',baseVersion=1,paidConsent=True))
    with pytest.raises(db.Conflict):e.submit(d['id'],StartRun(kind='references',mutationId='run-2222',baseVersion=1,paidConsent=True))
    e.control(r['id'],'pause');e.execute(r['id']);assert st.run(r['id'])['status']=='PAUSED'
    d2=st.create('drama','参考2');st.patch(d2['id'],lambda x:x.update({'cards':[card()]}))
    assert e.submit(d2['id'],StartRun(kind='references',mutationId='run-3333',baseVersion=1,paidConsent=True))
    bad=shot();bad['referenceIds']=['a','b','c','d']
    from pydantic import ValidationError
    with pytest.raises(ValidationError):workflow.schemas.Shot.model_validate(bad)

def test_long_paste_persists_txt_and_upstream_invalidates(setup):
    st,e,c=setup;d=st.create('drama','长文');data=d['data'];data['source']['text']='文'*5001
    p={'baseVersion':1,'mutationId':'long-save-1','data':data}
    r=c.put('/api/v1/drafts/'+d['id'],json=p);assert r.status_code==200
    assert st.draft(d['id'])['data']['source']['textAssetId']
    assert c.put('/api/v1/drafts/'+d['id'],json=p).status_code==200
    d=st.draft(d['id']);assert 'script' in d['data']['invalidStages']
    steps=workflow.initial_steps(d,'oneclick',[],{});assert steps[0]['kind']=='script'

def test_cross_origin_and_cost_stub(setup):
    st,e,c=setup
    assert c.post('/api/v1/drafts',json={'scene':'drama','name':'x'},headers={'Origin':'https://example.com'}).status_code==403
    result=c.get('/api/v1/costs').json();assert result['actual'] is None and result['implemented'] is False

def test_video_resume_queries_original_without_post(setup,monkeypatch):
    st,e,c=setup;d=st.create('drama','续做');a=files.ingest(pic(),'frame.png');s=shot();s['referenceIds']=[]
    st.patch(d['id'],lambda x:x.update({'shots':[s],'adoptions':{'frame-shot1':a['id']}}))
    post=Mock(return_value={'output':{'task_id':'known-task'}});monkeypatch.setattr(model_api,'video',post)
    query=Mock(side_effect=[model_api.RequestUnknown('network'),{'output':{'task_status':'SUCCEEDED','video_url':'https://example.test/v.mp4'}}]);monkeypatch.setattr(model_api,'query',query)
    monkeypatch.setattr(model_api,'download',lambda u:Path('.work/api-smoke/2026-11-05/cup-video.mp4').read_bytes())
    r=e.submit(d['id'],StartRun(kind='videos',mutationId='video-resume-1',baseVersion=1,paidConsent=True))
    with pytest.raises(model_api.RequestUnknown):e.execute(r['id'])
    st.update_run(r['id'],status='UNKNOWN');e.control(r['id'],'resume');e.execute(r['id'])
    assert post.call_count==1 and query.call_count==2
    assert st.draft(d['id'])['data']['candidates']['video-shot1']

def test_clearing_warnings_keeps_downstream_valid(setup):
    st,e,c=setup;d=st.create('drama','清警告')
    s=script();s['warnings']=['剧情跳跃需确认']
    st.patch(d['id'],lambda x:x.update({'script':s,'analysisWarnings':['参考数量提示'],'cards':[card()],'shots':[shot()]}))
    data=st.draft(d['id'])['data'];data['script']={**data['script'],'warnings':[]};data['analysisWarnings']=[]
    r=c.put('/api/v1/drafts/'+d['id'],json={'baseVersion':1,'mutationId':'clear-warn-1','data':data})
    assert r.status_code==200
    saved=st.draft(d['id'])['data'];assert saved['invalidStages']==[] and saved['needsReview']==[]
    data['script']={**data['script'],'title':'改名后的标题'}
    r=c.put('/api/v1/drafts/'+d['id'],json={'baseVersion':2,'mutationId':'clear-warn-2','data':data})
    assert set(st.draft(d['id'])['data']['invalidStages'])=={'cards','shots','media'}

def test_video_ratio_comes_from_settings(setup,monkeypatch):
    st,e,c=setup
    body={}
    monkeypatch.setattr(model_api,'dataurl',lambda a:'data:image/png;base64,xx')
    monkeypatch.setattr(model_api,'request',lambda url,k,b,async_=False:body.update(b) or {'output':{}})
    model_api.video('提示',Path('frame.png'),{'resolution':'480P','audio':True,'seconds':5,'ratio':'9:16'})
    assert body['parameters']['ratio']=='9:16'
    body.clear()
    model_api.video('提示',Path('frame.png'),{'resolution':'480P','audio':True,'seconds':5})
    assert body['parameters']['ratio']=='adaptive'

def test_copy_suggestions_uses_text_model(setup,monkeypatch):
    st,e,c=setup
    def fake_text(prompt,schema):
        assert '陶瓷马克杯' in prompt and schema['properties']['suggestions']
        return {'choices':[{'message':{'content':json.dumps({'suggestions':['手工烧制 温暖如初','今日下单 立减十元','一杯子 一辈子','新品首发 限时包邮','会议室的颜值担当']},ensure_ascii=False)}}]}
    monkeypatch.setattr(model_api,'text',fake_text)
    r=c.post('/api/v1/copy-suggestions',json={'name':'陶瓷马克杯','description':'高温陶瓷'})
    assert r.status_code==200 and len(r.json()['suggestions'])==5
    assert c.post('/api/v1/copy-suggestions',json={'description':'无名称'}).status_code==400
