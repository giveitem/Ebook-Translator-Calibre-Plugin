import json

from .openai import ChatgptTranslate

load_translations()  # type: ignore


class DeepseekTranslate(ChatgptTranslate):
    name = 'DeepSeek'
    alias = 'DeepSeek (Chat)'
    endpoint = 'https://api.deepseek.com/v1/chat/completions'
    temperature = 1.3

    concurrency_limit = 0
    request_interval = 0.0

    models: list[str] = [
        'deepseek-chat', 'deepseek-reasoner',
        'deepseek-v4-flash', 'deepseek-v4-pro']
    model: str | None = models[0]

    # Thinking mode is enabled by default per DeepSeek API.
    # https://api-docs.deepseek.com/guides/thinking_mode
    thinking = True

    def __init__(self):
        super().__init__()
        self.model = self.config.get('model', self.model)
        self.thinking = self.config.get('thinking', self.thinking)

    def get_models(self):
        return self.models

    def get_body(self, text):
        body = json.loads(super().get_body(text))
        body['thinking'] = {
            'type': 'enabled' if self.thinking else 'disabled'
        }
        return json.dumps(body)
