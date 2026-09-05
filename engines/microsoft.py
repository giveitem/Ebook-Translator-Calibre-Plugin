import json
import base64
import uuid
from datetime import datetime
from urllib.parse import urlencode

from calibre.utils.localization import _  # type: ignore

from ..lib.utils import request

from .base import Base
from .languages import microsoft
from .openai import ChatgptTranslate


load_translations()  # type: ignore


class MicrosoftEdgeTranslate(Base):
    name = 'MicrosoftEdge(Free)'
    alias = 'Microsoft Edge (Free)'
    free = True
    lang_codes = Base.load_lang_codes(microsoft)
    endpoint = 'https://edge.microsoft.com/translate/translatetext'
    need_api_key = False
    access_info = None

    def get_endpoint(self):
        query = {
            'isEnterpriseClient': False,
            'to': self._get_target_code(),
        }
        if not self._is_auto_lang():
            query['from'] = self._get_source_code()
        return '%s?%s' % (self.endpoint, urlencode(query))

    def get_headers(self):
        return {
            'Content-Type': 'application/json',
        }

    def get_body(self, text):
        return json.dumps([text])

    def get_result(self, response):
        return json.loads(response)[0]['translations'][0]['text']


class MicrosoftFoundryTranslate(Base):
    name = 'Microsoft(Foundry)'
    alias = 'Microsoft Foundry Translator'
    lang_codes = Base.load_lang_codes(microsoft)
    endpoint = 'https://api.cognitive.microsofttranslator.com'
    api_key_hint = _('API key, API key|region, or API key|region|endpoint')
    api_key_pattern = r'^[^\s|]+(\|[^\s|]+){0,2}$'
    api_key_errors = [
        '401', '403', 'InvalidSubscriptionKey',
        'Ocp-Apim-Subscription-Key']
    using_tip = _(
        'For regional or multi-service Foundry resources, enter each key as '
        '{}. For resources that require a custom endpoint, use {}. For global '
        'Translator resources, enter only the API key.'
    ).format('KEY|REGION', 'KEY|REGION|ENDPOINT')

    def __init__(self):
        super().__init__()
        self.endpoint = self.config.get('endpoint', self.endpoint)

    def _get_api_key_parts(self):
        parts = (self.api_key or '').split('|', 2)
        key = parts[0]
        region = parts[1] if len(parts) > 1 else None
        endpoint = parts[2] if len(parts) > 2 else None
        return key, region, endpoint

    def _get_translate_endpoint(self, endpoint):
        endpoint = endpoint.rstrip('/')
        if endpoint.endswith('/translate'):
            return endpoint
        lower_endpoint = endpoint.lower()
        if 'cognitiveservices.azure.com' in lower_endpoint \
                and '/translator/text/v3.0' not in lower_endpoint:
            endpoint = '%s/translator/text/v3.0' % endpoint
        return '%s/translate' % endpoint

    def get_endpoint(self):
        _, _, endpoint = self._get_api_key_parts()
        query = {
            'api-version': '3.0',
            'to': self._get_target_code(),
        }
        if not self._is_auto_lang():
            query['from'] = self._get_source_code()
        return '%s?%s' % (
            self._get_translate_endpoint(endpoint or self.endpoint),
            urlencode(query))

    def get_headers(self):
        api_key, region, _ = self._get_api_key_parts()
        headers = {
            'Content-Type': 'application/json; charset=UTF-8',
            'Ocp-Apim-Subscription-Key': api_key,
            'X-ClientTraceId': str(uuid.uuid4()),
        }
        if region:
            headers['Ocp-Apim-Subscription-Region'] = region
        return headers

    def get_body(self, text):
        return json.dumps([{'Text': text}])

    def get_result(self, response):
        return json.loads(response)[0]['translations'][0]['text']


class AzureChatgptTranslate(ChatgptTranslate):
    name = 'ChatGPT(Azure)'
    alias = 'ChatGPT (Azure)'
    endpoint = (
        'https://{your-resource-name}.openai.azure.com/openai/deployments/'
        '{deployment-id}/chat/completions?api-version={api-version}')

    def get_headers(self):
        return {
            'Content-Type': 'application/json',
            'api-key': self.api_key
        }

    def get_body(self, text):
        body = {
            'stream': self.stream,
            'messages': [
                {'role': 'system', 'content': self.get_prompt()},
                {'role': 'user', 'content': text}
            ]
        }
        sampling_value = getattr(self, self.sampling)
        body.update({self.sampling: sampling_value})
        return json.dumps(body)
