
try:
    from .config import Config
    from .audio_signer import AudioSigner
    from .audio_watermark import AudioWatermark
except ImportError:
    # Fallback for direct execution
    from config import Config
    from audio_signer import AudioSigner
    from audio_watermark import AudioWatermark

__version__ = "1.0.0"
__all__ = ["Config", "AudioSigner", "AudioWatermark", "__version__"]

# Create a default config instance for convenience
_default_config = None

def get_config():
    """Get the default configuration instance."""
    global _default_config
    if _default_config is None:
        _default_config = Config()
    return _default_config
