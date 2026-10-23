"""Evidence-first diagnosis. No model controls privileged operations."""
import re
from datetime import datetime, timezone

SECRET_PATTERNS = [
    (re.compile(r'(?i)(bearer\s+)[A-Za-z0-9._~+/=-]{8,}'), r'\1[REDACTED]'),
    (re.compile(r'(?i)((?:password|secret|token|api[_-]?key)\s*[=:]\s*)[^\s,;]+'), r'\1[REDACTED]'),
    (re.compile(r'(?i)(postgres(?:ql)?|mysql|redis)://[^\s@]+@'), r'\1://[REDACTED]@'),
    (re.compile(r'(?i)((?:DATABASE_URL|REDIS_URL)\s*=\s*)[^\s,;]+'), r'\1[REDACTED]'),
]

def redact(value):
    s = str(value)
    for pattern, substitute in SECRET_PATTERNS:
        s = pattern.sub(substitute, s)
    return s[:2500]


def evidence(snapshot):
    out=[]
    def add(kind, text, source):
        out.append({'id': f'E{len(out)+1}', 'kind':kind, 'text':redact(text), 'source':source})
    app = snapshot.get('project') or {}
    add('status', f"سرویس: {app.get('status', 'نامشخص')}؛ deployed={app.get('isDeployed', 'نامشخص')}", 'GET /v1/projects/{name}')
    for line in (snapshot.get('logs') or [])[-25:]:
        msg=line.get('message','') if isinstance(line,dict) else line
        if msg: add('log', msg, 'GET /v1/projects/{name}/logs')
    releases=snapshot.get('releases') or {}
    for release in (releases.get('releases') or [])[:3]:
        add('release', f"نسخه {release.get('tag') or release.get('_id','?')}، وضعیت {release.get('state','?')}، زمان {release.get('createdAt','?')}", 'GET /v1/projects/{name}/releases')
    for event in (snapshot.get('events') or [])[-4:]:
        add('event', str(event)[:400], 'GET /v1/projects/{name}/events')
    for metric in ['cpu_pct','memory_pct']:
        v=(snapshot.get('derived_metrics') or {}).get(metric)
        if v is not None: add('metric', f'{metric}: {v} (با منشأ {snapshot.get("metric_origin","نامشخص")})', 'GET /v1/projects/{name}/metrics/summary')
    return out


