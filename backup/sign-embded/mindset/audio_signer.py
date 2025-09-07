"""
C2PA-style audio signing and verification module.

This module provides classes for signing and verifying audio files using C2PA-style
manifests wrapped in COSE_Sign1 containers with Ed25519 signatures.
"""

import argparse
import base64
import os
import sys
import time
import uuid
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

import cbor2
from pycose.messages import Sign1Message, CoseMessage
from pycose.keys import CoseKey
from pycose.keys.okp import OKPKey
from pycose.keys.curves import Ed25519
from pycose.keys.keyparam import KpKty, OKPKpCurve, OKPKpD, OKPKpX
from pycose.keys.keytype import KtyOKP
from pycose.algorithms import EdDSA
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
import soundfile as sf

# Import watermarking functionality
try:
    from .audio_watermark import AudioWatermark, create_watermarked_audio_from_text, extract_text_watermark, create_audio_hash_watermark, extract_audio_hash_watermark
    WATERMARKING_AVAILABLE = True
except ImportError:
    WATERMARKING_AVAILABLE = False
    AudioWatermark = None
    create_watermarked_audio_from_text = None
    extract_text_watermark = None
    create_audio_hash_watermark = None
    extract_audio_hash_watermark = None


class AudioSigner:
    """Class for signing and verifying audio files with C2PA-style manifests."""

    def __init__(self, hash_duration: int = 15, utils=None):
        """
        Initialize the AudioSigner.

        Args:
            hash_duration: Duration in seconds of audio to hash (default: 15)
            utils: Utils instance for audio conversion (optional)
        """
        self.hash_duration = hash_duration
        self.utils = utils

    def generate_ed25519_keypair(self, priv_path: Path, pub_path: Path) -> None:
        """
        Create and store an Ed25519 private/public key pair.

        Args:
            priv_path: Path to save the private key
            pub_path: Path to save the public key
        """
        sk = ed25519.Ed25519PrivateKey.generate()
        pk = sk.public_key()
        priv_path.write_bytes(
            sk.private_bytes(
                serialization.Encoding.Raw,
                serialization.PrivateFormat.Raw,
                serialization.NoEncryption(),
            )
        )
        pub_path.write_bytes(
            pk.public_bytes(
                serialization.Encoding.Raw,
                serialization.PublicFormat.Raw,
            )
        )

    def load_private_key(self, path: Path) -> ed25519.Ed25519PrivateKey:
        """
        Load an Ed25519 private key from a file.

        Args:
            path: Path to the private key file

        Returns:
            Ed25519 private key object
        """
        return ed25519.Ed25519PrivateKey.from_private_bytes(path.read_bytes())

    def load_public_key(self, path: Path) -> ed25519.Ed25519PublicKey:
        """
        Load an Ed25519 public key from a file.

        Args:
            path: Path to the public key file

        Returns:
            Ed25519 public key object
        """
        return ed25519.Ed25519PublicKey.from_public_bytes(path.read_bytes())

    def _get_wav_path(self, audio_path: Path) -> Path:
        """
        Get WAV path for an audio file, converting from MP3 if necessary.

        Args:
            audio_path: Path to the audio file

        Returns:
            Path to the WAV file

        Raises:
            ValueError: If MP3 conversion is needed but Utils is not available
            ImportError: If pydub is needed but not available
        """
        # If it's already a WAV file, return as is
        if audio_path.suffix.lower() == ".wav":
            return audio_path
            
        # If it's an MP3 file and we have utils, convert it
        if audio_path.suffix.lower() == ".mp3" and self.utils is not None:
            try:
                # Create temporary WAV file
                wav_path = Path(tempfile.mktemp(suffix=".wav"))
                return self.utils.convert_mp3_to_wav(audio_path, wav_path)
            except ImportError as e:
                raise ImportError(f"MP3 conversion requires pydub: {e}")
            
        # If it's an MP3 file but we don't have utils, raise an error
        if audio_path.suffix.lower() == ".mp3":
            raise ValueError("MP3 conversion requires Utils instance. Please provide utils parameter to AudioSigner.")
            
        # For other formats, assume it can be read by soundfile
        return audio_path

    def compute_audio_hash(self, wav_path: Path) -> str:
        """
        Compute SHA-256 hash of the first N seconds of raw PCM audio.

        Args:
            wav_path: Path to the WAV/AIFF audio file

        Returns:
            Hex digest of the SHA-256 hash
        """
        data, sr = sf.read(str(wav_path), dtype="int16")
        num_samples = min(len(data), sr * self.hash_duration)
        raw_bytes = data[:num_samples].tobytes()
        return hashlib.sha256(raw_bytes).hexdigest()

    def build_manifest(self, track_id: str, model: str, audio_hash: str, watermark_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Build a C2PA-style manifest.

        Args:
            track_id: Unique identifier for the track
            model: Model name used for generation
            audio_hash: Hash of the audio content
            watermark_info: Information about watermark (optional)

        Returns:
            Dictionary representing the manifest
        """
        manifest = {
            "c2pa": {
                "version": "0.9",
                "track_id": track_id,
                "model": model,
                "unix_ts": int(time.time()),
                "hash": audio_hash,
            }
        }
        
        # Add watermark information if provided
        if watermark_info:
            manifest["c2pa"]["watermark"] = watermark_info
            
        return manifest

    def sign_manifest(self, manifest: Dict[str, Any], priv_key: ed25519.Ed25519PrivateKey) -> bytes:
        """
        Sign a manifest with an Ed25519 private key.

        Args:
            manifest: The manifest to sign
            priv_key: The private key for signing

        Returns:
            COSE_Sign1 encoded bytes
        """
        payload = cbor2.dumps(manifest, canonical=True)
        
        # Create the COSE key from the private key
        priv_bytes = priv_key.private_bytes(
            serialization.Encoding.Raw,
            serialization.PrivateFormat.Raw,
            serialization.NoEncryption(),
        )
        
        cose_key = OKPKey.from_dict(
            {
                KpKty: KtyOKP.identifier,
                OKPKpCurve: Ed25519,
                OKPKpD: priv_bytes,
            }
        )
        
        msg = Sign1Message(phdr={1: EdDSA}, uhdr={}, payload=payload)
        msg.key = cose_key
        return msg.encode(sign=True)

    def verify_sidecar(self, sidecar_bytes: bytes, pub_key: ed25519.Ed25519PublicKey) -> Tuple[Dict[str, Any], bool]:
        """
        Verify a signed sidecar file.

        Args:
            sidecar_bytes: The signed sidecar bytes
            pub_key: The public key for verification

        Returns:
            Tuple of (manifest, signature_valid)
        """
        msg: Sign1Message = CoseMessage.decode(sidecar_bytes)
        
        # Create the COSE key from the public key
        pub_bytes = pub_key.public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
        
        cose_key = OKPKey.from_dict(
            {
                KpKty: KtyOKP.identifier,
                OKPKpCurve: Ed25519,
                OKPKpX: pub_bytes,
            }
        )
        
        msg.key = cose_key
        sig_ok = msg.verify_signature()
        manifest = cbor2.loads(msg.payload)
        return manifest, sig_ok

    def sign_audio(self, audio_path: Path, model: str, priv_key_path: Path, output_path: Path, 
                   watermark_password: Optional[str] = None, watermark_text: Optional[str] = None,
                   embed_audio_hash: bool = False) -> str:
        """
        Sign an audio file and create a C2PA sidecar.

        Args:
            audio_path: Path to the audio file (WAV or MP3)
            model: Model name used for generation
            priv_key_path: Path to the private key file
            output_path: Path for the output sidecar file
            watermark_password: Password for audio watermark (optional)
            watermark_text: Text to embed as watermark (optional)
            embed_audio_hash: Whether to embed audio hash as watermark (optional)

        Returns:
            Track ID of the signed audio
        """
        # Convert to WAV if necessary
        wav_path = self._get_wav_path(audio_path)
        
        try:
            # If watermarking is requested and available, create watermarked version
            watermark_info = None
            if watermark_password and WATERMARKING_AVAILABLE:
                # Create watermarked version
                watermarked_path = Path(tempfile.mktemp(suffix=".wav"))
                
                if embed_audio_hash:
                    # Embed audio hash as watermark
                    if create_audio_hash_watermark(wav_path, watermarked_path, watermark_password):
                        # Use watermarked audio for signing
                        wav_path = watermarked_path
                        print(f"Created audio hash watermarked audio: {watermarked_path}")
                        watermark_info = {"type": "audio_hash", "method": "dct_steganography"}
                    else:
                        print("Failed to create audio hash watermarked audio, using original")
                elif watermark_text:
                    # Embed text as watermark
                    if create_watermarked_audio_from_text(wav_path, watermarked_path, watermark_text, watermark_password):
                        # Use watermarked audio for signing
                        wav_path = watermarked_path
                        print(f"Created text watermarked audio: {watermarked_path}")
                        watermark_info = {"type": "text", "content": watermark_text, "method": "dct_steganography"}
                    else:
                        print("Failed to create text watermarked audio, using original")
                else:
                    # Create a simple watermark with track info
                    track_info = f"track_id:{uuid.uuid4()}"
                    if create_watermarked_audio_from_text(wav_path, watermarked_path, track_info, watermark_password):
                        # Use watermarked audio for signing
                        wav_path = watermarked_path
                        print(f"Created track info watermarked audio: {watermarked_path}")
                        watermark_info = {"type": "track_info", "method": "dct_steganography"}
                    else:
                        print("Failed to create track info watermarked audio, using original")

            # Load private key
            priv_key = self.load_private_key(priv_key_path)
            
            # Generate track ID
            track_id = str(uuid.uuid4())
            
            # Compute audio hash
            audio_hash = self.compute_audio_hash(wav_path)
            
            # Build manifest
            manifest = self.build_manifest(track_id, model, audio_hash, watermark_info)
            
            # Sign manifest
            signed = self.sign_manifest(manifest, priv_key)
            
            # Save to output file
            output_path.write_bytes(signed)
            
            return track_id
        finally:
            # Clean up temporary WAV file if we created one
            if wav_path != audio_path and wav_path.exists():
                wav_path.unlink()

    def verify_audio(self, audio_path: Path, sidecar_path: Path, pub_key_path: Path) -> Tuple[bool, Dict[str, Any]]:
        """
        Verify an audio file against its C2PA sidecar.

        Args:
            audio_path: Path to the audio file (WAV or MP3)
            sidecar_path: Path to the sidecar file
            pub_key_path: Path to the public key file

        Returns:
            Tuple of (verification_passed, manifest)
        """
        # Convert to WAV if necessary
        wav_path = self._get_wav_path(audio_path)
        
        try:
            # Load public key
            pub_key = self.load_public_key(pub_key_path)
            
            # Load sidecar bytes
            sidecar_bytes = sidecar_path.read_bytes()
            
            # Verify sidecar
            manifest, sig_ok = self.verify_sidecar(sidecar_bytes, pub_key)
            
            # Compute audio hash
            audio_hash = self.compute_audio_hash(wav_path)
            
            # Check hash match
            hash_ok = audio_hash == manifest["c2pa"]["hash"]
            
            return (sig_ok and hash_ok), manifest
        finally:
            # Clean up temporary WAV file if we created one
            if wav_path != audio_path and wav_path.exists():
                wav_path.unlink()

    def format_manifest_pretty(self, manifest: Dict[str, Any]) -> str:
        """
        Format a manifest as a pretty JSON string.

        Args:
            manifest: The manifest to format

        Returns:
            Pretty formatted JSON string
        """
        return json.dumps(manifest, indent=2, ensure_ascii=False)


def main():
    """Command-line interface for the AudioSigner."""
    signer = AudioSigner()
    
    p = argparse.ArgumentParser(description="C2PA-style Sign / Verify for audio tracks")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("gen-keys", help="Generate Ed25519 key pair")
    g.add_argument("priv", type=Path, help="Private key file (output)")
    g.add_argument("pub", type=Path, help="Public key file (output)")

    s = sub.add_parser("sign", help="Sign WAV/AIFF audio and produce .c2pa sidecar")
    s.add_argument("audio", type=Path)
    s.add_argument("--model", default="lifesong-v0.4")
    s.add_argument("--priv", type=Path, required=True)
    s.add_argument("--out", type=Path, required=True)
    s.add_argument("--hash-duration", type=int, default=15, help="Seconds of audio to hash")
    s.add_argument("--watermark-password", type=str, help="Password for audio watermark")
    s.add_argument("--watermark-text", type=str, help="Text to embed as watermark")
    s.add_argument("--embed-audio-hash", action="store_true", help="Embed audio hash as watermark")

    v = sub.add_parser("verify", help="Verify audio vs .c2pa sidecar")
    v.add_argument("audio", type=Path)
    v.add_argument("sidecar", type=Path)
    v.add_argument("--pub", type=Path, required=True)
    v.add_argument("--hash-duration", type=int, default=15)

    args = p.parse_args()

    if args.cmd == "gen-keys":
        signer.generate_ed25519_keypair(args.priv, args.pub)
        print(f"Keys written to {args.priv} and {args.pub}")

    elif args.cmd == "sign":
        if args.hash_duration != signer.hash_duration:
            signer.hash_duration = args.hash_duration
        track_id = signer.sign_audio(
            args.audio, 
            args.model, 
            args.priv, 
            args.out, 
            args.watermark_password,
            args.watermark_text,
            args.embed_audio_hash
        )
        print(f"Signed manifest written to {args.out}\ntrack_id={track_id}")

    elif args.cmd == "verify":
        if args.hash_duration != signer.hash_duration:
            signer.hash_duration = args.hash_duration
        verify_ok, manifest = signer.verify_audio(args.audio, args.sidecar, args.pub)
        if verify_ok:
            print("✔ Signature and audio hash valid")
            print(signer.format_manifest_pretty(manifest))
        else:
            print("✗ Signature or audio hash invalid")
            print(signer.format_manifest_pretty(manifest))


if __name__ == "__main__":
    main()