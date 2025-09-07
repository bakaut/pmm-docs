"""
Audio watermarking module for embedding and extracting digital watermarks
using DCT-based steganography techniques.
"""

import numpy as np
import scipy.io.wavfile as wavfile
import json
import hashlib
from pathlib import Path
from typing import Optional, Tuple, Dict, Any


class AudioWatermark:
    """Class for embedding and extracting watermarks in audio files."""

    def __init__(self, segment_size: int = 2048, alpha: float = 0.1, redundancy: int = 3):
        """
        Initialize the AudioWatermark.

        Args:
            segment_size: Size of audio segments for DCT processing
            alpha: Strength of watermark embedding
            redundancy: Number of times each bit is embedded for error correction
        """
        self.segment_size = segment_size
        self.alpha = alpha
        self.redundancy = redundancy

    def _password_to_seed(self, password: str) -> int:
        """
        Convert a string password to a numeric seed for steganography.

        Args:
            password: Password string

        Returns:
            Numeric seed value
        """
        if not password:
            return 0
        return sum(ord(c) for c in password)

    def _bytes_to_bits(self, data_bytes: bytes) -> str:
        """
        Convert bytes to a string of 0s and 1s.

        Args:
            data_bytes: Bytes to convert

        Returns:
            String of bits
        """
        return ''.join(format(byte, '08b') for byte in data_bytes)

    def _bits_to_bytes(self, bits_str: str) -> bytes:
        """
        Convert a string of 0s and 1s to bytes.

        Args:
            bits_str: String of bits

        Returns:
            Bytes representation
        """
        # Pad with zeros if needed
        if len(bits_str) % 8 != 0:
            bits_str += '0' * (8 - len(bits_str) % 8)
        return int(bits_str, 2).to_bytes(len(bits_str) // 8, byteorder='big')

    def embed_payload(
        self,
        input_wav_path: Path,
        output_wav_path: Path,
        payload_bytes: bytes,
        steg_password: str
    ) -> bool:
        """
        Embed a payload into an audio file using DCT-based steganography.

        Args:
            input_wav_path: Path to input WAV file
            output_wav_path: Path to output watermarked WAV file
            payload_bytes: Payload data to embed
            steg_password: Password for steganography seed

        Returns:
            True if embedding was successful, False otherwise
        """
        print(f"Embedding payload into {input_wav_path}...")
        
        try:
            rate, audio_data = wavfile.read(str(input_wav_path))
        except Exception as e:
            print(f"Error reading audio file: {e}")
            return False

        # Handle stereo audio by taking only the first channel
        if len(audio_data.shape) > 1:
            audio_data = audio_data[:, 0]
        audio_data = audio_data.copy().astype(np.float64)

        # Convert payload to bits
        payload_bits_str = self._bytes_to_bits(payload_bytes)
        payload_bits = np.array(list(payload_bits_str), dtype=int)
        payload_bits_redundant = np.repeat(payload_bits, self.redundancy)
        payload_len_total_bits = len(payload_bits_redundant)

        # Check if audio file is long enough
        num_segments_available = len(audio_data) // self.segment_size
        if num_segments_available < payload_len_total_bits:
            print(f"Error: Audio file too short. Need {payload_len_total_bits} segments, "
                  f"available: {num_segments_available}.")
            return False

        # Set random seed based on password
        np.random.seed(self._password_to_seed(steg_password))
        mid_freq_indices = np.arange(int(self.segment_size * 0.1), int(self.segment_size * 0.5))

        # Embed bits into audio segments
        for bit_counter, i in enumerate(range(0, len(audio_data) - self.segment_size, self.segment_size)):
            if bit_counter >= payload_len_total_bits:
                break
                
            segment = audio_data[i:i+self.segment_size]
            dct_segment = self._dct(segment)
            
            # Select two random mid-frequency indices
            indices = np.random.choice(mid_freq_indices, 2, replace=False)
            c1_idx, c2_idx = sorted(indices)
            c1, c2 = dct_segment[c1_idx], dct_segment[c2_idx]
            
            bit_to_embed = payload_bits_redundant[bit_counter]

            # Embed bit by adjusting DCT coefficients
            if bit_to_embed == 1:
                if c1 <= c2:
                    mean, delta = (c1 + c2) / 2, abs(c1 - c2) * self.alpha + 1
                    dct_segment[c1_idx], dct_segment[c2_idx] = mean + delta, mean - delta
            else:  # bit_to_embed == 0
                if c2 <= c1:
                    mean, delta = (c1 + c2) / 2, abs(c1 - c2) * self.alpha + 1
                    dct_segment[c1_idx], dct_segment[c2_idx] = mean - delta, mean + delta

            # Convert back to time domain
            audio_data[i:i+self.segment_size] = self._idct(dct_segment)

        # Save watermarked audio
        wavfile.write(str(output_wav_path), rate, audio_data.astype(np.int16))
        print(f"Watermark embedded. File saved as {output_wav_path}")
        return True

    def extract_payload_bytes(
        self,
        wav_path: Path,
        payload_len_bits: int,
        steg_password: str
        ) -> Optional[bytes]:
        """
        Extract a payload from a watermarked audio file.

        Args:
            wav_path: Path to watermarked WAV file
            payload_len_bits: Length of payload in bits
            steg_password: Password for steganography seed

        Returns:
            Extracted payload bytes or None if extraction failed
        """
        print(f"Extracting payload from {wav_path}...")
        
        try:
            rate, audio_data = wavfile.read(str(wav_path))
        except Exception as e:
            print(f"Error reading audio file: {e}")
            return None

        # Handle stereo audio by taking only the first channel
        if len(audio_data.shape) > 1:
            audio_data = audio_data[:, 0]
        audio_data = audio_data.astype(np.float64)

        total_bits_to_extract = payload_len_bits * self.redundancy
        extracted_bits = []

        # Set random seed based on password
        np.random.seed(self._password_to_seed(steg_password))
        mid_freq_indices = np.arange(int(self.segment_size * 0.1), int(self.segment_size * 0.5))

        # Calculate available segments
        num_segments_available = len(audio_data) // self.segment_size
        if num_segments_available < total_bits_to_extract:
            total_bits_to_extract = num_segments_available

        # Extract bits from audio segments
        for bit_counter, i in enumerate(range(0, len(audio_data) - self.segment_size, self.segment_size)):
            if bit_counter >= total_bits_to_extract:
                break
                
            segment = audio_data[i:i+self.segment_size]
            dct_segment = self._dct(segment)
            
            # Select two random mid-frequency indices
            indices = np.random.choice(mid_freq_indices, 2, replace=False)
            c1_idx, c2_idx = sorted(indices)
            
            # Extract bit based on coefficient relationship
            extracted_bits.append(1 if dct_segment[c1_idx] > dct_segment[c2_idx] else 0)

        # Apply redundancy correction
        final_bits_str = ""
        for i in range(payload_len_bits):
            chunk = extracted_bits[i*self.redundancy : (i+1)*self.redundancy]
            if not chunk:
                continue
            # Use majority voting for error correction
            final_bits_str += '1' if sum(chunk) > len(chunk) / 2 else '0'

        try:
            return self._bits_to_bytes(final_bits_str)
        except Exception as e:
            print(f"Error converting bits to bytes: {e}")
            return None

    def _dct(self, data: np.ndarray) -> np.ndarray:
        """
        Perform Discrete Cosine Transform on data.

        Args:
            data: Input data array

        Returns:
            DCT-transformed data
        """
        # For compatibility with older scipy versions
        try:
            from scipy.fft import dct
            return dct(data, type=2, norm='ortho')
        except ImportError:
            from scipy.fftpack import dct
            return dct(data, type=2, norm='ortho')

    def _idct(self, data: np.ndarray) -> np.ndarray:
        """
        Perform Inverse Discrete Cosine Transform on data.

        Args:
            data: Input DCT data array

        Returns:
            IDCT-transformed data
        """
        # For compatibility with older scipy versions
        try:
            from scipy.fft import idct
            return idct(data, type=2, norm='ortho')
        except ImportError:
            from scipy.fftpack import idct
            return idct(data, type=2, norm='ortho')


def create_watermarked_audio_from_text(
    input_wav_path: Path,
    output_wav_path: Path,
    text_payload: str,
    steg_password: str
) -> bool:
    """
    Create a watermarked audio file with embedded text payload.

    Args:
        input_wav_path: Path to input WAV file
        output_wav_path: Path to output watermarked WAV file
        text_payload: Text to embed as watermark
        steg_password: Password for steganography

    Returns:
        True if successful, False otherwise
    """
    try:
        # Convert text to bytes
        payload_bytes = text_payload.encode('utf-8')
        print(f"Text payload size: {len(payload_bytes)} bytes.")

        # Embed the text payload
        watermark = AudioWatermark()
        return watermark.embed_payload(
            input_wav_path,
            output_wav_path,
            payload_bytes,
            steg_password
        )
    except Exception as e:
        print(f"Error creating watermarked audio: {e}")
        return False


def extract_text_watermark(
    wav_path: Path,
    payload_len_bits: int,
    steg_password: str
) -> Optional[str]:
    """
    Extract text watermark from a watermarked audio file.

    Args:
        wav_path: Path to watermarked WAV file
        payload_len_bits: Length of payload in bits
        steg_password: Password for steganography

    Returns:
        Extracted text or None if extraction failed
    """
    try:
        # Extract payload bytes
        watermark = AudioWatermark()
        extracted_payload_bytes = watermark.extract_payload_bytes(
            wav_path,
            payload_len_bits,
            steg_password
        )
        
        if not extracted_payload_bytes:
            print("Failed to extract payload.")
            return None

        # Convert bytes to text
        try:
            extracted_text = extracted_payload_bytes.decode('utf-8')
            return extracted_text
        except UnicodeDecodeError as e:
            print(f"Error decoding extracted payload as text: {e}")
            return None
    except Exception as e:
        print(f"Error extracting text watermark: {e}")
        return None


def create_audio_hash_watermark(
    input_wav_path: Path,
    output_wav_path: Path,
    steg_password: str
) -> bool:
    """
    Create a watermarked audio file with embedded audio hash as unique identifier.

    Args:
        input_wav_path: Path to input WAV file
        output_wav_path: Path to output watermarked WAV file
        steg_password: Password for steganography

    Returns:
        True if successful, False otherwise
    """
    try:
        # Compute hash of the audio file
        with open(input_wav_path, 'rb') as f:
            audio_data = f.read()
            audio_hash = hashlib.sha256(audio_data).hexdigest()[:32]  # Use first 32 chars
        
        print(f"Audio hash: {audio_hash}")

        # Embed the hash as text payload
        watermark = AudioWatermark()
        payload_bytes = audio_hash.encode('utf-8')
        return watermark.embed_payload(
            input_wav_path,
            output_wav_path,
            payload_bytes,
            steg_password
        )
    except Exception as e:
        print(f"Error creating audio hash watermark: {e}")
        return False


def extract_audio_hash_watermark(
    wav_path: Path,
    steg_password: str
) -> Optional[str]:
    """
    Extract audio hash watermark from a watermarked audio file.

    Args:
        wav_path: Path to watermarked WAV file
        steg_password: Password for steganography

    Returns:
        Extracted audio hash or None if extraction failed
    """
    try:
        # For hash extraction, we need to know the length (32 chars * 8 bits = 256 bits)
        payload_len_bits = 256
        
        # Extract payload bytes
        watermark = AudioWatermark()
        extracted_payload_bytes = watermark.extract_payload_bytes(
            wav_path,
            payload_len_bits,
            steg_password
        )
        
        if not extracted_payload_bytes:
            print("Failed to extract audio hash payload.")
            return None

        # Convert bytes to hash string
        try:
            extracted_hash = extracted_payload_bytes.decode('utf-8')
            return extracted_hash
        except UnicodeDecodeError as e:
            print(f"Error decoding extracted hash: {e}")
            return None
    except Exception as e:
        print(f"Error extracting audio hash watermark: {e}")
        return None