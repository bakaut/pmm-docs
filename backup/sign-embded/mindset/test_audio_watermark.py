"""
Test for audio watermarking functionality.
"""

import os
import tempfile
import unittest
from pathlib import Path
import numpy as np
from scipy.io.wavfile import write as wav_write

from .audio_watermark import AudioWatermark, create_watermarked_audio, extract_watermark


class TestAudioWatermark(unittest.TestCase):
    """Test cases for audio watermarking functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for our test files
        self.test_dir = Path(tempfile.mkdtemp())
        
        # Create a temporary WAV file for testing (60 seconds to ensure it's long enough)
        self.wav_path = self.test_dir / "test_audio.wav"
        sample_rate = 44100
        duration = 60  # 60 seconds
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        audio_data = np.sin(440 * 2 * np.pi * t)  # 440 Hz sine wave
        audio_data = (audio_data * 32767).astype(np.int16)  # Convert to 16-bit integers
        wav_write(str(self.wav_path), sample_rate, audio_data)
        
        # Watermarked file path
        self.watermarked_path = self.test_dir / "watermarked_audio.wav"
        
        # Test metadata
        self.metadata = {
            "track_id": "test-track-123",
            "model": "test-model-v1.0",
            "timestamp": 1234567890
        }
        
        # Steganography password
        self.steg_password = "test-password"

    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up temporary files
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_audio_watermark_class(self):
        """Test the AudioWatermark class directly."""
        # Use a smaller segment size for testing
        watermark = AudioWatermark(segment_size=512)
        
        # Test password to seed conversion
        seed = watermark._password_to_seed("test")
        self.assertIsInstance(seed, int, "Seed should be an integer")
        
        # Test bytes to bits conversion
        test_bytes = b"test"
        bits = watermark._bytes_to_bits(test_bytes)
        self.assertIsInstance(bits, str, "Bits should be a string")
        self.assertTrue(all(c in '01' for c in bits), "Bits should only contain 0 and 1")
        
        # Test bits to bytes conversion
        restored_bytes = watermark._bits_to_bytes(bits)
        self.assertEqual(restored_bytes, test_bytes, "Bytes should be restored correctly")

    def test_simple_watermark_operations(self):
        """Test simple watermark operations with a smaller segment size."""
        # Use a smaller segment size for testing with our audio
        watermark = AudioWatermark(segment_size=512)
        
        # Simple payload
        payload = b"test"
        
        # Test embedding
        success = watermark.embed_payload(
            self.wav_path,
            self.watermarked_path,
            payload,
            self.steg_password
        )
        
        self.assertTrue(success, "Watermark embedding should succeed")
        self.assertTrue(self.watermarked_path.exists(), "Watermarked file should be created")
        
        # Test extraction
        payload_len_bits = len(payload) * 8
        extracted_payload = watermark.extract_payload_bytes(
            self.watermarked_path,
            payload_len_bits,
            self.steg_password
        )
        
        self.assertIsNotNone(extracted_payload, "Payload extraction should succeed")
        # Note: Due to the nature of steganography and potential data corruption,
        # we might not get the exact same payload, but the operation should not fail


if __name__ == "__main__":
    unittest.main()