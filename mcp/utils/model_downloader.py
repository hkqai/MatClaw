"""
Model downloading and caching utilities for MatClaw.

This module handles automatic downloading of model files from GitHub releases
and caches them locally according to XDG Base Directory specification.
"""

import os
import urllib.request
import urllib.error
from pathlib import Path
import sys


# Model URLs from GitHub releases
MODEL_URLS = {
    'elemwiseretro_precursor_predictor': 'https://github.com/VCERS/MatClaw/releases/download/v0.0.3/elemwiseretro-precursor-predictor-v2.0.pt',
    'elemwiseretro_temperature_predictor': 'https://github.com/VCERS/MatClaw/releases/download/v0.0.3/elemwiseretro-temperature-predictor-v2.0.pt',
    'elemwiseretro_temperature_normalizer': 'https://github.com/VCERS/MatClaw/releases/download/v0.0.3/elemwiseretro-temperature-normalizer-v2.0.pt',
    'convnextv2_sem_classifier': 'https://github.com/VCERS/MatClaw/releases/download/v0.0.1/convnextv2_base-finetuned-sem-classifier.pth'
}


def get_cache_dir() -> Path:
    """
    Get the cache directory for model files.
    
    Uses XDG Base Directory specification:
    - Linux/macOS: ~/.cache/matclaw/models/
    - Windows: %LOCALAPPDATA%\\matclaw\\cache\\models\\
    
    Returns:
        Path object pointing to the cache directory
    """
    if sys.platform == 'win32':
        # Windows: use LOCALAPPDATA
        base = os.environ.get('LOCALAPPDATA', os.path.expanduser('~\\AppData\\Local'))
        cache_dir = Path(base) / 'matclaw' / 'cache' / 'models'
    else:
        # Linux/macOS: use XDG_CACHE_HOME or default ~/.cache
        base = os.environ.get('XDG_CACHE_HOME', os.path.expanduser('~/.cache'))
        cache_dir = Path(base) / 'matclaw' / 'models'
    
    # Create directory if it doesn't exist
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def download_file(url: str, dest_path: Path, show_progress: bool = True) -> None:
    """
    Download a file from URL to destination path with progress indicator.
    
    Args:
        url: URL to download from
        dest_path: Local path to save the file
        show_progress: Whether to show download progress
    """
    try:
        # Download with progress reporting
        def _progress_hook(block_num, block_size, total_size):
            if show_progress and total_size > 0:
                downloaded = block_num * block_size
                percent = min(100, (downloaded / total_size) * 100)
                mb_downloaded = downloaded / (1024 * 1024)
                mb_total = total_size / (1024 * 1024)
                print(f'\rDownloading: {percent:.1f}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)', end='')
        
        # Create temporary file
        temp_path = dest_path.with_suffix(dest_path.suffix + '.tmp')
        
        # Download
        urllib.request.urlretrieve(url, temp_path, _progress_hook if show_progress else None)
        
        if show_progress:
            print()  # New line after progress
        
        # Move to final location
        temp_path.rename(dest_path)
        
    except urllib.error.URLError as e:
        if temp_path.exists():
            temp_path.unlink()
        raise RuntimeError(f"Failed to download {url}: {e}")
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise RuntimeError(f"Error downloading {url}: {e}")


def get_model_path(model_key: str, force_download: bool = False) -> Path:
    """
    Get the path to a model file, downloading it if necessary.
    
    This function follows the pattern used by popular ML libraries like
    HuggingFace Transformers and PyTorch Hub:
    1. Check if model exists in cache
    2. If not (or force_download=True), download from GitHub releases
    3. Return path to cached model
    
    Args:
        model_key: Key identifying the model
        force_download: If True, re-download even if file exists
        
    Returns:
        Path to the cached model file
        
    Raises:
        ValueError: If model_key is not recognized
        RuntimeError: If download fails
    """
    if model_key not in MODEL_URLS:
        raise ValueError(
            f"Unknown model key: {model_key}. "
            f"Valid keys are: {', '.join(MODEL_URLS.keys())}"
        )
    
    # Get cache directory and model path
    cache_dir = get_cache_dir()
    url = MODEL_URLS[model_key]
    filename = url.split('/')[-1]
    model_path = cache_dir / filename
    
    # Download if needed
    if not model_path.exists() or force_download:
        print(f"Downloading {model_key} from GitHub releases...")
        print(f"URL: {url}")
        print(f"Cache location: {model_path}")
        download_file(url, model_path)
        print(f"✓ Downloaded {model_key}")
    
    return model_path


def clear_cache() -> None:
    """
    Clear all cached model files.
    """
    cache_dir = get_cache_dir()
    if cache_dir.exists():
        for ext in ['*.sav', '*.pt', '*.pth']:
            for file in cache_dir.glob(ext):
                file.unlink()
        print(f"Cleared cache directory: {cache_dir}")
    else:
        print(f"Cache directory does not exist: {cache_dir}")


def get_cache_info() -> dict:
    """
    Get information about cached models.
    
    Returns:
        Dictionary with cache directory and list of cached files with sizes
    """
    cache_dir = get_cache_dir()
    cached_files = []
    
    if cache_dir.exists():
        for ext in ['*.sav', '*.pt', '*.pth']:
            for file in cache_dir.glob(ext):
                size_mb = file.stat().st_size / (1024 * 1024)
                cached_files.append({
                    'name': file.name,
                    'path': str(file),
                    'size_mb': round(size_mb, 2)
                })
    
    return {
        'cache_dir': str(cache_dir),
        'cached_files': cached_files,
        'total_size_mb': round(sum(f['size_mb'] for f in cached_files), 2)
    }


if __name__ == '__main__':
    # Simple CLI for testing
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'info':
            info = get_cache_info()
            print(f"\nCache Directory: {info['cache_dir']}")
            print(f"Total Size: {info['total_size_mb']} MB\n")
            print("Cached Models:")
            for file in info['cached_files']:
                print(f"  - {file['name']} ({file['size_mb']} MB)")
        
        elif command == 'clear':
            clear_cache()
        
        elif command == 'download':
            print("Downloading all models...")
            for key in MODEL_URLS.keys():
                get_model_path(key)
            print("\n✓ All models downloaded")
        
        else:
            print(f"Unknown command: {command}")
            print("Usage: python model_downloader.py [info|clear|download]")
    else:
        info = get_cache_info()
        print(f"Cache Directory: {info['cache_dir']}")
        print(f"Cached Models: {len(info['cached_files'])}")
        print("\nUsage: python model_downloader.py [info|clear|download]")
