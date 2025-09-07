Отличная идея! Давайте создадим систему шаблонизации для system prompt, которая позволит динамически подставлять переменные как имя пользователя, названия песен и другую персональную информацию.
Ran tool
Ran tool
Ran tool
Read file: flow/database.py
Read file: flow/database.py
Теперь создам систему шаблонизации для dynamic system prompt с переменными. Создам новый модуль для управления персонализированными промптами:
Ran tool
Теперь создам систему персонализированных промптов с шаблонизацией:

```python
# flow/prompt_personalizer.py
import re
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from database import DatabaseManager
import logging

class PromptPersonalizer:
    """Система персонализации system prompt с динамическими переменными"""
    
    def __init__(self, config, db: DatabaseManager, logger: logging.Logger):
        self.config = config
        self.db = db
        self.logger = logger
        self.base_prompt = config.system_prompt
        
    def get_personalized_prompt(self, 
                              user_uuid: str, 
                              session_uuid: str,
                              user_name: str,
                              emotion_data: Dict = None,
                              intent_data: Dict = None,
                              history: List[Dict] = None) -> str:
        """
        Возвращает персонализированный system prompt с подстановкой переменных
        """
        
        # Собираем контекстную информацию о пользователе
        context_vars = self._gather_user_context(user_uuid, session_uuid, user_name)
        
        # Добавляем эмоциональный и намеренческий контекст
        context_vars.update(self._analyze_current_state(emotion_data, intent_data, history))
        
        # Применяем шаблонизацию к базовому промпту
        personalized_prompt = self._apply_template(self.base_prompt, context_vars)
        
        # Добавляем динамические модификации
        dynamic_additions = self._get_dynamic_additions(emotion_data, intent_data, context_vars)
        
        if dynamic_additions:
            personalized_prompt += "\n\n" + dynamic_additions
            
        self.logger.debug(f"Generated personalized prompt for user {user_uuid[:8]}...")
        return personalized_prompt
    
    def _gather_user_context(self, user_uuid: str, session_uuid: str, user_name: str) -> Dict[str, Any]:
        """Собирает контекстную информацию о пользователе"""
        
        context = {
            'user_name': user_name or "друг",
            'user_name_possessive': self._make_possessive(user_name) if user_name else "твоя",
            'current_time': datetime.now().strftime("%H:%M"),
            'current_date': datetime.now().strftime("%d.%m.%Y"),
            'weekday': self._get_weekday_ru(),
        }
        
        # Получаем информацию о предыдущих песнях
        user_songs = self._get_user_songs(user_uuid)
        context.update({
            'total_songs_created': len(user_songs),
            'last_song_title': user_songs[0]['title'] if user_songs else None,
            'last_song_style': user_songs[0]['style'] if user_songs else None,
            'songs_this_week': self._count_recent_songs(user_songs, days=7),
            'favorite_styles': self._get_favorite_styles(user_songs),
        })
        
        # Информация о текущей сессии
        session_info = self._get_session_context(session_uuid)
        context.update(session_info)
        
        return context
    
    def _get_user_songs(self, user_uuid: str, limit: int = 10) -> List[Dict]:
        """Получает последние песни пользователя"""
        try:
            songs = self.db.query_all(
                "SELECT title, style, created_at FROM songs WHERE user_id = %s "
                "ORDER BY created_at DESC LIMIT %s",
                (user_uuid, limit)
            )
            return list(songs) if songs else []
        except Exception as e:
            self.logger.error(f"Error fetching user songs: {e}")
            return []
    
    def _get_session_context(self, session_uuid: str) -> Dict[str, Any]:
        """Получает контекст текущей сессии"""
        try:
            # Количество сообщений в сессии
            message_count = self.db.query_one(
                "SELECT COUNT(*) as count FROM messages WHERE session_id = %s",
                (session_uuid,)
            )
            
            # Время начала сессии
            session_start = self.db.query_one(
                "SELECT created_at FROM conversation_sessions WHERE id = %s",
                (session_uuid,)
            )
            
            # Есть ли незавершённые песни в текущей сессии
            has_pending_song = self.db.query_one(
                "SELECT COUNT(*) as count FROM songs s "
                "JOIN messages m ON s.session_id = m.session_id "
                "WHERE s.session_id = %s AND s.path IS NULL",
                (session_uuid,)
            )
            
            return {
                'session_message_count': message_count['count'] if message_count else 0,
                'session_duration_minutes': self._get_session_duration(session_start),
                'has_pending_song': (has_pending_song['count'] > 0) if has_pending_song else False,
                'is_new_session': (message_count['count'] < 3) if message_count else True,
            }
        except Exception as e:
            self.logger.error(f"Error fetching session context: {e}")
            return {
                'session_message_count': 0,
                'session_duration_minutes': 0,
                'has_pending_song': False,
                'is_new_session': True,
            }
    
    def _analyze_current_state(self, emotion_data: Dict, intent_data: Dict, history: List[Dict]) -> Dict[str, Any]:
        """Анализирует текущее состояние диалога"""
        
        state_context = {
            'dominant_emotion': self._get_dominant_emotion(emotion_data),
            'emotion_intensity': self._get_emotion_intensity(emotion_data),
            'current_intent': intent_data.get('intent', 'conversation') if intent_data else 'conversation',
            'confidence_level': intent_data.get('confidence', 50) if intent_data else 50,
        }
        
        # Анализ стадии диалога
        if history:
            dialogue_stage = self._determine_dialogue_stage(history)
            state_context['dialogue_stage'] = dialogue_stage
            state_context['stage_description'] = self._get_stage_description(dialogue_stage)
        
        return state_context
    
    def _apply_template(self, template: str, variables: Dict[str, Any]) -> str:
        """Применяет шаблонизацию к промпту"""
        
        def replace_var(match):
            var_name = match.group(1)
            default_value = match.group(2) if match.group(2) else ""
            
            value = variables.get(var_name, default_value)
            
            # Специальная обработка для некоторых типов переменных
            if value is None:
                return default_value
            elif isinstance(value, (list, tuple)):
                return ', '.join(str(v) for v in value)
            elif isinstance(value, bool):
                return "да" if value else "нет"
            else:
                return str(value)
        
        # Поддержка синтаксиса {{variable_name|default_value}}
        pattern = r'\{\{([^|}]+)(?:\|([^}]*))?\}\}'
        return re.sub(pattern, replace_var, template)
    
    def _get_dynamic_additions(self, emotion_data: Dict, intent_data: Dict, context: Dict) -> str:
        """Генерирует динамические дополнения к промпту"""
        
        additions = []
        
        # Персональное обращение
        if context.get('user_name') and context['user_name'] != "друг":
            additions.append(f"Сегодня ты общаешься с {context['user_name']}.")
        
        # Контекст предыдущих песен
        if context.get('total_songs_created', 0) > 0:
            if context.get('last_song_title'):
                additions.append(
                    f"Ранее вы с {context['user_name']} создали песню \"{context['last_song_title']}\" "
                    f"в стиле {context.get('last_song_style', 'неизвестном')}."
                )
            
            if context.get('total_songs_created') > 3:
                additions.append(
                    f"У {context['user_name']} уже есть опыт создания {context['total_songs_created']} песен. "
                    f"Можешь ссылаться на этот творческий путь."
                )
        
        # Эмоциональная настройка
        dominant_emotion = context.get('dominant_emotion')
        emotion_intensity = context.get('emotion_intensity', 0)
        
        if dominant_emotion and emotion_intensity > 70:
            emotion_guidance = self._get_emotion_specific_guidance(dominant_emotion, emotion_intensity)
            if emotion_guidance:
                additions.append(emotion_guidance)
        
        # Намеренческие дополнения
        current_intent = context.get('current_intent')
        if current_intent == 'finalize_song' and context.get('has_pending_song'):
            additions.append(
                "Пользователь готов завершить работу над песней. "
                "Помоги ему финализировать творение с особой заботой."
            )
        elif current_intent == 'edit_song':
            additions.append(
                "Пользователь хочет внести правки. Будь открыт к изменениям "
                "и помоги найти точные слова для выражения чувств."
            )
        
        # Контекст времени и ситуации
        if context.get('current_time'):
            hour = int(context['current_time'].split(':')[0])
            if 6 <= hour < 12:
                additions.append("Сейчас утро — время новых начинаний и свежих идей.")
            elif 18 <= hour < 23:
                additions.append("Вечернее время располагает к глубоким размышлениям.")
            elif 23 <= hour or hour < 6:
                additions.append("Поздний час — время для искренних откровений.")
        
        return "\n".join(additions) if additions else ""
    
    def _get_emotion_specific_guidance(self, emotion: str, intensity: int) -> str:
        """Возвращает специфичные рекомендации для работы с эмоциями"""
        
        guidance_map = {
            'Растерянность': f"Пользователь находится в состоянии растерянности (интенсивность {intensity}%). "
                           "Будь особенно мягким, задавай простые вопросы, не торопи с глубокими откровениями.",
            
            'Грусть': f"Пользователь переживает грусть (интенсивность {intensity}%). "
                     "Создай безопасное пространство для выражения, не спеши с утешениями.",
            
            'Радость': f"Пользователь в радостном состоянии (интенсивность {intensity}%). "
                      "Поддержи эту энергию, помоги канализировать её в творчество.",
            
            'Тревога': f"Пользователь испытывает тревогу (интенсивность {intensity}%). "
                      "Помоги найти опору и стабильность в процессе создания.",
            
            'Вдохновение': f"Пользователь вдохновлён (интенсивность {intensity}%). "
                          "Поддержи творческий поток, помоги структурировать идеи.",
        }
        
        return guidance_map.get(emotion, "")
    
    # Вспомогательные методы
    def _make_possessive(self, name: str) -> str:
        """Создаёт притяжательную форму имени"""
        if not name:
            return "твоя"
        
        # Простая логика для русских имён
        if name.endswith(('а', 'я')):
            return name[:-1] + "ей"
        elif name.endswith('ь'):
            return name[:-1] + "и" 
        else:
            return name + "а"
    
    def _get_weekday_ru(self) -> str:
        """Возвращает день недели на русском"""
        weekdays = {
            0: "понедельник", 1: "вторник", 2: "среда", 3: "четверг",
            4: "пятница", 5: "суббота", 6: "воскресенье"
        }
        return weekdays[datetime.now().weekday()]
    
    def _count_recent_songs(self, songs: List[Dict], days: int) -> int:
        """Подсчитывает песни за последние N дней"""
        if not songs:
            return 0
        
        cutoff_date = datetime.now() - timedelta(days=days)
        return sum(1 for song in songs if song['created_at'] >= cutoff_date)
    
    def _get_favorite_styles(self, songs: List[Dict]) -> List[str]:
        """Определяет любимые стили пользователя"""
        if not songs:
            return []
        
        style_counts = {}
        for song in songs:
            style = song.get('style', '').strip()
            if style:
                style_counts[style] = style_counts.get(style, 0) + 1
        
        # Возвращаем топ-3 стиля
        return sorted(style_counts.keys(), key=lambda x: style_counts[x], reverse=True)[:3]
    
    def _get_dominant_emotion(self, emotion_data: Dict) -> Optional[str]:
        """Определяет доминирующую эмоцию"""
        if not emotion_data or 'emotions' not in emotion_data:
            return None
        
        emotions = emotion_data['emotions']
        if not emotions:
            return None
        
        # Находим эмоцию с максимальной интенсивностью
        dominant = max(emotions, key=lambda x: x.get('intensity', 0))
        return dominant.get('name')
    
    def _get_emotion_intensity(self, emotion_data: Dict) -> int:
        """Получает интенсивность доминирующей эмоции"""
        if not emotion_data or 'emotions' not in emotion_data:
            return 0
        
        emotions = emotion_data['emotions']
        if not emotions:
            return 0
        
        dominant = max(emotions, key=lambda x: x.get('intensity', 0))
        return dominant.get('intensity', 0)
    
    def _determine_dialogue_stage(self, history: List[Dict]) -> str:
        """Определяет стадию диалога"""
        if not history:
            return "opening"
        
        message_count = len(history)
        assistant_messages = [msg for msg in history if msg.get('role') == 'assistant']
        
        # Анализируем содержание для определения стадии
        if message_count <= 3:
            return "opening"
        elif any("песн" in msg.get('content', '').lower() for msg in assistant_messages[-3:]):
            return "creation"
        elif message_count > 10:
            return "deep_exploration"
        else:
            return "exploration"
    
    def _get_stage_description(self, stage: str) -> str:
        """Возвращает описание стадии диалога"""
        descriptions = {
            "opening": "начало знакомства",
            "exploration": "исследование чувств",
            "deep_exploration": "глубокое погружение",
            "creation": "творческий процесс"
        }
        return descriptions.get(stage, "общение")
    
    def _get_session_duration(self, session_start: Dict) -> int:
        """Вычисляет длительность сессии в минутах"""
        if not session_start or 'created_at' not in session_start:
            return 0
        
        try:
            start_time = session_start['created_at']
            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            
            duration = datetime.now(timezone.utc) - start_time
            return int(duration.total_seconds() / 60)
        except Exception:
            return 0
```

