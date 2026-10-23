"""Official Liara PaaS API adapter. Never return env values to clients or models."""
import os
import re
import time
import httpx

class LiaraError(Exception):
    pass

NAME = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]{0,62}$')

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
    def __init__(self, token=None, transport=None):
        self.token = token or os.environ.get('LIARA_API_TOKEN', '')
        if not self.token:
            raise LiaraError('توکن لیارا در سرور تنظیم نشده است')
        self.http = httpx.Client(base_url='https://api.liara.ir', timeout=10,
            headers={'Authorization': f'Bearer {self.token}', 'Accept': 'application/json'},
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
            raise LiaraError(f'Liara HTTP {exc.response.status_code}') from exc
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
