# -*- coding: utf-8 -*-
"""
handler.py – Yandex Cloud Functions серверлесс-backend Telegram-бота «Пой Мой Мир»
====================================================================================

Этот файл реализует:
 1. Приём вебхуков от Telegram (Yandex Cloud Functions).
 2. Хранение состояний диалога в гибридной памяти (YDB или Postgres).
 3. FSM-диалог на основе LangChain StateGraph.
 4. Определение переходов через LLM-классификатор + regex-fallback (StateClassifier).
 5. Модерацию через OpenAI и генерацию через OpenRouter.

Полная структура файлового модуля:
  - handler.py      ← этот файл
  - system_prompt.txt  ← текст системного промпта
  - requirements.txt   ← зависимости (aiogram, langchain, openai, httpx, ydb)

"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Pattern, Tuple

import httpx
import openai
import ydb
from openai import AsyncOpenAI
from ydb.iam import MetadataUrlCredentials
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.types import Update
from langchain import LLMChain
from langchain.chat_models import ChatOpenAI
from langchain.graphs import StateGraph
from langchain.memory import (
    ChatMessageHistory,
    ConversationBufferMemory,
    PostgresChatMessageHistory,
)
from langchain.schema import AIMessage, BaseMessage, HumanMessage
from langchain.prompts import PromptTemplate
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
class Settings(BaseModel):
    # Telegram Bot
    telegram_bot_token: str = Field(..., env="BOT_TOKEN")

    # OpenAI (для модерации)
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")

    # OpenRouter (для генерации)
    openrouter_key: str = Field(..., env="OPENROUTER_KEY")

    # Прокси и таймауты
    proxy_url: Optional[str] = Field(None, env="PROXY_URL")
    connect_timeout: float = Field(1.0, env="CONNECT_TIMEOUT")
    read_timeout: float = Field(15.0, env="READ_TIMEOUT")

    # Хранение: Postgres для долговременной памяти
    pg_dsn: str = Field(..., env="DATABASE_URL")

    # YDB: опциональный слой RAM-memory
    ydb_endpoint: Optional[str] = Field(None, env="YDB_ENDPOINT")
    ydb_database: Optional[str] = Field(None, env="YDB_DATABASE")
    ydb_table: str = Field("chat_messages", env="YDB_TABLE")

    # Системный промпт (может содержать полную роль бота)
    system_prompt_path: Path = Field(Path("system_prompt.txt"), env="SYSTEM_PROMPT_PATH")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()  # type: ignore[arg-type]

# ---------------------------------------------------------------------------
# LOGGER
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("poimoi-serverless")

# ---------------------------------------------------------------------------
# COLD-START GLOBAL RESOURCES
# ---------------------------------------------------------------------------
# 1) Системный промпт
try:
    SYSTEM_PROMPT = settings.system_prompt_path.read_text(encoding="utf-8")
except FileNotFoundError:
    SYSTEM_PROMPT = ""
    logger.warning("system_prompt.txt not found – proceeding without it")

# 2) HTTPX транспорт для прокси и таймаутов
_http_transport = httpx.AsyncHTTPTransport(retries=3, proxy=settings.proxy_url)
httpx_client = httpx.AsyncClient(
    transport=_http_transport,
    timeout=httpx.Timeout(settings.read_timeout),
    proxies=settings.proxy_url,
)

# 3) Клиент для модерации через OpenAI API
openai_client = AsyncOpenAI(
    api_key=settings.openai_api_key,
    http_client=httpx_client,
)

# 4) Клиент для генерации через OpenRouter
openrouter_client = AsyncOpenAI(
    api_key=settings.openrouter_key,
    base_url="https://openrouter.ai/api/v1",
    http_client=httpx_client,
)

# 5) LLMChain для генерации и классификации
generation_llm = ChatOpenAI(
    openai_client=openrouter_client,
    model_name="openai/gpt-4o-mini",
    temperature=0.7,
)

# 6) Telegram Bot & Dispatcher
bot = Bot(settings.telegram_bot_token, parse_mode=ParseMode.MARKDOWN_V2)
dp = Dispatcher()

# ---------------------------------------------------------------------------
# STATE CLASSIFIER (LLM + regex fallback)
# ---------------------------------------------------------------------------
class StateClassifier:
    """
    Классификатор следующего состояния диалога.
    Использует few-shot LLMChain и fallback на регулярки.
    """
    def __init__(
        self,
        llm: ChatOpenAI,
        possible_states: List[str],
        examples: List[Tuple[str, str]],
        regex_patterns: List[Tuple[Pattern, str]],
    ):
        self.llm = llm
        self.possible_states = possible_states
        self.regex_patterns = regex_patterns

        # Формируем few-shot примеры
        shots = "\n".join(
            f"User: \"{msg}\"\nState: {state}" for msg, state in examples
        )
        template = f"""
