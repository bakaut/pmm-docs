"""
Integration test for audio signing in SunoManager.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import soundfile as sf

from .suno_manager import SunoManager
from .config import Config


class TestSunoAudioSigning(unittest.TestCase):
    """Test cases for audio signing integration in SunoManager."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for our test files
        self.test_dir = Path(tempfile.mkdtemp())
        
        # Create a temporary WAV file for testing
        self.audio_path = self.test_dir / "test_audio.mp3"
        sample_rate = 44100
        duration = 10  # 10 seconds
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        audio_data = np.sin(440 * 2 * np.pi * t)  # 440 Hz sine wave
        sf.write(str(self.audio_path), audio_data, sample_rate)
        
        # Create mock objects for dependencies
        self.config = Mock(spec=Config)
        self.config.suno_model = "test-model-v1.0"
        self.config.song_path = str(self.test_dir)
        self.config.song_bucket_name = "test-bucket"
        self.config.ai_composer = "AI Composer"
        self.config.connect_timeout = 10
        self.config.read_timeout = 30
        self.config.audio_signing_enabled = True
        self.config.audio_signing_private_key_path = str(self.test_dir / "private.key")
        
        # Create mock keys
        from .audio_signer import AudioSigner
        signer = AudioSigner()
        signer.generate_ed25519_keypair(
            Path(self.config.audio_signing_private_key_path),
            self.test_dir / "public.key"
        )
        
        self.db = Mock()
        self.telegram_bot = Mock()
        self.utils = Mock()
        self.llm = Mock()
        self.logger = Mock()
        
        # Create SunoManager instance
        self.suno_manager = SunoManager(
            self.config, self.db, self.telegram_bot, self.utils, self.llm, self.logger
        )

    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up temporary files
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch("boto3.client")
    @patch("requests.get")
    def test_download_and_process_song_with_signing(self, mock_requests_get, mock_boto3_client):
        """Test that download_and_process_song signs the audio when enabled."""
        # Mock the requests response
        mock_response = Mock()
        mock_response.content = self.audio_path.read_bytes()
        mock_requests_get.return_value = mock_response
        
        # Mock the S3 client
        mock_s3_client = Mock()
        mock_boto3_client.return_value = mock_s3_client
        
        # Call the method
        song_url = "http://example.com/song.mp3"
        result_url = self.suno_manager.download_and_process_song(
            song_url=song_url,
            tg_user_id="123456",
            song_title="Test Song",
            song_artist="Test Artist",
            local_folder=str(self.test_dir),
            song_bucket_name="test-bucket"
        )
        
        # Verify that the audio file was signed
        sidecar_path = self.test_dir / "123456" / "Test Song.c2pa"
        self.assertTrue(sidecar_path.exists(), "Sidecar file should be created when signing is enabled")
        
        # Verify that the sidecar was uploaded
        # We need to check if upload_file was called with the sidecar path
        upload_calls = [call for call in mock_s3_client.upload_file.call_args_list 
                       if "Test Song.c2pa" in str(call[0][2])]
        self.assertTrue(len(upload_calls) > 0, "Sidecar file should be uploaded to S3")


if __name__ == "__main__":
    unittest.main()