def diagnose(snapshot):
    ev=evidence(snapshot)
    log_text='\n'.join(x['text'].lower() for x in ev if x['kind']=='log')
    hypotheses=[]
    def hypothesis(code, title, confidence, reason, keys, action=None):
        hypotheses.append({'code':code,'title':title,'confidence':confidence,'reason':reason,'evidence_ids':keys,'action':action})
    log_ids=[x['id'] for x in ev if x['kind']=='log']
    release_ids=[x['id'] for x in ev if x['kind']=='release']
    metric_ids=[x['id'] for x in ev if x['kind']=='metric']
    status_ids=[x['id'] for x in ev if x['kind']=='status']
    env_pat=r'(missing (?:env|environment|variable)|keyerror|undefined environment|database_url.*not (?:set|found)|configurationerror)'
    if re.search(env_pat,log_text):
        hypothesis('missing_config','پیکربندی یا متغیر محیطی ناقص', 'بالا', 'الگوی خطای پیکربندی در لاگ مشاهده شد. قبل از هر تغییر، وجود کلیدها و مقداردهی امن بررسی شود.', log_ids, 'manual_env')
    if re.search(r'(out of memory|oomkilled|memoryerror|allocation failed|heap out of memory)',log_text):
        hypothesis('oom','کمبود حافظه یا نشت حافظه', 'بالا', 'پیام کمبود حافظه در لاگ وجود دارد؛ بررسی اندازه پلن، مصرف حافظه و الگوی بار ضروری است.',log_ids + metric_ids,'manual_memory')
    mem = (snapshot.get('derived_metrics') or {}).get('memory_pct')
    if isinstance(mem,(int,float)) and mem>90 and not any(h['code']=='oom' for h in hypotheses):
        hypothesis('memory_pressure','فشار حافظه', 'متوسط', 'مصرف حافظه بالا گزارش شده است اما علت افزایش مصرف هنوز مشخص نیست.',metric_ids,'manual_memory')
    if re.search(r'(econnrefused|connection refused|could not connect|connect etimedout)',log_text):
        hypothesis('dependency','اختلال در اتصال به سرویس وابسته', 'متوسط', 'اتصال برنامه به وابستگی ناموفق بوده است؛ امکان مشکل پایگاه داده یا شبکه وجود دارد.', log_ids, 'manual_dependency')
    if re.search(r'(temporary failure|transient error|worker crashed|uncaught exception)',log_text) and not hypotheses:
        hypothesis('transient','خرابی احتمالی فرایند اجرایی', 'متوسط', 'نشانه خرابی موقتی پردازش دیده می‌شود. ری‌استارت می‌تواند اقدام موقت باشد، اما علت بنیادی را لزوماً حل نمی‌کند.', log_ids + status_ids,'restart')
    if re.search(r'(500 internal server error|http 500|status=500)',log_text) and not hypotheses:
        hypothesis('http500','خطای HTTP 500 با علت نامشخص', 'پایین', 'خطا ثبت شده ولی برای تعیین علت به شواهد بیشتری نیاز است.',log_ids,'investigate')
    # A release coinciding with error logs is a clue, not evidence of causality.
    # Live responses expose createdAt and datetime per Liara OpenAPI; no timing is inferred
    # when either source lacks a parseable timestamp.
    def parse_timestamp(value):
        if not isinstance(value, str): return None
        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
            return parsed if parsed.tzinfo else None
        except ValueError: return None
    release_history = (snapshot.get('releases') or {}).get('releases') or []
    release_times = [parse_timestamp(x.get('createdAt')) for x in release_history[:5] if isinstance(x, dict)]
    log_times = [parse_timestamp(x.get('datetime')) for x in (snapshot.get('logs') or [])[-25:] if isinstance(x, dict)]
    error_log = bool(re.search(r'(http 500|internal server error|traceback|error|exception|crashed|oomkilled)', log_text))
    temporal_match = error_log and any(
        release_time and log_time and 0 <= (log_time - release_time).total_seconds() <= 1800
        for release_time in release_times for log_time in log_times
    )
    if (snapshot.get('suspected_recent_change') or temporal_match) and release_ids:
        hypothesis('release_correlation','هم‌زمانی احتمالی خطا با انتشار اخیر', 'پایین', 'زمان‌بندی انتشار و اختلال ظاهراً نزدیک است؛ هم‌زمانی به‌تنهایی علت را اثبات نمی‌کند.',release_ids + log_ids,'manual_rollback')
    if not hypotheses:
        hypothesis('insufficient','شاهد کافی برای تشخیص قطعی وجود ندارد', 'نامشخص', 'شواهد فعلی برای نتیجه‌گیری کافی نیست. برای رفع ابهام باید داده بیشتری جمع‌آوری شود.',status_ids,'investigate')
    prior={'بالا':0,'متوسط':1,'پایین':2,'نامشخص':3}
    hypotheses.sort(key=lambda h:prior[h['confidence']])
    top=hypotheses[0]
    proposals=[]
    # Never restart a currently healthy/running service solely because of an old log.
    unhealthy_status = str((snapshot.get('project') or {}).get('status','')).lower() in {'crashed','failed','error','unhealthy','stopped'}
    if top['action']=='restart' and unhealthy_status:
        proposals.append({'operation':'restart','title':'ری‌استارت کنترل‌شده سرویس','risk':'متوسط','impact':'قطع یا اختلال کوتاه احتمالی؛ علت بنیادی ممکن است پابرجا بماند','reversible':False,'requires_approval':True,'reason':top['reason']})
    recommendations={
      'manual_env':'کلیدهای متغیرهای محیطی را با نیازمندی‌های پروژه تطبیق دهید. مقدار محرمانه را در گزارش وارد نکنید.',
      'manual_memory':'مصرف منابع را در بازه زمانی طولانی‌تر بررسی کنید؛ افزایش پلن را تنها پس از بررسی نشت حافظه و هزینه پیشنهاد دهید.',
      'manual_dependency':'سلامت پایگاه داده، اعتبارنامه‌ها، شبکه و timeout اتصال را مستقل بررسی کنید.',
      'manual_rollback':'گزینه بازگشت به نسخه قبلی را در کنسول/CLI بررسی کنید؛ API مستند برای فعال‌سازی نسخه قدیمی در این MVP تأیید نشده است.',
      'investigate':'داده دقیق‌تر از خطا، پاسخ HTTP، لاگ برنامه و وضعیت وابستگی‌ها جمع‌آوری کنید.'
    }
    return {'project':snapshot.get('name'), 'mode':snapshot.get('mode','unknown'), 'hypotheses':hypotheses,'evidence':ev,
            'proposals':proposals, 'recommendation': recommendations.get(top['action'],'از افزایش بی‌دلیل منابع یا تغییرات پرریسک پرهیز شود.'),
            'limitations':snapshot.get('limitations',[]), 'investigated_at':datetime.now(timezone.utc).isoformat(),
            'verdict': 'شواهد اولیه وجود دارد' if top['confidence']!='نامشخص' else 'نیازمند داده بیشتر'}


def mock_snapshot(scenario='transient'):
    baseline={'name':'demo-shop','mode':'demo','project':{'status':'running','isDeployed':True,'planID':'demo-plan'},
              'logs':[],'releases':{'currentRelease':'v3','releases':[{'tag':'v3','state':'ready','createdAt':'demo T+00'},{'tag':'v2','state':'ready','createdAt':'demo T-1h'}]},
              'events':[],'derived_metrics':{},'metric_origin':'داده مصنوعی سناریو','limitations':['داده‌های این سناریو شبیه‌سازی‌شده‌اند و نتیجه اجرای واقعی روی لیارا نیست.']}
    cases={
      'transient': {'project':{'status':'crashed','isDeployed':True},'logs':[{'message':'2026-10-23 12:30:01 ERROR worker crashed: transient error in request handler'},{'message':'2026-10-23 12:30:04 HTTP 500 internal server error'}]},
      'env': {'project':{'status':'crashed','isDeployed':True},'logs':[{'message':'KeyError: DATABASE_URL - missing environment variable'},{'message':'HTTP 500 internal server error'}], 'suspected_recent_change':True},
      'memory': {'project':{'status':'running','isDeployed':True},'logs':[{'message':'worker terminated: OOMKilled - out of memory'}],'derived_metrics':{'memory_pct':96.4,'cpu_pct':38.0}},
      'release':{'project':{'status':'crashed','isDeployed':True},'logs':[{'message':'HTTP 500 internal server error'}], 'suspected_recent_change':True},
      'healthy':{'project':{'status':'running','isDeployed':True},'logs':[{'message':'GET /health 200 OK'}]},
    }
    if scenario not in cases: raise ValueError('سناریوی ناشناخته')
    update=cases[scenario]
    baseline['project'].update(update.get('project',{}))
    for k,v in update.items():
        if k!='project':baseline[k]=v
    return baseline