Теперь создам обновленный шаблон system prompt с поддержкой переменных:

```python
# flow/system_prompt_template.txt
<<SYSTEM PROMPT START>>
Роль:
Ты — ИИ-собеседник, зовущий себя "ПойМойМир". Бережный спутник, а не учитель.

{{#user_name}}Сегодня ты общаешься с {{user_name}}.{{/user_name}}

{{#total_songs_created}}
{{user_name}} уже создал(а) {{total_songs_created}} песен(и). 
{{#last_song_title}}Последняя песня — "{{last_song_title}}"{{#last_song_style}} в стиле {{last_song_style}}{{/last_song_style}}.{{/last_song_title}}
{{#favorite_styles}}Любимые стили: {{favorite_styles}}.{{/favorite_styles}}
{{/total_songs_created}}

Пиши песню как песню: с ритмом, рифмой и мелодичностью — чтобы строки звучали и пелись. Избегай белого стиха.
8–12 слогов на строку, 4 строки в куплете,припеве, рифм ABAB, AABB или AAAA, концовки всех строк — открытые гласные.

ВСЕГДА строго следуй правилам отображения текста
Думаю: Твои внутренние рассуждения, СКРЫТЫЕ от пользователя, ЗАПРЕЩЕНО показывать пользователю
Показываю: То что ты показываешь пользователю

Миссия:
- Помогать человеку превращать чувства, воспоминания и ценности (семья, род, любовь, путь, свобода, надежда) в поющие, рифмованные песни.
- Сопровождать внутренний путь мягко, с уважением к тишине и сомнениям.
- Помогать безопасно найти важное внутри себя и сделать первый шаг к личной трансформации.
- Бережно сопровождать человека в его внутреннем пути.
- Помочь услышать не только то, что он чувствует, но и то, во что он верит. Семья, род, любовь, путь, свобода, надежда.
- Помочь собеседнику почувствовать себя услышанным, важным и интересным.
- Создать атмосферу заботы, внимания

{{#is_new_session}}
Это начало новой беседы. Создай атмосферу доверия и безопасности.
{{/is_new_session}}

{{#session_message_count}}
{{#gt session_message_count 10}}
Вы уже долго общаетесь ({{session_message_count}} сообщений). Углубляйся в детали и нюансы.
{{/gt}}
{{/session_message_count}}

Запреты обсуждения:
- Пропаганда ЛГБТ — описание, романтизация или позитивное продвижение однополых отношений, гендерной идентичности, трансгендерности или гендерных переходов.
```

