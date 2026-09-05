import os
import sys
import time
import json
import io
from html import unescape
from subprocess import Popen, PIPE
from http.client import IncompleteRead
from urllib.parse import urlsplit, urlunsplit

from ..lib.utils import request, traceback_error
from ..lib.exception import UnsupportedModel

from .base import Base
from .genai import GenAI
from .languages import google, gemini


load_translations()  # type: ignore


class GoogleFreeTranslateNew(Base):
    name = 'Google(Free)New'
    alias = 'Google (Free) - New'
    free = True
    lang_codes = Base.load_lang_codes(google)
    endpoint = 'https://translate-pa.googleapis.com/v1/translate'
    need_api_key = False

    def get_headers(self):
        return {
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'en-US,en;q=0.9',
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 '
            'Safari/537.36',
        }

    def get_body(self, text):
        self.method = 'GET'
        return {
            'params.client': 'gtx',
            'query.source_language': self._get_source_code(),
            'query.target_language': self._get_target_code(),
            'query.display_language': 'en-US',
            'data_types': 'TRANSLATION',
            # 'data_types': 'SENTENCE_SPLITS',
            # 'data_types': 'BILINGUAL_DICTIONARY_FULL',
            'key': 'AIzaSyDLEeFI5OtFBwYBIoK_jj5m32rZK5CkCXA',
            'query.text': text,
        }

    def get_result(self, response):
        return json.loads(response)['translation']


class GoogleFreeTranslateHtml(Base):
    name = 'Google(Free)Html'
    alias = 'Google (Free) - HTML'
    free = True
    lang_codes = Base.load_lang_codes(google)
    endpoint = 'https://translate-pa.googleapis.com/v1/translateHtml'
    need_api_key = False
    support_html = True

    def get_headers(self):
        return {
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'en-US,en;q=0.9',
            'Content-Type': 'application/json+protobuf',
            'X-Goog-Api-Key': 'AIzaSyATBXajvzQLTDHEQbcpq0Ihe0vWDHmO520',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 '
            'Safari/537.36',
        }

    def get_body(self, text):
        return json.dumps([
            [
                [text],
                self._get_source_code(),
                self._get_target_code()
            ],
            "wt_lib"
        ])

    def get_result(self, response):
        return json.loads(response)[0][0]


class GoogleFreeTranslate(Base):
    name = 'Google(Free)'
    alias = 'Google (Free) - Old'
    free = True
    lang_codes = Base.load_lang_codes(google)
    endpoint = 'https://translate.googleapis.com/translate_a/single'
    need_api_key = False

    def get_headers(self):
        return {
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'en-US,en;q=0.9',
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'DeepLBrowserExtension/1.3.0 Mozilla/5.0 (Macintosh;'
            ' Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)'
            ' Chrome/111.0.0.0 Safari/537.36',
        }

    def get_body(self, text):
        # The POST method is unstable, despite its ability to send more text.
        # However, it can be used occasionally with an unacceptable length.
        self.method = 'GET' if len(text) <= 1800 else 'POST'
        return {
            'client': 'gtx',
            'sl': self._get_source_code(),
            'tl': self._get_target_code(),
            'dt': 't',
            'dj': 1,
            'q': text,
        }

    def get_result(self, response):
        # return ''.join(i[0] for i in json.loads(data)[0])
        return ''.join(i['trans'] for i in json.loads(response)['sentences'])


