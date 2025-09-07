"""Client for interacting with the Suno API and object storage.

Each method has a clear purpose (download, tag, upload, or request
generation), following Clean Code principles. Functions are small and
self‑explanatory. Using SQLAlchemy does not affect this module, but
we still honour meaningful naming and modularity.
"""

import os
from typing import Any, Dict, Optional

import boto3
import requests
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3

from .config import Config


class SunoClient:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.session = requests.Session()

    def generate_signed_url(self, bucket: str, key: str, expires_in: int = 3600) -> str:
        s3 = boto3.client('s3')
        return s3.generate_presigned_url(
            ClientMethod='get_object',
            Params={'Bucket': bucket, 'Key': key},
            ExpiresIn=expires_in,
        )

    def download_and_process_song(self, song_url: str, tg_user_id: str, song_title: str, song_artist: str) -> str:
        user_folder = os.path.join('/function/storage/songs/', tg_user_id)
        os.makedirs(user_folder, exist_ok=True)
        local_path = os.path.join(user_folder, f"{song_title}.mp3")
        song_key = f"{tg_user_id}/{song_title}.mp3"
        response = requests.get(song_url)
        response.raise_for_status()
        with open(local_path, 'wb') as f:
            f.write(response.content)
        audio = MP3(local_path, ID3=EasyID3)
        audio['title'] = song_title
        audio['artist'] = song_artist
        audio['composer'] = 'AI сгенерировано с помощью https://t.me/PoyMoyMirBot'
        audio.save()
        if not self.config.song_bucket_name:
            raise RuntimeError('song_bucket_name is not configured')
        return self.generate_signed_url(bucket=self.config.song_bucket_name, key=song_key)

    def request_song(self, prompt: str, style: str, title: str) -> Dict[str, Any]:
        if not (self.config.suno_api_key and self.config.suno_callback_url):
            return {}
        payload = {
            'prompt': prompt,
            'style': style,
            'title': title,
            'customMode': True,
            'instrumental': False,
            'model': self.config.suno_model,
            'callBackUrl': self.config.suno_callback_url,
        }
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.config.suno_api_key}',
        }
        resp = self.session.post(self.config.suno_api_url, json=payload, headers=headers, timeout=(self.config.connect_timeout, self.config.read_timeout))
        resp.raise_for_status()
        return resp.json()