Теперь обновим `utils.py` для использования персонализированных промптов:

```python:180:190:flow/utils.py
# flow/utils.py (модификация compute_message_context)

def compute_message_context(self, history: List[Dict[str, Any]], user_text: str, 
                          user_uuid: str = None, session_uuid: str = None, 
                          user_name: str = None, emotion_data: Dict = None, 
                          intent_data: Dict = None):
    # ... существующий код для обработки истории ...
    
    # Получаем персонализированный промпт
    if hasattr(self, 'prompt_personalizer') and user_uuid and session_uuid:
        system_prompt = self.prompt_personalizer.get_personalized_prompt(
            user_uuid=user_uuid,
            session_uuid=session_uuid, 
            user_name=user_name,
            emotion_data=emotion_data,
            intent_data=intent_data,
            history=history
        )
    else:
        system_prompt = self.config.system_prompt
    
    if msgs_from_phrase:
        openai_msgs = [
            {"role": "system", "content": system_prompt},
            *msgs_from_phrase,
            {"role": "user", "content": user_text}
        ]
    else:
        openai_msgs = [
            {"role": "system", "content": system_prompt},
            *history,
            {"role": "user", "content": user_text}
        ]
```

И обновим `index.py` для передачи необходимых параметров:

```python:85:100:flow/index.py
# flow/index.py (модификация)

# После сохранения анализа
analysis = {"intent": detect_intent, "emotion": detect_emotion}
db.update_message_analysis(msg_id, analysis)

# Подготовка контекста сообщений с персонализацией
ctx = utils.compute_message_context(
    history=history, 
    user_text=text,
    user_uuid=user_uuid,
    session_uuid=session_uuid,
    user_name=full_name,
    emotion_data=detect_emotion,
    intent_data=detect_intent
)
```

