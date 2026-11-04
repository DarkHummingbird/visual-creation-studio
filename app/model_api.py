import base64,json,os,mimetypes,time,urllib.request,urllib.error
from pathlib import Path
from . import config
class RequestUnknown(Exception):pass
class Rejected(Exception):pass

def request(url,key,body=None,async_=False):
    # curl handles large inline reference uploads consistently on macOS. No retries.
    import subprocess,tempfile
    if any(x in key for x in ('\n','\r','"')):raise Rejected('密钥格式不合法')
    config_text='header = "Authorization: Bearer '+key+'"\nheader = "Content-Type: application/json"\n'
    if async_:config_text+='header = "X-DashScope-Async: enable"\n'
    path=None
    try:
        cmd=['curl','--silent','--show-error','--retry','0','--connect-timeout','20','--max-time','240','--config','-','--write-out','\n%{http_code}',url]
        if body is not None:
            with tempfile.NamedTemporaryFile(mode='w',suffix='.json',dir=config.DATA,delete=False) as f:
                json.dump(body,f,ensure_ascii=False);path=Path(f.name)
            cmd.extend(['--data-binary','@'+str(path)])
        p=subprocess.run(cmd,input=config_text.encode(),capture_output=True,timeout=250)
        if p.returncode:raise RequestUnknown(f'连接异常（curl {p.returncode}），远端执行结果不明；不会自动重发。')
        raw,code=p.stdout.rsplit(b'\n',1);status=int(code)
        try:result=json.loads(raw)
        except Exception:raise RequestUnknown('模型返回无法解析的响应，已停止后续提交，不自动重发') from None
        if status>=400:
            error=result.get('code') or result.get('error',{}).get('code') or str(status)
            raise Rejected(f'模型服务返回HTTP {status}（{error}）。请检查权限、额度或参数；未自动重试。')
        return result
    except subprocess.TimeoutExpired:raise RequestUnknown('请求等待超时，远端结果不明；不会自动重发') from None
    finally:
        if path:path.unlink(missing_ok=True)

def key(name):
    value=os.getenv(name,'')
    if not value:raise Rejected('请在本地.env配置 '+name+' 后重启服务')
    return value

def dataurl(asset):
    remote=asset.get('meta',{}).get('remoteUrl')
    if remote and asset.get('meta',{}).get('remoteExpiresAt',0)>time.time():return remote
    p=Path(asset['path']);raw=p.read_bytes()
    if len(raw)>10_000_000:raise Rejected('参考图超过接口安全限制10MB，请压缩后另存为新素材')
    return 'data:'+(mimetypes.guess_type(p.name)[0] or 'image/png')+';base64,'+base64.b64encode(raw).decode()

def text(prompt,schema):
    return request(config.DEEP_BASE+'/chat/completions',key('DEEPSEEK_API_KEY'),{'model':config.TEXT_MODEL,'messages':[{'role':'system','content':'你是视觉创作工作台的编剧与制作助理。仅返回符合指定JSON Schema的JSON对象。不要省略原文关键剧情，不编造商品事实。所有ID必须稳定且引用有效。Schema:'+json.dumps(schema,ensure_ascii=False)},{'role':'user','content':prompt}],'response_format':{'type':'json_object'},'max_tokens':8000})

def image(prompt,assets,ratio):
    if len(assets)>3:raise Rejected('Qwen-Image-3.0最多3张参考图，请选择或拆镜')
    content=[{'image':dataurl(a)} for a in assets]+[{'text':prompt}]
    size={'16:9':'1536*864','9:16':'864*1536','1:1':'1024*1024'}.get(ratio,'1024*1024')
    return request(config.ALI_BASE+'/services/aigc/multimodal-generation/generation',key('DASHSCOPE_API_KEY'),{'model':config.IMAGE_MODEL,'input':{'messages':[{'role':'user','content':content}]},'parameters':{'size':size,'n':1,'prompt_extend':True}})

def video(prompt,asset,settings):
    media=[{'type':'first_frame','url':dataurl(asset)}]
    ratio={'16:9':'16:9','9:16':'9:16','1:1':'1:1'}.get(settings.get('ratio'),'adaptive')
    return request(config.ALI_BASE+'/services/aigc/video-generation/video-synthesis',key('DASHSCOPE_API_KEY'),{'model':config.VIDEO_MODEL,'input':{'prompt':prompt,'media':media},'parameters':{'resolution':settings['resolution'],'ratio':ratio,'duration':settings['seconds'],'audio':settings['audio']}},async_=True)

def query(task):return request(config.ALI_BASE+'/tasks/'+task,key('DASHSCOPE_API_KEY'))

def download(url):
    if not url.startswith('https://'):raise ValueError('模型返回非HTTPS媒体地址，未下载')
    with urllib.request.urlopen(url,timeout=180) as r:
        raw=r.read(300_000_001)
    if len(raw)>300_000_000:raise ValueError('生成文件超过300MB，下载停止')
    return raw
