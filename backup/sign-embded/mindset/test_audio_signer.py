"""
Unit tests for the AudioSigner class.
"""

import os
import tempfile
import unittest
from pathlib import Path
import numpy as np
import soundfile as sf

from .audio_signer import AudioSigner


class TestAudioSigner(unittest.TestCase):
    """Test cases for the AudioSigner class."""

    def setUp(self):
        """Set up test fixtures."""
        self.signer = AudioSigner(hash_duration=5)  # Use 5 seconds for faster tests
        self.test_dir = Path(tempfile.mkdtemp())
        
        # Create a temporary WAV file for testing
        self.audio_path = self.test_dir / "test_audio.wav"
        sample_rate = 44100
        duration = 10  # 10 seconds
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        audio_data = np.sin(440 * 2 * np.pi * t)  # 440 Hz sine wave
        sf.write(str(self.audio_path), audio_data, sample_rate)
        
        # Key paths
        self.priv_key_path = self.test_dir / "priv.key"
        self.pub_key_path = self.test_dir / "pub.key"
        self.sidecar_path = self.test_dir / "test_audio.c2pa"

    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up temporary files
        for path in [self.audio_path, self.priv_key_path, self.pub_key_path, self.sidecar_path]:
            if path.exists():
                path.unlink()
        self.test_dir.rmdir()

    def test_generate_ed25519_keypair(self):
        """Test generating an Ed25519 key pair."""
        self.signer.generate_ed25519_keypair(self.priv_key_path, self.pub_key_path)
        
        # Check that both files were created
        self.assertTrue(self.priv_key_path.exists())
        self.assertTrue(self.pub_key_path.exists())
        
        # Check that files are not empty
        self.assertGreater(self.priv_key_path.stat().st_size, 0)
        self.assertGreater(self.pub_key_path.stat().st_size, 0)

    def test_load_keys(self):
        """Test loading Ed25519 keys."""
        # First generate keys
        self.signer.generate_ed25519_keypair(self.priv_key_path, self.pub_key_path)
        
        # Test loading private key
        priv_key = self.signer.load_private_key(self.priv_key_path)
        self.assertIsNotNone(priv_key)
        
        # Test loading public key
        pub_key = self.signer.load_public_key(self.pub_key_path)
        self.assertIsNotNone(pub_key)

    def test_compute_audio_hash(self):
        """Test computing audio hash."""
        # Compute hash of our test audio
        audio_hash = self.signer.compute_audio_hash(self.audio_path)
        
        # Check that we get a valid hex string
        self.assertIsInstance(audio_hash, str)
        self.assertEqual(len(audio_hash), 64)  # SHA-256 produces 64 hex chars
        self.assertTrue(all(c in '0123456789abcdef' for c in audio_hash))

    def test_build_manifest(self):
        """Test building a manifest."""
        track_id = "test-track-123"
        model = "test-model-v1.0"
        audio_hash = "abcdef1234567890" * 4  # 64 chars
        
        manifest = self.signer.build_manifest(track_id, model, audio_hash)
        
        # Check manifest structure
        self.assertIn("c2pa", manifest)
        c2pa = manifest["c2pa"]
        self.assertEqual(c2pa["version"], "0.9")
        self.assertEqual(c2pa["track_id"], track_id)
        self.assertEqual(c2pa["model"], model)
        self.assertEqual(c2pa["hash"], audio_hash)
        self.assertIn("unix_ts", c2pa)
        self.assertIsInstance(c2pa["unix_ts"], int)

    def test_sign_and_verify_audio(self):
        """Test signing and verifying an audio file."""
        # Generate keys
        self.signer.generate_ed25519_keypair(self.priv_key_path, self.pub_key_path)
        
        # Sign the audio
        model = "test-model-v1.0"
        track_id = self.signer.sign_audio(
            self.audio_path, 
            model, 
            self.priv_key_path, 
            self.sidecar_path
        )
        
        # Check that sidecar was created
        self.assertTrue(self.sidecar_path.exists())
        self.assertGreater(self.sidecar_path.stat().st_size, 0)
        
        # Verify the audio
        verify_ok, manifest = self.signer.verify_audio(
            self.audio_path,
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
        
        # Verify the hash matches
        audio_hash = self.signer.compute_audio_hash(self.audio_path)
        self.assertEqual(c2pa["hash"], audio_hash)

    def test_verify_with_tampered_audio(self):
        """Test that verification fails with tampered audio."""
        # Generate keys
        self.signer.generate_ed25519_keypair(self.priv_key_path, self.pub_key_path)
        
        # Sign the original audio
        self.signer.sign_audio(
            self.audio_path, 
            "test-model-v1.0", 
            self.priv_key_path, 
            self.sidecar_path
        )
        
        # Create tampered audio (different frequency)
        tampered_path = self.test_dir / "tampered_audio.wav"
        sample_rate = 44100
        duration = 10  # 10 seconds
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        audio_data = np.sin(880 * 2 * np.pi * t)  # 880 Hz sine wave (different from original)
        sf.write(str(tampered_path), audio_data, sample_rate)
        
        # Verification should fail
        verify_ok, _ = self.signer.verify_audio(
            tampered_path,
            self.sidecar_path,
            self.pub_key_path
        )
        
        self.assertFalse(verify_ok)
        
        # Clean up
        tampered_path.unlink()


if __name__ == "__main__":
    unittest.main()