Теперь нужно добавить инициализацию `PromptPersonalizer` в начало `index.py`:

```python:30:35:flow/index.py
# flow/index.py (дополнение после создания основных менеджеров)

# LLM manager
llm = LLMManager(config, utils, logger)
# Prompt personalizer
from prompt_personalizer import PromptPersonalizer
prompt_personalizer = PromptPersonalizer(config, db, logger)
# Добавляем в utils для использования
utils.prompt_personalizer = prompt_personalizer
```

## Основные возможности созданной системы:

### 1. **Переменные пользователя:**
- `{{user_name}}` - имя пользователя
- `{{user_name_possessive}}` - притяжательная форма
- `{{total_songs_created}}` - количество созданных песен
- `{{last_song_title}}` - название последней песни
- `{{favorite_styles}}` - любимые стили

### 2. **Контекстные переменные:**
- `{{current_time}}`, `{{current_date}}`, `{{weekday}}`
- `{{session_message_count}}` - количество сообщений в сессии
- `{{is_new_session}}` - новая ли это сессия
- `{{dominant_emotion}}` - основная эмоция
- `{{current_intent}}` - текущее намерение

### 3. **Динамические дополнения:**
- Эмоционально-специфичные рекомендации
- Ссылки на предыдущие песни
- Контекст времени и ситуации
- Рекомендации для разных стадий диалога

Система автоматически персонализирует каждый system prompt под конкретного пользователя, создавая более глубокое и значимое взаимодействие!