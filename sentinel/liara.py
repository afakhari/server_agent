"""Official Liara PaaS API adapter. Never return env values to clients or models."""
import os
import re
import time
import httpx

class LiaraError(Exception):
    pass

NAME = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]{0,62}$')
TEAM_ID = re.compile(r'^[A-Za-z0-9_-]{6,80}$')

def validate_team_id(value):
    """Accept a constrained team identifier; CLI uses ?teamID=<id>."""
    if value is None or value == '':
        return ''
    if isinstance(value, str) and value.strip().upper() in {
        'TEAM_ID', 'YOUR_TEAM_ID', 'YOUR_REAL_TEAM_ID',
        'TEAM_ID_FROM_CONSOLE', 'YOUR_TEAM_ID_FROM_CONSOLE'
    }:
        raise LiaraError(
            'TEAM_ID صرفاً مثال است؛ شناسه واقعی تیم را از پایین صفحه API کنسول لیارا جایگزین کنید')
    if not isinstance(value, str) or not TEAM_ID.fullmatch(value):
        raise LiaraError('شناسه تیم نامعتبر است؛ آن را از صفحه API همان تیم کپی کنید')
    return value

def validate_name(name):
    if not NAME.fullmatch(str(name)):
        raise LiaraError('شناسه پروژه معتبر نیست')
    return str(name)

def safe_project(payload):
    if not isinstance(payload, dict):
        raise LiaraError('پاسخ پروژه معتبر نیست')
    allowed = {'_id', 'project_id', 'name', 'type', 'status', 'isDeployed', 'scale', 'planID', 'created_at', 'zeroDowntime', 'defaultSubdomain', 'hourlyPrice'}
    return {k: v for k, v in payload.items() if k in allowed}

class LiaraClient:
    def __init__(self, token=None, transport=None, team_id=None):
        self.token = token or os.environ.get('LIARA_API_TOKEN', '')
        if not self.token:
            raise LiaraError('توکن لیارا در سرور تنظیم نشده است')
        # Fixed operator-selected team scope; never accept a team ID from a model
        # or browser request. httpx client params are merged into every read/write.
        self.team_id = validate_team_id(
            os.environ.get('LIARA_TEAM_ID', '') if team_id is None else team_id)
        self.http = httpx.Client(base_url='https://api.liara.ir', timeout=10,
            headers={'Authorization': f'Bearer {self.token}', 'Accept': 'application/json'},
            params={'teamID': self.team_id} if self.team_id else {},
            transport=transport, follow_redirects=False, trust_env=False)

    def close(self):
        self.http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def request(self, method, path, **kwargs):
        try:
            response = self.http.request(method, path, **kwargs)
            response.raise_for_status()
            if len(response.content) > 1_500_000:
                raise LiaraError('حجم پاسخ API بیش از سقف مجاز است')
            return response.json() if response.content else {}
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            # Expose only the endpoint path and HTTP status, never token or response body.
            route = str(exc.request.url.path)
            if status == 404 and method.upper() == 'GET' and route.startswith('/v1/projects/'):
                hint = '؛ برنامه در حساب متصل پیدا نشد. نام را از فهرست برنامه‌های قابل دسترسی انتخاب کنید'
            elif status == 404 and route == '/v1/projects':
                hint = '؛ فهرست برنامه‌ها هم 404 برگرداند: مسیر API/دسترسی حساب نیاز به بررسی دارد'
            else:
                hint = ''
            raise LiaraError(f'Liara HTTP {status}: {method.upper()} {route}{hint}') from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise LiaraError(f'اختلال ارتباط یا پاسخ نامعتبر ({type(exc).__name__})') from exc

    def list_projects(self):
        response = self.request('GET', '/v1/projects')
        if not isinstance(response, dict) or not isinstance(response.get('projects'), list):
            raise LiaraError('ساختار فهرست پروژه‌ها نامعتبر است')
        return {'projects': [safe_project(p) for p in response['projects'][:100]]}

    def get_project(self, name):
        response = self.request('GET', f'/v1/projects/{validate_name(name)}')
        if not isinstance(response, dict) or not isinstance(response.get('project'), dict):
            raise LiaraError('ساختار پروژه نامعتبر است')
        return safe_project(response['project'])

    def logs(self, name):
        data = self.request('GET', f'/v1/projects/{validate_name(name)}/logs', params={'since': str(int(time.time()) - 3600)})
        if not isinstance(data, list):
            raise LiaraError('ساختار لاگ معتبر نیست')
        return data[-80:]

    def events(self, name):
        data = self.request('GET', f'/v1/projects/{validate_name(name)}/events', params={'start': int(time.time()) - 3600})
        if not isinstance(data, dict) or not isinstance(data.get('data'), list):
            raise LiaraError('ساختار رویدادها نامعتبر است')
        return data['data'][-40:]

    def releases(self, name):
        data = self.request('GET', f'/v1/projects/{validate_name(name)}/releases', params={'page': 1, 'count': 10})
        if not isinstance(data, dict) or not isinstance(data.get('releases'), list):
            raise LiaraError('ساختار انتشارها نامعتبر است')
        return data

    def metrics(self, name):
        data = self.request('GET', f'/v1/projects/{validate_name(name)}/metrics/summary')
        if not isinstance(data, dict):
            raise LiaraError('ساختار متریک‌ها نامعتبر است')
        return data

    def domains(self, name):
        """Read domains for one project; expose a strictly nonsecret shape."""
        data = self.request('GET', '/v1/domains', params={'project': validate_name(name)})
        if not isinstance(data, dict) or not isinstance(data.get('domains'), list):
            raise LiaraError('ساختار دامنه‌ها نامعتبر است')
        return {'domains': [self._safe_domain(row) for row in data['domains'][:50]]}

    @staticmethod
    def _safe_domain(row):
        if not isinstance(row, dict):
            raise LiaraError('ساختار دامنه نامعتبر است')
        allowed = ('_id', 'name', 'type', 'status', 'certificatesStatus',
                   'CNameRecord', 'redirectTo', 'redirectStatus')
        return {key: row[key] for key in allowed if key in row}

    def check_domain(self, domain_id):
        if not re.fullmatch(r'[A-Za-z0-9_-]{8,80}', str(domain_id)):
            raise LiaraError('شناسه دامنه معتبر نیست')
        data = self.request('GET', '/v1/domains/' + domain_id + '/check')
        if not isinstance(data, dict) or not isinstance(data.get('domain'), dict):
            raise LiaraError('پاسخ بررسی دامنه معتبر نیست')
        return {'domain': self._safe_domain(data['domain'])}

    def restart(self, name):
        return self.request('POST', f'/v1/projects/{validate_name(name)}/actions/restart')

    def snapshot(self, name):
        name = validate_name(name)
        project = self.get_project(name)
        result = {'name': name, 'mode': 'live', 'project': project,
                  'logs': [], 'events': [], 'releases': {}, 'raw_metrics': {},
                  'derived_metrics': {}, 'metric_origin': 'unknown', 'limitations': []}
        for key, function in [('logs', self.logs), ('events', self.events),
                              ('releases', self.releases), ('raw_metrics', self.metrics)]:
            try:
                result[key] = function(name)
            except LiaraError as exc:
                result['limitations'].append(f'{key}: {exc}')
        # Never pretend API raw values are percentages without validated plan limits.
        return result