class GoogleTranslate(Base):
    api_key_errors = ['429']
    api_key_cache: tuple[float, str | None] = (0.0, None)
    gcloud = None
    project_id = None
    using_tip = _(
        'This plugin uses Application Default Credentials (ADC) in your local '
        'environment to access your Google Translate service. To set up the '
        'ADC, follow these steps:\n'
        '1. Install the gcloud CLI by checking out its instructions {}.\n'
        '2. Run the command: gcloud auth application-default login.\n'
        '3. Sign in to your Google account and grant needed privileges.') \
        .format('<sup><a href="https://cloud.google.com/sdk/docs/install">[^]'
                '</a></sup>').replace('\n', '<br />')

    def _run_command(self, command, silence=False):
        error_msg = _('Cannot run the command "{}".').format(command)
        try:
            startupinfo = None
            # Prevent the popping console window on Windows.
            if sys.platform == 'win32':
                from subprocess import STARTUPINFO, STARTF_USESHOWWINDOW
                startupinfo = STARTUPINFO()
                startupinfo.dwFlags |= STARTF_USESHOWWINDOW
            process = Popen(
                command, stdout=PIPE, stderr=PIPE, universal_newlines=True,
                startupinfo=startupinfo)
        except Exception:
            if silence:
                return None
            error_msg += '\n\n%s' % traceback_error()
            raise Exception(error_msg)
        if process.wait() != 0:
            if silence:
                return None
            stderr = process.stderr
            error_msg += f'\n\n{stderr.read()}' if stderr is not None else ''
            raise Exception(error_msg)
        stdout = process.stdout
        return stdout.read().strip() if stdout is not None else ''

    def _get_gcloud_command(self):
        if self.gcloud is not None:
            return self.gcloud
        if sys.platform == 'win32':
            name = 'gcloud.cmd'
            which = 'where'
            base = r'google-cloud-sdk\bin\%s' % name
            paths = [
                r'"%s\Google\Cloud SDK\%s"'
                % (os.environ.get('programfiles(x86)'), base),
                r'"%s\AppData\Local\Google\Cloud SDK\%s"'
                % (os.environ.get('userprofile'), base)]
        else:
            name = 'gcloud'
            which = 'which'
            paths = ['/usr/local/bin/%s' % name]
        gcloud = self.get_external_program(name, paths)
        if gcloud is None:
            gcloud = self._run_command([which, name], silence=True)
            if gcloud is not None:
                gcloud = gcloud.split('\n')[0]
        if gcloud is None:
            raise Exception(_('Cannot find the command "{}".').format(name))
        self.gcloud = gcloud
        return gcloud

    def _get_project_id(self):
        if self.project_id is not None:
            return self.project_id
        self.project_id = self._run_command(
            [self._get_gcloud_command(), 'config', 'get', 'project'])
        return self.project_id

    def _get_credential(self):
        """The default lifetime of the API key is 3600 seconds. Once an
        available key is generated, it will be cached until it expired.
        """
        timestamp, old_api_key = self.api_key_cache
        if old_api_key is not None and time.time() - timestamp < 3600:
            return old_api_key
        # Temporarily add existing proxies.
        if self.proxy_uri:
            os.environ.update(
                http_proxy=self.proxy_uri, https_proxy=self.proxy_uri)
        new_api_key = self._run_command([
            self._get_gcloud_command(), 'auth', 'application-default',
            'print-access-token'])
        # Cleanse the proxies after use.
        for proxy in ('http_proxy', 'https_proxy'):
            if proxy in os.environ:
                del os.environ[proxy]
        self.api_key_cache = (time.time(), new_api_key)
        return new_api_key


class GoogleBasicTranslateADC(GoogleTranslate):
    name = 'Google(Basic)ADC'
    alias = 'Google (Basic) ADC'
    lang_codes = Base.load_lang_codes(google)
    endpoint = 'https://translation.googleapis.com/language/translate/v2'
    need_api_key = False

    def get_headers(self):
        return {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer %s' % self._get_credential(),
            'x-goog-user-project': self._get_project_id(),
        }

    def get_body(self, text):
        body = {
            'format': 'html',
            'model': 'nmt',
            'target': self._get_target_code(),
            'q': text
        }
        if not self._is_auto_lang():
            body.update(source=self._get_source_code())
        return json.dumps(body)

    def get_result(self, response):
        translations = json.loads(response)['data']['translations']
        return ''.join(unescape(i['translatedText']) for i in translations)