You are an assistant whose single job is to choose exactly one state name
from the list of possible states, based on the user's latest message.
Use the examples to guide you.

Examples:
{shots}

Possible states:
{{states}}

User message:
"""{{message}}"""

Respond with exactly one of the state names above, without extra words.
"""
        self.chain = LLMChain(
            llm=self.llm,
            prompt=PromptTemplate(
                template=template,
                input_variables=["states", "message"],
            ),
        )

    async def classify(self, message: str) -> str:
        # Few-shot LLM
        states_str = "\n".join(f"- {s}" for s in self.possible_states)
        raw = await self.chain.arun(states=states_str, message=message)
        state = raw.strip()
        # Если LLM вернул известный стейт, используем его
        if state in self.possible_states:
            return state
        # Иначе пробуем regex-fallback
        for pattern, fallback_state in self.regex_patterns:
            if pattern.search(message):
                return fallback_state
        # По умолчанию
        return "ask_feeling"

# Определяем полный список состояний для классификатора
POSSIBLE_STATES = [
    "intro", "ask_name", "ask_feeling",
    "first_line_offer", "first_line_feedback",
    "verse_build", "verse_feedback",
    "chorus_build", "chorus_feedback",
    "bridge_build", "bridge_feedback",
    "assemble_song", "ask_style", "style_feedback",
    "tempo_feedback", "instruments_feedback",
    "offer_playback", "playback_feedback",
    "final_thanks", "post_finish",
    "silent_mode", "doubt_support",
]

# Few-shot примеры
EXAMPLES: List[Tuple[str, str]] = [
    ("Привет", "intro"),
    ("Меня зовут Оля", "ask_name"),
    ("Я очень грустил вчера", "ask_feeling"),
    ("Да, мне нравится эта строка", "first_line_feedback"),
    ("Давай ещё куплет", "verse_feedback"),
    ("Какой жанр предпочтёшь?", "ask_style"),
]

# Fallback regex-паттерны
REGEX_PATTERNS: List[Tuple[Pattern, str]] = [
    (re.compile(r"\bпривет\b|\bздравствуй\b", re.I), "intro"),
    (re.compile(r"\bзовут\b|\bменя зовут\b", re.I), "ask_name"),
    (re.compile(r"\bне знаю\b|\bне помню\b", re.I), "ask_feeling"),
    (re.compile(r"\bкуплет\b|\bещё куплет\b", re.I), "verse_build"),
    (re.compile(r"\bприпев\b", re.I), "chorus_build"),
    (re.compile(r"\bстиль\b|\bжанр\b", re.I), "ask_style"),
]

# Инициализируем классификатор
classifier = StateClassifier(
    llm=generation_llm,
    possible_states=POSSIBLE_STATES,
    examples=EXAMPLES,
    regex_patterns=REGEX_PATTERNS,
)

# ---------------------------------------------------------------------------
# GraphState & узлы FSM
# ---------------------------------------------------------------------------
class GraphState(BaseModel):
    messages: List[BaseMessage] = []
    step: str = "intro"

    # Пользовательские данные
    user_name: Optional[str] = None
    feeling: Optional[str] = None

    # Черновики песни
    first_line: Optional[str] = None
    verses: List[str] = []
    chorus: Optional[str] = None
    bridge: Optional[str] = None

    # Оформление
    style_genre: Optional[str] = None
    style_tempo: Optional[str] = None
    instruments: List[str] = []

    # Флаги прогресса
    assembled: bool = False
    offered_playback: bool = False
    thanked: bool = False

    # Особые состояния
    silent_mode: bool = False
    doubt_supported: bool = False

# Определение функций-узлов
async def intro(state: GraphState) -> GraphState:
    """Приветствие и запрос имени"""
    state.messages.append(
        AIMessage(
            content=(
                "Я — Пой Мой Мир. Я помогу тебе услышать песню твоего внутреннего мира.\n"
                "Как ты хочешь, чтобы я к тебе обращался?"
            )
        )
    )
    state.step = "ask_name"
    return state

async def ask_name(state: GraphState, user_msg: HumanMessage) -> GraphState:
    """Сохранение обращения и переход к эмоциональному погружению"""
    state.user_name = user_msg.content.strip()
    state.messages.append(user_msg)
    state.messages.append(AIMessage(content="Что ты чувствовал недавно по-настоящему?"))
    state.step = "ask_feeling"
    return state

async def ask_feeling(state: GraphState, user_msg: HumanMessage) -> GraphState:
    """Обработка эмоции или подсказка, если пользователь не знает/не помнит"""
    state.feeling = user_msg.content.strip()
    state.messages.append(user_msg)
    low = state.feeling.lower()
    if low in {"не знаю", "не помню", "непомню"}:
        state.messages.append(
            AIMessage(content="Представь образы, запахи, воспоминания из детства…")
        )
        state.step = "ask_feeling"
    else:
        state.messages.append(
            AIMessage(content="❄️ Я услышал. Предлагаю первую строку твоей песни.")
        )
        state.step = "first_line_offer"
    return state

async def first_line_offer(state: GraphState) -> GraphState:
    """Генерация и предложение первой строки"""
    # Генерация через LLМChain
    prompt = f"Сгенерируй первую строку песни на тему '{state.feeling}' " \
              "в формате 8 слогов, открытая гласная в конце"
    line = (await generation_llm.generate(messages=[
        HumanMessage(content=prompt)
    ])).generations[0][0].text.strip()
    state.first_line = line
    state.messages.append(AIMessage(content=f"Первая строка: “{line}”. Как тебе?"))
    state.step = "first_line_feedback"
    return state

async def first_line_feedback(state: GraphState, user_msg: HumanMessage) -> GraphState:
    """Обработка отклика на первую строку"""
    text = user_msg.content.lower()
    state.messages.append(user_msg)
    positive = any(w in text for w in ["нравится", "ок", "да"])  # простая проверка
    if positive:
        state.step = "verse_build"
    else:
        state.step = "first_line_offer"
    return state

async def verse_build(state: GraphState) -> GraphState:
    """Генерация куплета и запрос фидбека"""
    prompt = f"Сгенерируй куплет песни из 4 строк по 8 слогов, рифма ABAB, " \
              f"на основе первой строки '{state.first_line}'"
    verse = (await generation_llm.generate(messages=[
        HumanMessage(content=prompt)
    ])).generations[0][0].text.strip()
    state.verses.append(verse)
    state.messages.append(AIMessage(content=f"Куплет:\n{verse}\nКак тебе?"))
    state.step = "verse_feedback"
    return state

async def verse_feedback(state: GraphState, user_msg: HumanMessage) -> GraphState:
    """Решение: ещё куплет или к припеву"""
    text = user_msg.content.lower()
    state.messages.append(user_msg)
    if "ещ" in text:
        state.step = "verse_build"
    else:
        state.step = "chorus_build"
    return state

async def chorus_build(state: GraphState) -> GraphState:
    """Генерация припева и запрос фидбека"""
    prompt = f"Сгенерируй припев из 4 строк по 6 слогов, рифма AABB, " \
              f"на тему '{state.feeling}'"
    chorus = (await generation_llm.generate(messages=[
        HumanMessage(content=prompt)
    ])).generations[0][0].text.strip()
    state.chorus = chorus
    state.messages.append(AIMessage(content=f"Припев:\n{chorus}\nКак звучит?"))
    state.step = "chorus_feedback"
    return state

async def chorus_feedback(state: GraphState, user_msg: HumanMessage) -> GraphState:
    """Решение: ещё припев или сборка песни"""
    text = user_msg.content.lower()
    state.messages.append(user_msg)
    if "ещ" in text:
        state.step = "chorus_build"
    else:
        state.step = "assemble_song"
    return state

async def bridge_build(state: GraphState) -> GraphState:
    """Опциональный бридж между куплетом и припевом"""
    prompt = f"Сгенерируй короткий бридж для песни на тему '{state.feeling}'"
    bridge = (await generation_llm.generate(messages=[
        HumanMessage(content=prompt)
    ])).generations[0][0].text.strip()
    state.bridge = bridge
    state.messages.append(AIMessage(content=f"Бридж:\n{bridge}"))
    state.step = "bridge_feedback"
    return state

async def bridge_feedback(state: GraphState, user_msg: HumanMessage) -> GraphState:
    """Отклик на бридж: далее или повтор"""
    # Аналогично verse_feedback
    state.messages.append(user_msg)
    if "ещ" in user_msg.content.lower():
        state.step = "bridge_build"
    else:
        state.step = "assemble_song"
    return state

async def assemble_song(state: GraphState) -> GraphState:
    """Сборка всей песни в красивый блок кода"""
    parts = []
    parts.append("[Intro]")
    parts.append(state.first_line or "")
    for idx, v in enumerate(state.verses, start=1):
        parts.append(f"[Verse {idx}]")
        parts.append(v)
    if state.chorus:
        parts.append("[Chorus]")
        parts.append(state.chorus)
    if state.bridge:
        parts.append("[Bridge]")
        parts.append(state.bridge)
    parts.append("[Outro]")
    parts.append(state.first_line or "")  # можно переиспользовать или добавить outro
    song_block = "\n".join(parts)
    state.messages.append(AIMessage(content=f"```\n{song_block}\n```"))
    state.assembled = True
    state.step = "ask_style"
    return state

async def ask_style(state: GraphState) -> GraphState:
    """Запрос жанра"""
    state.messages.append(AIMessage(content="Какой жанр предпочитаешь: камерная баллада или нежный фолк?"))
    state.step = "style_feedback"
    return state

async def style_feedback(state: GraphState, user_msg: HumanMessage) -> GraphState:
    """Сохранение жанра и запрос темпа"""
    state.style_genre = user_msg.content.strip()
    state.messages.append(user_msg)
    state.messages.append(AIMessage(content="Отлично. Какой темп: медленный, средний или быстрый?"))
    state.step = "tempo_feedback"
    return state

async def tempo_feedback(state: GraphState, user_msg: HumanMessage) -> GraphState:
    """Сохранение темпа и запрос инструментов"""
    state.style_tempo = user_msg.content.strip()
    state.messages.append(user_msg)
    state.messages.append(AIMessage(content="Какие инструменты ты бы хотел услышать?"))
    state.step = "instruments_feedback"
    return state

async def instruments_feedback(state: GraphState, user_msg: HumanMessage) -> GraphState:
    """Сохранение инструментов и переход к предложению воспроизведения"""
    instruments = [i.strip() for i in user_msg.content.split(",")]
    state.instruments = instruments
    state.messages.append(user_msg)
    state.messages.append(AIMessage(content="Хорошо. Хочешь, я попробую проговорить или пропеть песню?"))
    state.step = "offer_playback"
    return state

async def offer_playback(state: GraphState, user_msg: Optional[HumanMessage] = None) -> GraphState:
    """Предложение воспроизведения и возможный отклик"""
    # Это узел без user_msg при генерации запроса, но после фидбека
    if user_msg:
        state.messages.append(user_msg)
        if "да" in user_msg.content.lower():
            state.messages.append(AIMessage(content="Попробую пропеть... 🎶"))
        else:
            state.messages.append(AIMessage(content="Хорошо, пропуск воспроизведения."))
        state.step = "final_thanks"
    else:
        # первый вызов: сам предложить
        state.messages.append(AIMessage(content="Хочешь, я попробую проговорить или пропеть песню?"))
        state.step = "playback_feedback"
    return state

async def playback_feedback(state: GraphState, user_msg: HumanMessage) -> GraphState:
    """Обработка ответа на предложение воспроизведения"""
    return await offer_playback(state, user_msg)

async def final_thanks(state: GraphState, user_msg: Optional[HumanMessage] = None) -> GraphState:
    """Прощание, благодарность и приглашение к поддержке"""
    if user_msg:
        state.messages.append(user_msg)
    state.messages.append(AIMessage(content=(
        "Спасибо за доверие. 
        Если тебе откликнулось, можешь поддержать этот проект и вдохновить новые песни: https://bit.ly/4jZSMIH
        "
    )))
    state.step = "post_finish"
    return state

async def post_finish(state: GraphState) -> GraphState:
    """Опции после финала: сохранить, поделиться, остаться в моменте"""
    state.messages.append(
        AIMessage(content=(
            "Ты можешь сохранить песню, поделиться ею или просто остаться в этом моменте..."
        ))
    )
    return state

# ---------------------------------------------------------------------------
# BUILD AND COMPILE GRAPH
# ---------------------------------------------------------------------------
def build_flow() -> StateGraph:
    g = StateGraph(GraphState)
    # Добавляем узлы
    g.add_node("intro", intro)
    g.add_node("ask_name", ask_name)
    g.add_node("ask_feeling", ask_feeling)
    g.add_node("first_line_offer", first_line_offer)
    g.add_node("first_line_feedback", first_line_feedback)
    g.add_node("verse_build", verse_build)
    g.add_node("verse_feedback", verse_feedback)
    g.add_node("chorus_build", chorus_build)
    g.add_node("chorus_feedback", chorus_feedback)
    g.add_node("bridge_build", bridge_build)
    g.add_node("bridge_feedback", bridge_feedback)
    g.add_node("assemble_song", assemble_song)
    g.add_node("ask_style", ask_style)
    g.add_node("style_feedback", style_feedback)
    g.add_node("tempo_feedback", tempo_feedback)
    g.add_node("instruments_feedback", instruments_feedback)
    g.add_node("offer_playback", offer_playback)
    g.add_node("playback_feedback", playback_feedback)
    g.add_node("final_thanks", final_thanks)
    g.add_node("post_finish", post_finish)
    # Специальные состояния по умолчанию обрабатываются внутри узлов

    # Точка входа
    g.set_entry_point("intro")

    # Обычные ребра
    g.add_edge("intro", "ask_name")
    g.add_edge("ask_name", "ask_feeling")
    g.add_edge("ask_feeling", "first_line_offer")
    g.add_edge("first_line_offer", "first_line_feedback")
    g.add_edge("first_line_feedback", "verse_build")
    g.add_edge("first_line_feedback", "first_line_offer")
    g.add_edge("verse_build", "verse_feedback")
    g.add_edge("verse_feedback", "verse_build")
    g.add_edge("verse_feedback", "chorus_build")
    g.add_edge("chorus_build", "chorus_feedback")
    g.add_edge("chorus_feedback", "chorus_build")
    g.add_edge("chorus_feedback", "assemble_song")
    g.add_edge("assemble_song", "ask_style")
    g.add_edge("ask_style", "style_feedback")
    g.add_edge("style_feedback", "tempo_feedback")
    g.add_edge("tempo_feedback", "instruments_feedback")
    g.add_edge("instruments_feedback", "offer_playback")
    g.add_edge("offer_playback", "playback_feedback")
    g.add_edge("playback_feedback", "final_thanks")
    g.add_edge("final_thanks", "post_finish")

    return g

flow = build_flow().compile()

# ---------------------------------------------------------------------------
# CORE UPDATE HANDLER
# ---------------------------------------------------------------------------
async def process_update(update: Update) -> None:
    """Главная функция обработки одного Telegram Update"""
    if not update.message or not update.message.text:
        return

    chat_id = update.message.chat.id
    user_text = update.message.text

    # 1) Модерация
    if await openai_client.moderations.create(
        model="omni-moderation-latest", input=user_text
    ).results[0].flagged:  # type: ignore[attr-defined]
        await bot.send_message(chat_id, "Извините, я не могу помочь с этой темой.")
        return

    # 2) Классификация состояния
    next_step = await classifier.classify(user_text)

    # 3) Инициализация или загрузка состояния
    # Здесь можно хранить state в RAM или в памяти (YDB/Postgres) по chat_id
    state = GraphState(step=next_step)

    # 4) Выполнение узла FSM
    # Передаём user_text при необходимости
    human_msg = HumanMessage(content=user_text)
    await flow.astep(state, human_msg)

    # 5) Ответ и сохранение в память
    ai_msg = state.messages[-1]
    await bot.send_message(chat_id, ai_msg.content)
    # сохранение в memory (Postgres/YDB)
    memory = HybridMemory(session_id=str(chat_id))
    await memory.aadd_message(human_msg)
    await memory.aadd_message(ai_msg)

# ---------------------------------------------------------------------------
# DISPATCHER ROUTE
# ---------------------------------------------------------------------------
@dp.update()
async def handle(update: Update):
    try:
        await process_update(update)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error processing update: %s", exc)

# ---------------------------------------------------------------------------
# ENTRYPOINT для Yandex Cloud Functions
# ---------------------------------------------------------------------------
async def _async_entry(event: Dict[str, Any]) -> Dict[str, Any]:
    """Асинхронная обёртка: принимает event.body как JSON-Update"""
    try:
        payload = json.loads(event.get("body", "{}"))
        update = Update.model_validate(payload)
    except Exception as err:
        logger.warning("Invalid update payload: %s", err)
        return {"statusCode": 400, "body": "bad request"}

    await dp.feed_update(bot, update)
    return {"statusCode": 200, "body": "OK"}


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Sync wrapper для Yandex Cloud Functions"""
    try:
        return asyncio.run(_async_entry(event))
    except Exception:
        # Всегда возвращаем 200, чтобы Telegram не зацикливал retries
        return {"statusCode": 200, "body": "error"}

# ---------------------------------------------------------------------------
# LOCAL DEBUG MODE
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    from pathlib import Path

    if len(sys.argv) != 2:
        print("Usage: python handler.py <update.json>")
        exit(1)
    body = Path(sys.argv[1]).read_text(encoding="utf-8")
    event_debug = {"body": body}
    print(asyncio.run(_async_entry(event_debug)))
