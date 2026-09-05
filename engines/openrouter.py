import json
from urllib.parse import urlsplit

from ..lib.utils import request

from .openai import ChatgptTranslate


load_translations()  # type: ignore


class OpenRouterTranslate(ChatgptTranslate):
    name = 'OpenRouter'
    alias = 'OpenRouter'
    endpoint = 'https://openrouter.ai/api/v1/chat/completions'
    # https://openrouter.ai/docs/api/reference/overview
    api_key_errors = ['401', 'unauthorized', 'quota', '402']

    concurrency_limit = 1
    request_interval = 1.0
    request_timeout = 60.0

    models: list[str] = []
    model: str | None = 'openai/gpt-4o'

    def get_headers(self):
        headers = super().get_headers()
        headers.update({
            'HTTP-Referer': 'https://translator.bookfere.com',
            'X-Title': 'Ebook Translator',
        })
        return headers


class OpenRouterBatchTranslate:
    """https://openrouter.ai/docs/batch-quickstart"""
    alias = 'OpenRouter'
    provider = 'OpenRouter'
    docs_url = 'https://openrouter.ai/docs/batch-quickstart'
    cache_prefix = 'openrouter'
    inline_file_id = 'inline'

    def __init__(self, translator):
        self.translator = translator
        self.translator.stream = False
        self._requests = []
        self._latest = {}

        parts = urlsplit(self.translator.endpoint or '', 'https')
        origin = '%s://%s' % (parts.scheme or 'https', parts.netloc)
        self.batch_endpoint = '%s/api/beta/batches' % origin

    @staticmethod
    def matches(translator):
        endpoint = getattr(translator, 'endpoint', None) or ''
        return 'openrouter.ai' in endpoint.lower()

    def supported_models(self):
        return self.translator.get_models()

    def headers(self, extra=None):
        headers = self.translator.get_headers()
        if extra:
            headers.update(extra)
        return headers

    def upload(self, paragraphs):
        """Prepare inline batch requests. OpenRouter does not use file upload.
        https://openrouter.ai/docs/batch-quickstart
        """
        requests = []
        for paragraph in paragraphs:
            body = json.loads(self.translator.get_body(paragraph.original))
            body.pop('stream', None)
            requests.append({
                'custom_id': paragraph.md5,
                'body': body,
            })
        self._requests = requests
        return self.inline_file_id

    def create(self, file_id):
        # endpoint and model must appear before requests for stream parsing.
        payload = {
            'endpoint': '/v1/chat/completions',
            'model': self.translator.model,
            'completion_window': '24h',
            'requests': self._requests or [],
        }
        response = request(
            self.batch_endpoint, json.dumps(payload), self.headers(), 'POST',
            proxy_uri=self.translator.proxy_uri)
        return json.loads(response).get('id')

    def check(self, batch_id):
        response = request(
            '%s/%s' % (self.batch_endpoint, batch_id),
            headers=self.headers(),
            proxy_uri=self.translator.proxy_uri)
        data = json.loads(response)
        self._latest = data
        return data

    def retrieve(self, output_file_id):
        results = (self._latest or {}).get('results') or []
        translations = {}
        for item in results:
            custom_id = item.get('custom_id')
            response_item = item.get('response') or {}
            if response_item.get('status_code') not in (None, 200):
                continue
            body = response_item.get('body')
            if not custom_id or not body:
                continue
            try:
                content = self.translator.get_result(
                    body if isinstance(body, str) else json.dumps(body))
            except Exception:
                continue
            if content:
                translations[custom_id] = content
        return translations

    def cancel(self, batch_id):
        request(
            '%s/%s/cancel' % (self.batch_endpoint, batch_id),
            headers=self.headers(), method='POST',
            proxy_uri=self.translator.proxy_uri)
        return True

    def delete(self, file_id):
        return True
