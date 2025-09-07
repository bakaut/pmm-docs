# Standard library imports
import json
import logging
from typing import List, Dict, Any

# Third-party imports
import requests

# Local imports
from .config import Config
from .utils import Utils


class LLMManager:
    """Менеджер для работы с LLM API"""

    def __init__(self, config: Config, utils: Utils, logger: logging.Logger):
        self.config = config
        self.utils = utils
        self.logger = logger

        # Извлекаем настройки из конфига
        self.ai_model = config.ai_model
        self.ai_models_fallback = config.ai_models_fallback
        self.ai_endpoint = config.ai_endpoint
        self.operouter_key = config.operouter_key
        self.openai_api_key = config.openai_api_key
        self.fallback_answer = config.fallback_answer
        self.tools = config.llm_tools
        self.timeout = (config.connect_timeout, config.read_timeout)
        self.proxy = config.proxy
        self.proxy_url = config.proxy_url
        self.read_timeout = config.read_timeout

    def check_proxy(self, proxy_url: str, timeout: int = None, test_url: str = None) -> bool:
        """
        Проверяет работоспособность HTTP/HTTPS прокси, отправляя запрос на test_url.
        Возвращает True, если прокси работает, иначе False.
        """
        if timeout is None:
            timeout = self.read_timeout
        if test_url is None:
            test_url = self.config.proxy_test_url

        try:
            response = requests.get(test_url, proxies=self.proxy, timeout=timeout)
            response.raise_for_status()
            return True
        except Exception as e:
            self.logger.debug(f"Proxy check failed: {e}")
            return False

    def is_text_flagged(self, text: str, api_key: str = None) -> bool:
        """Проверяет текст на наличие нарушений с помощью OpenAI Moderation API"""
        if api_key is None:
            api_key = self.openai_api_key

        url = "https://api.openai.com/v1/moderations"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"input": text, "model": "omni-moderation-latest"}

        try:
            resp = self.utils.get_session().post(
                url,
                headers=headers,
                json=payload,
                proxies=self.proxy,
                timeout=self.timeout
            )
            data = resp.json()
            self.logger.debug("Moderation response: %s", data)
            return data.get("results", [{}])[0].get("flagged", False)
        except Exception as e:
            self.logger.error("Moderation call failed: %s", e)
            return False

    def llm_response(self, user_message: str, system_message: str) -> Dict[str, Any]:
        """Отправляет простой запрос к LLM с одним пользовательским сообщением"""
        messages = [{"role": "user", "content": user_message}]
        if system_message:
            messages.insert(0, {"role": "system", "content": system_message})

        try:
            resp = self.utils.get_session().post(
                self.ai_endpoint,
                json={
                    "model": self.ai_model,
                    "messages": messages,
                    "models": self.ai_models_fallback
                },
                headers={
                    "Authorization": f"Bearer {self.operouter_key}",
                    "Content-Type": "application/json"
                },
                proxies=(None if not self.check_proxy(self.proxy_url, self.read_timeout) else self.proxy),
                timeout=self.timeout
            )
            data = resp.json()
            self.logger.debug("LLM one response: %s", data)
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
        except Exception as e:
            self.logger.error("LLM one call failed: %s", e)
            return {"error": str(e)}

    def llm_conversation(self, messages: List[Dict[str, str]], system_message: str) -> Dict[str, Any]:
        """Отправляет запрос к LLM с историей сообщений"""
        # Create a copy of messages to avoid modifying the original list
        messages_copy = messages.copy()
        if system_message:
            messages_copy.insert(0, {"role": "system", "content": system_message})

        try:
            resp = self.utils.get_session().post(
                self.ai_endpoint,
                json={
                    "model": self.ai_model,
                    "messages": messages_copy,
                    "models": self.ai_models_fallback
                },
                headers={
                    "Authorization": f"Bearer {self.operouter_key}",
                    "Content-Type": "application/json"
                },
                proxies=(None if not self.check_proxy(self.proxy_url, self.read_timeout) else self.proxy),
                timeout=self.timeout
            )
            data = resp.json()
            self.logger.debug("LLM conversation response: %s", data)
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
        except Exception as e:
            self.logger.error("LLM conversation call failed: %s", e)
            return {"error": str(e)}

    def llm_call(self, messages: List[Dict[str, str]], chat_id: str, tg_user_id: str, moderate_user_callback=None) -> str:
        """
        Основной метод для вызова LLM с поддержкой tool calls и модерации

        Args:
            messages: Список сообщений для отправки в LLM
            chat_id: ID чата для модерации
            tg_user_id: ID пользователя Telegram для модерации
            moderate_user_callback: Функция обратного вызова для модерации пользователя
        """
        MAX_TOKENS = 50_000  # 51962 ~ 128k эмпирически
        try:
            import tiktoken
            encoder = tiktoken.encoding_for_model("gpt-4o")
        except ImportError:
            self.logger.warning("tiktoken not available, using approximate token counting")
            encoder = None

        # Функция для подсчёта токенов в одном сообщении
        def count_tokens(msg: Dict[str, str]) -> int:
            if encoder is None:
                # Приблизительный подсчет: ~4 символа на токен
                role_tokens = len(msg["role"]) // 4
                content_tokens = len(msg["content"]) // 4
                return role_tokens + content_tokens + 4
            else:
                # Точный подсчет с помощью tiktoken
                role_tokens = len(encoder.encode(msg["role"]))
                content_tokens = len(encoder.encode(msg["content"]))
                return role_tokens + content_tokens + 4  # +4 — служебные токены системы

        # Подсчитываем и обрезаем
        total = sum(count_tokens(m) for m in messages)
        self.logger.debug("Total tokens: %s", total)

        # Всегда оставляем первый системный prompt
        sys_msg = messages[0]
        chat_msgs = messages[1:]

        # Обрезаем oldest-first, пока не уложимся
        while total > MAX_TOKENS and chat_msgs:
            removed = chat_msgs.pop(0)
            total -= count_tokens(removed)

        messages = [sys_msg] + chat_msgs
        total = sum(count_tokens(m) for m in messages)
        self.logger.debug("Total tokens after trim: %s", total)

        try:
            resp = self.utils.get_session().post(
                self.ai_endpoint,
                json={
                    "model": self.ai_model,
                    "messages": messages,
                    "tools": self.tools,
                    "tool_choice": "auto",
                    "models": self.ai_models_fallback
                },
                headers={
                    "Authorization": f"Bearer {self.operouter_key}",
                    "Content-Type": "application/json"
                },
                proxies=(None if not self.check_proxy(self.proxy_url, self.read_timeout) else self.proxy),
                timeout=self.timeout
            )
            data = resp.json()
            self.logger.debug("LLM response: %s", data)
            choice = data["choices"][0]["message"]

            # Tool call moderation
            if "tool_calls" in choice and choice["tool_calls"][0]["function"]["name"] == "moderate_user":
                if moderate_user_callback:
                    args = json.loads(choice["tool_calls"][0]["function"]["arguments"])
                    moderate_user_callback(args["chat_id"], str(args["user_id"]), args.get("additional_reason", ""))

            content = choice.get("content", "")
            self.logger.debug("LLM content: %s", content)

            # Проверяем на флаги модерации
            if content == "Извините, я не могу помочь с этой просьбой." or self.is_text_flagged(content, self.openai_api_key):
                if moderate_user_callback:
                    moderate_user_callback(chat_id, str(tg_user_id), "LLM or moderation flagged message")

            return content
        except Exception as e:
            self.logger.error("LLM call failed: %s", e)
            return self.fallback_answer


    def embd_text(self, text: str, api_key: str = None, model: str = "text-embedding-3-small") -> List[float]:
        """Делает OpenAI embdeding текста"""
        if api_key is None:
            api_key = self.openai_api_key

        url = "https://api.openai.com/v1/embeddings"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"input": text, "model": model}

        try:
            resp = self.utils.get_session().post(
                url,
                headers=headers,
                json=payload,
                proxies=self.proxy,
                timeout=self.timeout
            )
            data = resp.json()
            self.logger.debug("Embedding response len: %s", len(data))
            embedding = data['data'][0]['embedding']
            return embedding
        except Exception as e:
            self.logger.error("Embedding call failed: %s", e)
            return False
