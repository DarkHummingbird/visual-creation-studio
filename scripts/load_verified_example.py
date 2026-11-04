"""Import existing verified API artifacts. Does not invoke any model."""
import json,time
from pathlib import Path
from app.db import DBASE,uid
from app import config,files
from app.workflow import ENGINE
from app.schemas import StartRun
source=config.ROOT/'.work/api-smoke/2026-11-05'
if not (source/'cup-video.mp4').exists():raise SystemExit('Existing API test media unavailable; no fixture invented')
if any(d['name']=='白瓷杯 · 已验证素材续作' for d in DBASE.drafts()):raise SystemExit('Example already imported; no duplicate')
image=files.ingest((source/'cup.png').read_bytes(),'接口验证 · 白瓷杯.png','IMPORTED_API_TEST',{'model':config.IMAGE_MODEL,'source':'2026-11-05真实接口测试'})
video=files.ingest((source/'cup-video.mp4').read_bytes(),'接口验证 · 白瓷杯有声片段.mp4','IMPORTED_API_TEST',{'model':config.VIDEO_MODEL,'source':'2026-11-05真实接口测试'})
d=DBASE.create('drama','白瓷杯 · 已验证素材续作');data=d['data'];data['step']=6;data['source']={'text':'自然光照亮木桌上的白瓷杯，镜头缓慢推近。','type':'script','complete':True,'warnings':[],'note':'文字为手工示例；图片视频来自已验证的API测试，不是本次新生成。'}
data['settings'].update(ratio='1:1',targetSeconds=5)
data['script']={'schemaVersion':1,'title':'白瓷杯','synopsis':'木桌上的白瓷杯，镜头缓慢推近。','scenes':[{'schemaVersion':1,'title':'杯子','location':'室内木桌','time':'午后','action':'镜头缓慢推近','dialogue':''}],'warnings':[]}
data['shots']=[{'schemaVersion':1,'id':'cup-shot','title':'白瓷杯 · 缓慢推近','prompt':'木桌上的白瓷杯，自然光','action':'缓慢推近杯子','dialogue':'','speakerId':'','camera':'缓慢推进','seconds':5,'referenceIds':[],'startState':'杯子在桌上','endState':'杯子在桌上','dependsOn':[]}]
data['candidates']={'frame-cup-shot':[image['id']],'video-cup-shot':[video['id']]};data['adoptions']={'frame-cup-shot':image['id'],'video-cup-shot':video['id']};data['exampleNotice']='此草稿复用2026-11-05已验证接口测试的真实图片与视频；文字为手工示例。可验证采用、合成、导出，不代表本次重新生成或完整一键模型实测。'
DBASE.patch(d['id'],lambda x:x.update(data))
r=ENGINE.submit(d['id'],StartRun(kind='compose',mutationId=uid(),baseVersion=1))
print('Example imported; composition scheduled:',r['id'],'(start the local service to execute)')
