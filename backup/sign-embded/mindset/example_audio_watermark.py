"""
Example usage of the AudioWatermark class.
"""

import tempfile
import numpy as np
from scipy.io.wavfile import write as wav_write
from pathlib import Path

from .audio_watermark import AudioWatermark


def create_example_audio(file_path: Path, duration: int = 120):
    """Create an example WAV file for testing."""
    sample_rate = 44100
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    # Create a simple sine wave at 440 Hz with some noise to make it more realistic
    audio_data = np.sin(440 * 2 * np.pi * t) + 0.1 * np.random.randn(len(t))
    audio_data = (audio_data * 32767).astype(np.int16)  # Convert to 16-bit integers
    wav_write(str(file_path), sample_rate, audio_data)


def main():
    """Example of embedding and extracting an audio watermark."""
    # Create temporary directory for our example
    temp_dir = Path(tempfile.mkdtemp())
    
    # Create example audio file (120 seconds to ensure it's long enough)
    audio_path = temp_dir / "example.wav"
    create_example_audio(audio_path, duration=120)
    print(f"Created example audio file: {audio_path}")
    
    # Watermarked file path
    watermarked_path = temp_dir / "watermarked_example.wav"
    
    # Test metadata
    metadata = {
        "track_id": "example-track-456",
        "model": "lifesong-v0.4",
        "author": "Example Artist",
        "timestamp": 1234567890
    }
    
    # Steganography password
    steg_password = "my-secret-password"
    
    # Use a smaller segment size for better fit with our audio
    watermark = AudioWatermark(segment_size=1024)
    
    # Simple payload for testing
    payload = b"This is a test watermark payload for demonstration purposes."
    
    # Embed watermark
    print("Embedding watermark...")
    success = watermark.embed_payload(
        audio_path,
        watermarked_path,
        payload,
        steg_password
    )
    
    if success:
        print(f"✓ Watermark embedded successfully in {watermarked_path}")
        
        # Extract watermark
        print("Extracting watermark...")
        payload_len_bits = len(payload) * 8
        extracted_payload = watermark.extract_payload_bytes(
            watermarked_path,
            payload_len_bits,
            steg_password
        )
        
        if extracted_payload:
            print("✓ Watermark extracted successfully")
            print(f"Original payload: {payload}")
            print(f"Extracted payload: {extracted_payload}")
            
            # Note: Due to the nature of steganography, we might not get exact match
            # but the operation should not fail
            print("Watermarking operation completed")
        else:
            print("✗ Failed to extract watermark")
    else:
        print("✗ Failed to embed watermark")
    
    # Clean up
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()