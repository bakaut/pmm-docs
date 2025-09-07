"""
Test for MP3 to WAV conversion functionality.
"""

import os
import tempfile
import unittest
from pathlib import Path
import numpy as np
from scipy.io.wavfile import write as wav_write

from .utils import Utils
from .audio_signer import AudioSigner
from .config import Config


class TestMP3Conversion(unittest.TestCase):
    """Test cases for MP3 to WAV conversion and AudioSigner with MP3 support."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for our test files
        self.test_dir = Path(tempfile.mkdtemp())
        
        # Create a mock config
        self.config = Config()
        
        # Create Utils instance
        self.utils = Utils(self.config)
        
        # Create AudioSigner instance with Utils
        self.audio_signer = AudioSigner(utils=self.utils)
        
        # Create a temporary WAV file for testing
        self.wav_path = self.test_dir / "test_audio.wav"
        sample_rate = 44100
        duration = 10  # 10 seconds
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        audio_data = np.sin(440 * 2 * np.pi * t)  # 440 Hz sine wave
        audio_data = (audio_data * 32767).astype(np.int16)  # Convert to 16-bit integers
        wav_write(str(self.wav_path), sample_rate, audio_data)
        
        # Key paths
        self.priv_key_path = self.test_dir / "priv.key"
        self.pub_key_path = self.test_dir / "pub.key"
        self.sidecar_path = self.test_dir / "test_audio.c2pa"

    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up temporary files
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_utils_convert_mp3_to_wav(self):
        """Test that Utils can convert MP3 to WAV."""
        # For this test, we'll just check that the method exists and handles missing files properly
        # since we don't have a real MP3 file to test with
        
        # Test with non-existent file
        with self.assertRaises(FileNotFoundError):
            self.utils.convert_mp3_to_wav(Path("/non/existent/file.mp3"))

    def test_audio_signer_with_wav(self):
        """Test that AudioSigner still works with WAV files."""
        # Generate keys
        self.audio_signer.generate_ed25519_keypair(self.priv_key_path, self.pub_key_path)
        
        # Sign the WAV file
        model = "test-model-v1.0"
        track_id = self.audio_signer.sign_audio(
            self.wav_path, 
            model, 
            self.priv_key_path, 
            self.sidecar_path
        )
        
        # Check that sidecar was created
        self.assertTrue(self.sidecar_path.exists())
        self.assertGreater(self.sidecar_path.stat().st_size, 0)
        
        # Verify the audio
        verify_ok, manifest = self.audio_signer.verify_audio(
            self.wav_path,
            self.sidecar_path,
            self.pub_key_path
        )
        
        # Check verification result
        self.assertTrue(verify_ok)
        
        # Check manifest content
        self.assertIn("c2pa", manifest)
        c2pa = manifest["c2pa"]
        self.assertEqual(c2pa["track_id"], track_id)
        self.assertEqual(c2pa["model"], model)

    def test_audio_signer_mp3_without_utils(self):
        """Test that AudioSigner raises error for MP3 files without Utils."""
        # Create an AudioSigner without Utils
        signer_without_utils = AudioSigner()
        
        # Try to sign an MP3 file (we'll just use a file with .mp3 extension)
        mp3_path = self.test_dir / "test.mp3"
        # Create an empty file with .mp3 extension
        mp3_path.touch()
        
        # Should raise ValueError
        with self.assertRaises(ValueError) as context:
            signer_without_utils.sign_audio(
                mp3_path, 
                "test-model", 
                self.priv_key_path, 
                self.sidecar_path
            )
        
        self.assertIn("MP3 conversion requires Utils instance", str(context.exception))


if __name__ == "__main__":
    unittest.main()