class GoogleBasicTranslate(GoogleTranslate):
    name = 'Google(Basic)'
    alias = 'Google (Basic)'
    lang_codes = Base.load_lang_codes(google)
    endpoint = 'https://translation.googleapis.com/language/translate/v2'
    api_key_hint = 'API key'
    need_api_key = True
    using_tip = None

    def get_headers(self):
        return {'Content-Type': 'application/x-www-form-urlencoded'}

    def get_body(self, text):
        body = {
            'key': self.api_key,
            'format': 'html',
            'model': 'nmt',
            'target': self._get_target_code(),
            'q': text
        }
        if not self._is_auto_lang():
            body.update(source=self._get_source_code())
        return body

    def get_result(self, response):
        translations = json.loads(response)['data']['translations']
        return ''.join(unescape(i['translatedText']) for i in translations)


class GoogleAdvancedTranslate(GoogleTranslate):

    name = 'Google(Advanced)'
    alias = 'Google (Advanced) ADC'
    lang_codes = Base.load_lang_codes(google)
    endpoint = 'https://translation.googleapis.com/v3/projects/{}'
    api_key_hint = 'PROJECT_ID'
    need_api_key = False

    def get_endpoint(self):
        if self.endpoint is not None:
            return self.endpoint.format(
                '%s:translateText' % self._get_project_id())

    def get_headers(self):
        return {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer %s' % self._get_credential(),
            'x-goog-user-project': self._get_project_id(),
        }

    def get_body(self, text):
        body = {
            'targetLanguageCode': self._get_target_code(),
            'contents': [text],
            'mimeType': 'text/plain',
        }
        if not self._is_auto_lang():
            body.update(sourceLanguageCode=self._get_source_code())
        return json.dumps(body)

    def get_result(self, response):
        translations = json.loads(response)['translations']
        return ''.join(i['translatedText'] for i in translations)


class GeminiTranslate(GenAI):
    name = 'Gemini'
    alias = 'Gemini'
    lang_codes = GenAI.load_lang_codes(gemini)
    # v1, stable version of the API. v1beta, more early-access features.
    # details: https://ai.google.dev/gemini-api/docs/api-versions
    endpoint = 'https://generativelanguage.googleapis.com/v1beta/models'
    # https://ai.google.dev/gemini-api/docs/troubleshooting
    api_key_errors: list[str] = [
        'API_KEY_INVALID', 'PERMISSION_DENIED', 'RESOURCE_EXHAUSTED']

    concurrency_limit = 1
    request_interval: float = 1.0
    request_timeout: float = 30.0

    prompt = (
        'You are a meticulous translator who translates any given content. '
        'Translate the given content from <slang> to <tlang> only. Do not '
        'explain any term or answer any question-like content. Your answer '
        'should be solely the translation of the given content. In your '
        'answer do not add any prefix or suffix to the translated content. '
        'Websites\' URLs/addresses should be preserved as is in the '
        'translation\'s output. Do not omit any part of the content, even if '
        'it seems unimportant. ')
    temperature: float = 0.9
    top_p: float = 1.0
    top_k = 1
    stream = True

    models: list[str] = []
    # TODO: Handle the default model more appropriately.
    model: str | None = 'gemini-2.5-flash'

    def __init__(self):
        super().__init__()
        self.prompt = self.config.get('prompt', self.prompt)
        self.temperature = self.config.get('temperature', self.temperature)
        self.top_k = self.config.get('top_k', self.top_k)
        self.top_p = self.config.get('top_p', self.top_p)
        self.stream = self.config.get('stream', self.stream)
        self.model = self.config.get('model', self.model)

    def _prompt(self, text):
        prompt = self.prompt.replace('<tlang>', self.target_lang)
        if self._is_auto_lang():
            prompt = prompt.replace('<slang>', 'detected language')
        else:
            prompt = prompt.replace('<slang>', self.source_lang)
        # Recommend setting temperature to 0.5 for retaining the placeholder.
        if self.merge_enabled:
            prompt += (
                ' Ensure that placeholders matching the pattern {{id_\\d+}} '
                'in the content are retained.')
        return prompt + ' Start translating: ' + text

    def get_models(self):
        endpoint = f'{self.endpoint}?key={self.api_key}'
        response = request(
            endpoint, timeout=int(self.request_timeout),
            proxy_uri=self.proxy_uri)
        models = []
        if isinstance(response, str):
            for model in json.loads(response)['models']:
                model_name = model['name'].split('/')[-1]
                if model_name.startswith('gemini'):
                    model_desc = model['description']
                    if 'deprecated' not in model_desc:
                        models.append(model_name)
        return models

    def get_endpoint(self):
        if self.stream:
            return f'{self.endpoint}/{self.model}:streamGenerateContent?' \
                f'alt=sse&key={self.api_key}'
        else:
            return f'{self.endpoint}/{self.model}:generateContent?' \
                f'key={self.api_key}'

    def get_headers(self):
        return {'Content-Type': 'application/json'}

    def get_body(self, text):
        return json.dumps({
            "contents": [
                {"role": "user", "parts": [{"text": self._prompt(text)}]},
            ],
            "generationConfig": {
                # "stopSequences": ["Test"],
                # "maxOutputTokens": 2048,
                "temperature": self.temperature,
                "topP": self.top_p,
                "topK": self.top_k,
            },
            "safetySettings": [
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_NONE"
                },
            ],
        })

    @staticmethod
    def extract_text(payload):
        parts = payload['candidates'][0]['content']['parts']
        return ''.join(
            part['text'] for part in parts
            if part.get('text') and not part.get('thought'))

    def get_result(self, response):
        if self.stream:
            return self._parse_stream(response)
        return self.extract_text(json.loads(response))

    def _parse_stream(self, response):
        while True:
            try:
                line = response.readline().decode('utf-8').strip()
            except IncompleteRead:
                continue
            except Exception as e:
                raise Exception(
                    _('Can not parse returned response. Raw data: {}')
                    .format(str(e)))
            if line.startswith('data:'):
                item = json.loads(line.split('data: ')[1])
                candidate = item['candidates'][0]
                content = candidate['content']
                if 'parts' in content.keys():
                    for part in content['parts']:
                        if part.get('text') and not part.get('thought'):
                            yield part['text']
                if candidate.get('finishReason') == 'STOP':
                    break


