"""Client for interacting with the LLM provider via OpenRouter/OpenAI.

This module encapsulates all logic related to counting tokens, trimming
conversation history, performing single or multi‑message completions
and moderation checks. Following Clean Code principles, each method
has a descriptive name and handles one well‑defined task.
"""

import json
from typing import Any, Dict, List, Optional

import requests
import tiktoken

from .config import Config


class LLMClient:
    MAX_TOKENS: int = 50_000

    def __init__(self, config: Config) -> None:
        self.config = config
        self.session = requests.Session()
        self.encoder = tiktoken.encoding_for_model('gpt-4o')

    def _post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        proxies = None
        if self.config.proxy_url:
            proxies = {'http': self.config.proxy_url, 'https': self.config.proxy_url}
        resp = self.session.post(
            self.config.ai_endpoint,
            json=payload,
            headers={
                'Authorization': f'Bearer {self.config.operouter_key}',
                'Content-Type': 'application/json',
            },
            proxies=proxies,
            timeout=(self.config.connect_timeout, self.config.read_timeout),
        )
        resp.raise_for_status()
        return resp.json()

    def _count_tokens(self, message: Dict[str, str]) -> int:
        return len(self.encoder.encode(message['role'])) + len(self.encoder.encode(message['content'])) + 4

    def _trim(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        total = sum(self._count_tokens(m) for m in messages)
        if total <= self.MAX_TOKENS:
            return messages
        sys_msg, other = messages[0], messages[1:]
        while total > self.MAX_TOKENS and other:
            removed = other.pop(0)
            total -= self._count_tokens(removed)
        return [sys_msg] + other

    def call_single(self, user_message: str, system_message: Optional[str] = None) -> Dict[str, Any]:
        messages: List[Dict[str, str]] = []
        if system_message:
            messages.append({'role': 'system', 'content': system_message})
        messages.append({'role': 'user', 'content': user_message})
        payload = {
            'model': self.config.ai_model,
            'messages': messages,
            'models': self.config.ai_models_fallback,
        }
        data = self._post(payload)
        content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {'content': content}

    def call_conversation(self, messages: List[Dict[str, str]], system_message: Optional[str] = None) -> Dict[str, Any]:
        msgs: List[Dict[str, str]] = []
        if system_message:
            msgs.append({'role': 'system', 'content': system_message})
        msgs.extend(messages)
        payload = {
            'model': self.config.ai_model,
            'messages': msgs,
            'models': self.config.ai_models_fallback,
        }
        data = self._post(payload)
        content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {'content': content}

    def call_with_tools(self, messages: List[Dict[str, str]], tools: List[Dict[str, Any]]) -> str:
        trimmed = self._trim(messages.copy())
        payload = {
            'model': self.config.ai_model,
            'messages': trimmed,
            'tools': tools,
            'tool_choice': 'auto',
            'models': self.config.ai_models_fallback,
        }
        data = self._post(payload)
        choice = data.get('choices', [{}])[0].get('message', {})
        return choice.get('content', '')

    def moderation_flagged(self, text: str) -> bool:
        if not self.config.openai_api_key:
            return False
        url = 'https://api.openai.com/v1/moderations'
        headers = {
            'Authorization': f'Bearer {self.config.openai_api_key}',
            'Content-Type': 'application/json',
        }
        payload = {'input': text, 'model': 'omni-moderation-latest'}
        proxies = None
        if self.config.proxy_url:
            proxies = {'http': self.config.proxy_url, 'https': self.config.proxy_url}
        resp = self.session.post(url, headers=headers, json=payload, proxies=proxies, timeout=(self.config.connect_timeout, self.config.read_timeout))
        resp.raise_for_status()
        data = resp.json()
        return data.get('results', [{}])[0].get('flagged', False)