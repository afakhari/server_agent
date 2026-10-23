"""Static repository readiness inspection. Never runs untrusted repository code."""
import json,re,hashlib
from pathlib import Path

IGNORE={'.git','node_modules','venv','.venv','dist','build','__pycache__','.next'}

def inspect_repo(folder):
    folder=Path(folder).resolve()
    if not folder.is_dir():raise ValueError('پوشه پروژه پیدا نشد')
    # Limit inspection, avoid symlinks, read only relevant small manifest files.
    manifest_names=['package.json','requirements.txt','pyproject.toml','composer.json','Dockerfile','liara.json','.env.example','Procfile']
    sources={}
    for n in manifest_names:
        p=folder/n
        if p.is_file() and not p.is_symlink() and p.stat().st_size<=100_000:
            sources[n]=p.read_text(encoding='utf8',errors='replace')
    if not sources:raise ValueError('هیچ فایل پیکربندی پشتیبانی‌شده‌ای پیدا نشد')
    framework='نامشخص'; platform='نامشخص';port=None; warnings=[]
    try:
        package=json.loads(sources.get('package.json','{}'))
    except json.JSONDecodeError:
        package={};warnings.append('package.json نامعتبر است')
    deps={**package.get('dependencies',{}),**package.get('devDependencies',{})} if isinstance(package,dict) else {}
    if 'next' in deps:framework='Next.js';platform='node'
    elif 'express' in deps:framework='Express.js';platform='node'
    elif 'package.json' in sources:framework='Node.js';platform='node'
    pyfile=sources.get('requirements.txt','')+'\n'+sources.get('pyproject.toml','')
    if re.search(r'\bfastapi\b',pyfile,re.I):framework='FastAPI';platform='python'
    elif re.search(r'\bdjango\b',pyfile,re.I):framework='Django';platform='python'
    elif 'requirements.txt' in sources and platform=='نامشخص':framework='Python';platform='python'
    if 'composer.json' in sources:framework='PHP/Composer';platform='php'
    if 'Dockerfile' in sources:platform='docker'
    cfg={}
    if 'liara.json' in sources:
        try:cfg=json.loads(sources['liara.json'])
        except json.JSONDecodeError:warnings.append('liara.json نامعتبر است')
    if isinstance(cfg,dict):
        # Config is advisory, not blindly trusted for live commands.
        cport=cfg.get('port')
        if isinstance(cport,int) and 1<=cport<=65535:port=cport
    if port is None:warnings.append('پورت سرویس تأیید نشده؛ قبل از دیپلوی باید مشخص شود')
    envkeys=[]
    if '.env.example' in sources:
        envkeys=sorted({m.group(1) for line in sources['.env.example'].splitlines() if (m:=re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=',line))})
    if 'DATABASE_URL' in envkeys:warnings.append('اتصال پایگاه داده موردنیاز به نظر می‌رسد؛ تنظیم آن باید توسط مالک پروژه انجام شود')
    if not envkeys:warnings.append('فایل .env.example موجود نیست؛ متغیرهای لازم را با توسعه‌دهنده بررسی کنید')
    hashes=[f'{name}:{hashlib.sha256(content.encode()).hexdigest()}' for name,content in sorted(sources.items())]
    stamp=hashlib.sha256('|'.join(hashes).encode()).hexdigest()
    return {'framework':framework,'platform':platform,'port':port,'manifest_files':list(sources),
      'required_env_names':envkeys,'warnings':warnings,'readiness':'needs-review' if warnings else 'ready-for-review',
      'fingerprint':stamp,'cost_status':'قیمت و شناسه پلن باید هنگام اجرا از منبع معتبر تأیید شود',
      'can_deploy_automatically':False,
      'reason':'این مرحله فقط تحلیل ایستای سورس است؛ بدون کنترل پلن/توکن/تأیید امکان دیپلوی ندارد'}

def repo_from_workspace(relative):
    import os
    root=os.getenv('SENTINEL_WORKSPACE')
    if not root:raise ValueError('SENTINEL_WORKSPACE تنظیم نشده است')
    base=Path(root).expanduser().resolve()
    path=(base/relative).resolve()
    if not path.is_relative_to(base):raise ValueError('مسیر خارج از فضای کاری مجاز است')
    return path
