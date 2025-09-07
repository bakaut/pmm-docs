"""
Example usage of the AudioSigner class.
"""

import tempfile
import numpy as np
import soundfile as sf
from pathlib import Path

from .audio_signer import AudioSigner


def create_example_audio(file_path: Path, duration: int = 10):
    """Create an example WAV file for testing."""
    sample_rate = 44100
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    # Create a simple sine wave at 440 Hz
    audio_data = np.sin(440 * 2 * np.pi * t)
    sf.write(str(file_path), audio_data, sample_rate)


def main():
    """Example of signing and verifying an audio file."""
    # Create temporary directory for our example
    temp_dir = Path(tempfile.mkdtemp())
    
    # Create example audio file
    audio_path = temp_dir / "example.wav"
    create_example_audio(audio_path)
    print(f"Created example audio file: {audio_path}")
    
    # Key paths
    priv_key_path = temp_dir / "private.key"
    pub_key_path = temp_dir / "public.key"
    sidecar_path = temp_dir / "example.c2pa"
    
    # Create signer
    signer = AudioSigner(hash_duration=5)  # Hash first 5 seconds
    
    # Generate key pair
    signer.generate_ed25519_keypair(priv_key_path, pub_key_path)
    print(f"Generated key pair: {priv_key_path}, {pub_key_path}")
    
    # Sign the audio file
    model_name = "lifesong-v0.4"
    track_id = signer.sign_audio(audio_path, model_name, priv_key_path, sidecar_path)
    print(f"Signed audio file with track ID: {track_id}")
    print(f"Sidecar file created: {sidecar_path}")
    
    # Verify the audio file
    verify_ok, manifest = signer.verify_audio(audio_path, sidecar_path, pub_key_path)
    
    if verify_ok:
        print("✅ Verification successful!")
        print("Manifest contents:")
        print(signer.format_manifest_pretty(manifest))
    else:
        print("❌ Verification failed!")
    
    # Clean up
    for path in [audio_path, priv_key_path, pub_key_path, sidecar_path]:
        if path.exists():
            path.unlink()
    temp_dir.rmdir()


if __name__ == "__main__":
    main()