class GeminiBatchTranslate:
    """https://ai.google.dev/gemini-api/docs/batch-api"""
    alias = 'Gemini'
    provider = 'Google'
    docs_url = 'https://ai.google.dev/gemini-api/docs/batch-api'
    cache_prefix = 'gemini'
    inline_file_id = 'inline'
    inline_size_limit = 20 * 1024 * 1024
    _state_map = {
        'JOB_STATE_PENDING': 'pending',
        'JOB_STATE_RUNNING': 'in_progress',
        'JOB_STATE_SUCCEEDED': 'completed',
        'JOB_STATE_FAILED': 'failed',
        'JOB_STATE_CANCELLED': 'cancelled',
        'JOB_STATE_CANCELED': 'cancelled',
        'JOB_STATE_EXPIRED': 'expired',
        'BATCH_STATE_PENDING': 'pending',
        'BATCH_STATE_RUNNING': 'in_progress',
        'BATCH_STATE_SUCCEEDED': 'completed',
        'BATCH_STATE_FAILED': 'failed',
        'BATCH_STATE_CANCELLED': 'cancelled',
        'BATCH_STATE_CANCELED': 'cancelled',
        'BATCH_STATE_EXPIRED': 'expired',
    }

    def __init__(self, translator):
        self.translator = translator
        self.translator.stream = False
        self._inlined_requests = []
        self._latest = {}

        models_endpoint = (self.translator.endpoint or '').rstrip('/')
        if models_endpoint.endswith('/models'):
            self.api_base = models_endpoint[:-len('/models')]
            self.models_endpoint = models_endpoint
        else:
            self.api_base = models_endpoint or (
                'https://generativelanguage.googleapis.com/v1beta')
            self.models_endpoint = '%s/models' % self.api_base

        parts = urlsplit(self.api_base)
        self.upload_endpoint = urlunsplit((
            parts.scheme, parts.netloc,
            '/upload%s/files' % parts.path, '', ''))
        self.download_base = urlunsplit((
            parts.scheme, parts.netloc,
            '/download%s' % parts.path, '', ''))

    def supported_models(self):
        return self.translator.get_models()

    def headers(self, extra=None):
        headers = {
            'Content-Type': 'application/json',
            'x-goog-api-key': self.translator.api_key or '',
        }
        if extra:
            headers.update(extra)
        return headers

    def _ensure_prefix(self, name, prefix):
        if not name:
            return name
        if name.startswith('%s/' % prefix):
            return name
        return '%s/%s' % (prefix, name)

    def _batch_url(self, batch_id):
        return '%s/%s' % (
            self.api_base, self._ensure_prefix(batch_id, 'batches'))

    def _build_requests(self, paragraphs):
        inlined = []
        jsonl_lines = []
        for paragraph in paragraphs:
            body = json.loads(self.translator.get_body(paragraph.original))
            inlined.append({
                'request': body,
                'metadata': {'key': paragraph.md5},
            })
            jsonl_lines.append(json.dumps({
                'key': paragraph.md5,
                'request': body,
            }))
        return inlined, '\n'.join(jsonl_lines).encode('utf-8')

    def upload(self, paragraphs):
        """Prepare batch input. Small payloads are sent inline later; larger
        ones are uploaded as a JSONL file via the Gemini File API.
        """
        if self.translator.model not in self.supported_models():
            raise UnsupportedModel(
                'The model "{}" does not support batch functionality.'
                .format(self.translator.model))
        inlined, jsonl = self._build_requests(paragraphs)
        self._inlined_requests = inlined
        inline_body = json.dumps({
            'batch': {
                'display_name': 'ebook-translator',
                'input_config': {
                    'requests': {'requests': inlined},
                },
            }
        }).encode('utf-8')
        if len(inline_body) < self.inline_size_limit:
            return self.inline_file_id
        return self._upload_jsonl(jsonl)

    def _get_upload_url(self, response):
        if response is None or not hasattr(response, 'info'):
            raise Exception(_('Failed to start Gemini batch file upload.'))
        info = response.info()
        url = None
        if hasattr(info, 'get'):
            url = info.get('X-Goog-Upload-URL') or info.get('x-goog-upload-url')
        if not url:
            raise Exception(_('Failed to start Gemini batch file upload.'))
        return url.strip()

    def _upload_jsonl(self, payload):
        start_headers = self.headers({
            'X-Goog-Upload-Protocol': 'resumable',
            'X-Goog-Upload-Command': 'start',
            'X-Goog-Upload-Header-Content-Length': str(len(payload)),
            'X-Goog-Upload-Header-Content-Type': 'application/json',
        })
        start_response = request(
            self.upload_endpoint,
            json.dumps({'file': {'display_name': 'ebook-translator-batch'}}),
            start_headers, 'POST', proxy_uri=self.translator.proxy_uri,
            raw_object=True)
        upload_url = self._get_upload_url(start_response)
        upload_headers = {
            'x-goog-api-key': self.translator.api_key or '',
            'Content-Length': str(len(payload)),
            'X-Goog-Upload-Offset': '0',
            'X-Goog-Upload-Command': 'upload, finalize',
        }
        response = request(
            upload_url, payload, upload_headers, 'POST',
            proxy_uri=self.translator.proxy_uri)
        data = json.loads(response)
        file_info = data.get('file') or data
        file_id = file_info.get('name')
        if not file_id:
            raise Exception(_('Failed to upload Gemini batch input file.'))
        return file_id

    def create(self, file_id):
        if file_id == self.inline_file_id:
            body = json.dumps({
                'batch': {
                    'display_name': 'ebook-translator',
                    'input_config': {
                        'requests': {
                            'requests': self._inlined_requests or [],
                        }
                    }
                }
            })
        else:
            body = json.dumps({
                'batch': {
                    'display_name': 'ebook-translator',
                    'input_config': {
                        'file_name': file_id,
                    }
                }
            })
        response = request(
            '%s/%s:batchGenerateContent' % (
                self.models_endpoint, self.translator.model),
            body, self.headers(), 'POST',
            proxy_uri=self.translator.proxy_uri)
        return json.loads(response).get('name')

    def check(self, batch_id):
        response = request(
            self._batch_url(batch_id),
            headers=self.headers(),
            proxy_uri=self.translator.proxy_uri)
        data = json.loads(response)
        self._latest = data
        return self._normalize_batch_info(data)

    def _normalize_batch_info(self, data):
        metadata = data.get('metadata') or {}
        state = data.get('state') or metadata.get('state') or ''
        if isinstance(state, dict):
            state = state.get('name') or ''
        status = self._state_map.get(state)
        if status is None:
            if data.get('error') or metadata.get('error'):
                status = 'failed'
            elif data.get('done') is True:
                status = 'completed'
            elif data.get('done') is False:
                status = 'in_progress'
            else:
                status = state or 'unknown'

        dest = data.get('dest') or {}
        output = data.get('output') or data.get('response') or {}
        output_file_id = (
            dest.get('fileName') or dest.get('file_name')
            or output.get('responsesFile') or output.get('responses_file')
            or output.get('fileName') or output.get('file_name'))

        stats = (
            data.get('batchStats') or data.get('batch_stats')
            or metadata.get('batchStats') or metadata.get('batch_stats')
            or {})
        request_counts = {
            'total': int(
                stats.get('requestCount') or stats.get('request_count') or 0),
            'completed': int(
                stats.get('successfulRequestCount')
                or stats.get('successful_request_count') or 0),
            'failed': int(
                stats.get('failedRequestCount')
                or stats.get('failed_request_count') or 0),
        }
        return {
            'status': status,
            'output_file_id': output_file_id,
            'request_counts': request_counts,
            'errors': (
                data.get('error') or data.get('errors')
                or metadata.get('error')),
        }

    def retrieve(self, output_file_id):
        if output_file_id and output_file_id != self.inline_file_id:
            return self._retrieve_file(output_file_id)
        return self._retrieve_inlined(self._latest or {})

    def _iter_inlined(self, data):
        dest = data.get('dest') or {}
        output = data.get('output') or data.get('response') or {}
        items = dest.get('inlinedResponses') or dest.get('inlined_responses')
        if items is None:
            nested = (
                output.get('inlinedResponses')
                or output.get('inlined_responses'))
            if isinstance(nested, dict):
                items = (
                    nested.get('inlinedResponses')
                    or nested.get('inlined_responses'))
            else:
                items = nested
        return items or []

    def _result_item(self, item):
        if not isinstance(item, dict):
            return None, None
        key = item.get('key')
        metadata = item.get('metadata') or {}
        if key is None:
            key = metadata.get('key')
        response = item.get('response')
        if not response:
            return key, None
        try:
            return key, GeminiTranslate.extract_text(response)
        except (KeyError, IndexError, TypeError):
            return key, None

    def _retrieve_inlined(self, data):
        translations = {}
        for item in self._iter_inlined(data):
            key, text = self._result_item(item)
            if key and text:
                translations[key] = text
        return translations

    def _retrieve_file(self, file_id):
        file_name = self._ensure_prefix(file_id, 'files')
        headers = self.headers()
        del headers['Content-Type']
        response = request(
            '%s/%s:download?alt=media' % (self.download_base, file_name),
            headers=headers, raw_object=True,
            proxy_uri=self.translator.proxy_uri)
        payload = response.read() if hasattr(response, 'read') else response
        if isinstance(payload, str):
            payload = payload.encode('utf-8')

        translations = {}
        for line in io.BytesIO(payload):
            if not line.strip():
                continue
            key, text = self._result_item(json.loads(line))
            if key and text:
                translations[key] = text
        return translations

    def cancel(self, batch_id):
        request(
            '%s:cancel' % self._batch_url(batch_id),
            headers=self.headers(), method='POST',
            proxy_uri=self.translator.proxy_uri)
        return True

    def delete(self, file_id):
        if not file_id or file_id == self.inline_file_id:
            return True
        request(
            '%s/%s' % (
                self.api_base, self._ensure_prefix(file_id, 'files')),
            headers=self.headers(), method='DELETE',
            proxy_uri=self.translator.proxy_uri)
        return True
