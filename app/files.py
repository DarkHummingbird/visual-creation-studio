import hashlib,io,json,os,subprocess,shutil,tempfile,zipfile
from pathlib import Path
from PIL import Image,ImageOps
from .config import DATA
from .db import DBASE

MAX_FILE=20_000_000

def atomic(path,raw):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_bytes(raw);os.replace(tmp,path)
    return path

def ingest(raw,name,origin='UPLOAD',meta=None):
    meta=meta or {};suffix=Path(name).suffix.lower()
    if len(raw)>MAX_FILE if suffix not in ('.mp4','.zip') else len(raw)>300_000_000:raise ValueError('文件超过允许大小')
    if suffix in ('.png','.jpg','.jpeg','.webp'):
        if len(raw)>16_000_000:raise ValueError('图片超过16MB，请先压缩或转换格式；原文件未修改')
        with Image.open(io.BytesIO(raw)) as im:
            if im.width*im.height>40_000_000:raise ValueError('图片像素过大，请缩小后上传')
            im.verify()
        with Image.open(io.BytesIO(raw)) as im:meta.update(width=im.width,height=im.height)
        kind='IMAGE'
    elif suffix=='.mp4':kind='VIDEO'
    elif suffix=='.zip':kind='EXPORT'
    else:kind='DOCUMENT'
    digest=hashlib.sha256(raw).hexdigest();path=DATA/'files'/(digest+suffix);atomic(path,raw)
    if kind=='VIDEO':meta.update(probe(path))
    return DBASE.add_asset(name,kind,path,origin,meta)

def probe(path):
    if not shutil.which('ffprobe'):raise ValueError('缺少ffprobe，无法验证视频文件')
    r=subprocess.run(['ffprobe','-v','error','-show_entries','stream=codec_type,codec_name,width,height,duration:format=duration','-of','json',str(path)],capture_output=True,text=True,timeout=30)
    if r.returncode:raise ValueError('视频不可解码')
    d=json.loads(r.stdout);video=next((x for x in d.get('streams',[]) if x.get('codec_type')=='video'),None)
    if not video:raise ValueError('文件没有视频流')
    return {'width':video['width'],'height':video['height'],'seconds':float(d['format']['duration']),'hasAudio':any(x.get('codec_type')=='audio' for x in d['streams']),'probe':d}

def extract(raw,name):
    if len(raw)>MAX_FILE:raise ValueError('单个文件最多20MB。请去除内嵌图片、导出TXT或按章节拆分后再导入。')
    suffix=Path(name).suffix.lower();warnings=[]
    if suffix in ('.txt','.md'):
        try:text=raw.decode('utf-8-sig')
        except UnicodeDecodeError:raise ValueError('编码不是UTF-8，请另存为UTF-8文本后导入')
    elif suffix=='.docx':
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            if sum(x.file_size for x in z.infolist())>100_000_000:raise ValueError('Word解压后过大，请导出纯文字')
            if any(x.filename.startswith('word/media/') for x in z.infolist()):warnings.append('Word包含图片，本步骤不识图，请在正文补充图片里的剧情。')
        from docx import Document
        d=Document(io.BytesIO(raw));parts=[]
        from docx.oxml.ns import qn
        from docx.table import Table
        from docx.text.paragraph import Paragraph
        for child in d.element.body:
            if child.tag==qn('w:p'):parts.append(Paragraph(child,d).text)
            elif child.tag==qn('w:tbl'):parts.extend('\t'.join(c.text for c in row.cells) for row in Table(child,d).rows)
        text='\n'.join(parts)
    elif suffix=='.pdf':
        from pypdf import PdfReader
        d=PdfReader(io.BytesIO(raw))
        if d.is_encrypted:raise ValueError('PDF已加密，请提供未加密副本或粘贴正文')
        pages=[];missing=[]
        for i,p in enumerate(d.pages):
            t=p.extract_text() or '';pages.append(t)
            if not t.strip():missing.append(i+1)
        text='\n\n'.join(pages)
        warnings.append('PDF只读取文字层，不识图；多栏、表格顺序可能有误，请核对正文。')
        if missing:warnings.append('以下页没有可读取正文：'+','.join(map(str,missing)))
        if not text.strip():raise ValueError('PDF没有文字层，本步骤不识图。请转为可复制正文或上传TXT。')
    else:raise ValueError('支持TXT、MD、DOCX、PDF；旧版DOC请另存为DOCX。')
    complete=len(text)<=200_000 and not (suffix=='.pdf' and bool(missing))
    if len(text)>200_000:warnings.append('正文超过200,000字符，保留提取结果供下载整理；请拆分章节后导入，暂不能生成。')
    return {'text':text,'characters':len(text),'warnings':warnings,'complete':complete}

def compose(assets,audio=True):
    if not assets:raise ValueError('请先生成并采用全部必要视频片段')
    ff=shutil.which('ffmpeg')
    if not ff:raise ValueError('缺少FFmpeg，请安装后重试合成')
    with tempfile.TemporaryDirectory(dir=DATA) as folder:
        folder=Path(folder);normalized=[]
        first=assets[0]['meta'];w=int(first['width']);h=int(first['height'])
        w-=w%2;h-=h%2
        for i,a in enumerate(assets):
            if audio and not a['meta'].get('hasAudio'):raise ValueError(f'片段{i+1}缺少音轨，请重做或主动选择无声模式')
            dst=folder/f'{i}.mp4'
            cmd=[ff,'-v','error','-y','-i',a['path'],'-vf',f'scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30','-c:v','libx264','-pix_fmt','yuv420p']
            cmd+=['-af','aresample=48000,asetpts=PTS-STARTPTS','-c:a','aac','-ac','2'] if audio else ['-an']
            cmd+=['-avoid_negative_ts','make_zero',str(dst)]
            r=subprocess.run(cmd,capture_output=True,timeout=300)
            if r.returncode:raise ValueError('片段标准化失败；原视频保留，可只重试合成')
            normalized.append(dst)
        from .concat_media import concat_scenes
        target=folder/'final.mp4';concat_scenes(normalized,target)
        return ingest(target.read_bytes(),'完整视频.mp4','COMPOSE',{'sources':[a['id'] for a in assets]})
