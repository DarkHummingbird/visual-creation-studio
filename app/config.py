import os, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for line in (ROOT/'.env').read_text().splitlines() if (ROOT/'.env').exists() else []:
    if '=' in line and not line.lstrip().startswith('#'):
        k,v=line.split('=',1);os.environ.setdefault(k.strip(),v.strip().strip('\"\''))
DATA=Path(os.getenv('STUDIO_DATA_DIR',str(ROOT/'data'))).resolve();DATA.mkdir(parents=True,exist_ok=True)
ALI_BASE=os.getenv('DASHSCOPE_BASE_URL','https://cn-beijing.maas.qianwenaiapi.com/api/v1').rstrip('/')
DEEP_BASE=os.getenv('DEEPSEEK_BASE_URL','https://api.deepseek.com').rstrip('/')
TEXT_MODEL=os.getenv('DEEPSEEK_MODEL','deepseek-flash')
IMAGE_MODEL='qwen-image-3.0';VIDEO_MODEL='wan3.0-video-prime'
def status():
    return {'text':{'model':TEXT_MODEL,'configured':bool(os.getenv('DEEPSEEK_API_KEY'))},'image':{'model':IMAGE_MODEL,'configured':bool(os.getenv('DASHSCOPE_API_KEY'))},'video':{'model':VIDEO_MODEL,'configured':bool(os.getenv('DASHSCOPE_API_KEY'))},'ffmpeg':bool(shutil.which('ffmpeg')),'ffprobe':bool(shutil.which('ffprobe')),'actualCosts':{'implemented':False,'value':None,'label':'未接入'}}
