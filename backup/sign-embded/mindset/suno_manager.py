# Standard library imports
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# Third-party imports
import boto3
import requests
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3

# Local imports
from .config import Config
from .database import DatabaseManager
from .telegram_bot import TelegramBot
from .utils import Utils
from .llm_manager import LLMManager
from .audio_signer import AudioSigner


class SunoManager:
    """Класс для работы с Suno API и обработки аудио"""

    def __init__(self, config: Config, db: DatabaseManager, telegram_bot: TelegramBot, utils: Utils, llm: LLMManager, logger: logging.Logger):
        """
        Инициализация SunoManager

        Args:
            config: Объект конфигурации
            db: Менеджер базы данных
            telegram_bot: Телеграм бот
            utils: Утилиты
            llm: Менеджер LLM
            logger: Логгер
        """
        self.config = config
        self.db = db
        self.telegram_bot = telegram_bot
        self.utils = utils
        self.llm = llm
        self.logger = logger

        # Настройки Suno API из конфигурации
        self.suno_api_url = config.suno_api_url
        self.suno_model = config.suno_model
        self.suno_callback_url = config.suno_callback_url
        self.suno_api_key = config.suno_api_key

        # Другие настройки
        self.song_path = config.song_path
        self.song_bucket_name = config.song_bucket_name
        self.ai_composer = config.ai_composer
        self.timeout = (config.connect_timeout, config.read_timeout)
        
        # Audio signing configuration
        self.audio_signer = AudioSigner(utils=utils)
        self.signing_enabled = getattr(config, 'audio_signing_enabled', False)
        self.private_key_path = getattr(config, 'audio_signing_private_key_path', None)
        
        # Audio watermarking configuration
        self.watermarking_enabled = getattr(config, 'audio_watermarking_enabled', False)
        self.watermark_password = getattr(config, 'audio_watermark_password', None)

    def generate_song_url(self, bucket: str, key: str, expires_in: int = 3600) -> str:
        """
        Генерирует временную (signed) ссылку на файл в приватном S3/Yandex Object Storage бакете.

        Args:
            bucket: имя бакета
            key: путь к файлу внутри бакета
            expires_in: время жизни ссылки в секундах (по умолчанию 1 час)

        Returns:
            временная ссылка (signed url)
        """
        self.logger.debug("Generating signed URL for key %s, expires_in %d", key, expires_in)
        s3 = boto3.client("s3")
        url = s3.generate_presigned_url(
            ClientMethod='get_object',
            Params={'Bucket': bucket, 'Key': key},
            ExpiresIn=expires_in
        )
        self.logger.debug("Generated signed URL for key %s", key)
        return url

    def download_and_process_song(self, song_url: str, tg_user_id: str, song_title: str, song_artist: str, local_folder: str, song_bucket_name: str) -> str:
        """
        Скачивает песню, обрабатывает метаданные и загружает в бакет

        Args:
            song_url: URL песни для скачивания
            tg_user_id: ID пользователя Telegram
            song_title: Название песни
            song_artist: Исполнитель
            local_folder: Локальная папка для временного хранения
            song_bucket_name: Имя бакета для загрузки

        Returns:
            Подписанный URL для доступа к загруженной песне
        """
        self.logger.debug("Downloading song from %s for user %s", song_url, tg_user_id)
        local_path = os.path.join(f"{local_folder}/{tg_user_id}/", f"{song_title}.mp3")
        song_key = f"{tg_user_id}/{song_title}.mp3"
        os.makedirs(f"{local_folder}/{tg_user_id}", exist_ok=True)
        r = requests.get(song_url)
        with open(local_path, "wb") as f:
            f.write(r.content)

        self.logger.debug("Changing metadata for song %s by %s", song_title, song_artist)
        audio = MP3(local_path, ID3=EasyID3)
        audio["title"] = song_title
        audio["artist"] = song_artist
        audio["composer"] = self.ai_composer
        audio.save()

        # Sign the audio file if signing is enabled
        if self.signing_enabled and self.private_key_path:
            try:
                sidecar_path = local_path.replace(".mp3", ".c2pa")
                track_id = self.audio_signer.sign_audio(
                    Path(local_path), 
                    self.suno_model, 
                    Path(self.private_key_path), 
                    Path(sidecar_path),
                    watermark_password=self.watermark_password if self.watermarking_enabled else None
                )
                self.logger.debug("Signed audio file with track ID: %s", track_id)
                
                # Upload the sidecar file as well
                sidecar_key = song_key.replace(".mp3", ".c2pa")
                s3 = boto3.client("s3")
                s3.upload_file(sidecar_path, song_bucket_name, sidecar_key)
                self.logger.debug("Uploaded sidecar file to %s", sidecar_key)
            except Exception as e:
                self.logger.exception("Failed to sign audio file: %s", e)

        if not song_bucket_name:
            self.logger.warning("song_bucket_name is not configured; returning original song URL")
            return song_url

        self.logger.debug("Uploading song %s to bucket %s with key %s", local_path, song_bucket_name, song_key)
        s3 = boto3.client("s3")
        try:
            s3.upload_file(local_path, song_bucket_name, song_key, ExtraArgs={"ContentType": "audio/mpeg"})
        except Exception as e:
            self.logger.exception("Failed to upload song to S3: %s", e)
            raise

        signed_url = self.generate_song_url(bucket=song_bucket_name, key=song_key)
        return signed_url

    def request_suno(self, prompt: str, style: str, title: str) -> Optional[Dict[str, Any]]:
        """
        Отправляет запрос к Suno AI API для генерации аудио

        Args:
            prompt: Текстовый промпт для генерации аудио
            style: Стиль генерируемого аудио
            title: Название генерируемого аудио

        Returns:
            Ответ API в формате {"code": 200,"msg": "success","data": {"taskId": "5c79****be8e"}}
            или None в случае ошибки
        """
        if not self.suno_callback_url:
            self.logger.error("suno_callback_url is not set")
            return None

        callback = f"{self.suno_callback_url}"
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.suno_api_key}'
        }

        payload = {
            "prompt": prompt,
            "style": style,
            "title": title,
            "customMode": True,
            "instrumental": False,
            "model": self.suno_model,
            "callBackUrl": callback,
        }

        try:
            r = self.utils.get_session().post(self.suno_api_url, json=payload, timeout=self.timeout, headers=headers)
            data = r.json()
            r.raise_for_status()
            self.logger.debug("Suno request OK: %s", r.text)
            return data
        except Exception as e:
            self.logger.exception("Suno generation failed: %s", e)
            return None

    def handle_suno_callback(self, body: Dict[str, Any], bot_id: str, session_lifetime: int) -> Dict[str, Any]:
        """
        Обрабатывает callback от Suno API когда песня готова

        Args:
            body: Тело запроса с данными callback
            bot_id: ID бота
            session_lifetime: Время жизни сессии

        Returns:
            Ответ для Lambda функции
        """
        try:
            task_id = body["data"]["task_id"]
            song_url = body["data"]["data"][0]["audio_url"]
            song_title = body["data"]["data"][0]["title"]
            song_artist = "ПойМойМир"

            self.logger.debug("Suno song generated: %s", song_url)

            # Получаем информацию о пользователе
            rec = self.db.get_user_by_song_task(task_id)
            tg_user_id = rec["telegram_user_id"]

            # Получаем полное имя пользователя
            user_rec = self.db.get_user_by_tg_id(tg_user_id)
            full_name = user_rec["full_name"]

            self.logger.debug("Telegram user found: %s", rec)

            # Скачиваем и обрабатываем песню
            processed_song_url = self.download_and_process_song(
                song_url=song_url,
                song_title=song_title,
                tg_user_id=tg_user_id,
                song_artist=song_artist,
                local_folder=self.song_path,
                song_bucket_name=self.song_bucket_name
            )

            # Обновляем путь к песне в базе данных
            path_prefix = f"{tg_user_id}/{song_title}.mp3"
            self.db.update_song_path(task_id, path_prefix)

            # Создаем пользователя и сессию
            # tg_user_id из базы уже строковый, но get_or_create_user ожидает int
            user_uuid = self.db.get_or_create_user(int(tg_user_id), full_name=full_name)
            session_uuid = self.db.get_active_session(user_uuid, bot_id, session_lifetime)

            # Отправляем песню пользователю
            self.telegram_bot.send_audio(chat_id=int(tg_user_id), audio_url=processed_song_url, title=song_title)
            # Для callback сообщений используем 0 как tg_msg_id, т.к. это системное сообщение
            self.db.save_message(session_uuid, user_uuid, "assistant", "финальная версия песни получена пользователем", self.llm.embd_text("финальная версия песни получена пользователем"), 0)

            return {"statusCode": 200, "body": ""}

        except Exception as e:
            self.logger.exception("Error handling Suno callback: %s", e)
            return {"statusCode": 500, "body": "Internal server error"}