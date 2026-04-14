"""
Utility helpers for ARROWS tools.

Handles two issues with the ARROWS package as installed via pip:

1.  MP_Energetics.json is tracked with git LFS in the ARROWS repo, so
    ``pip install git+https://github.com/njszym/ARROWS.git`` downloads only
    the LFS pointer — not the actual data.  ``ensure_energetics_data()``
    downloads the real file on first use and caches it alongside the
    installed package.

2.  ARROWS loads MP_Energetics.json via the hardcoded **relative** path
    ``'arrows/energetics/MP_Energetics.json'`` resolved from the process
    CWD.  ``arrows_cwd()`` is a context manager that temporarily changes
    the CWD to the site-packages directory so the relative path resolves
    correctly, then restores the original CWD on exit.
"""

import os
import threading
from contextlib import contextmanager

# GitHub LFS media URL — serves the actual binary, not the pointer stub
_MP_ENERGETICS_URL = (
    "https://media.githubusercontent.com/media/njszym/ARROWS/main"
    "/arrows/energetics/MP_Energetics.json"
)

# Thread lock so parallel pytest workers don't race on the first download
_download_lock = threading.Lock()


def get_arrows_site_packages_dir() -> str:
    """
    Return the site-packages directory that contains the ``arrows`` package.

    Raises ImportError if ARROWS is not installed.
    """
    import arrows  # noqa: F401 – triggers ImportError if missing
    arrows_pkg_dir = os.path.dirname(arrows.__file__)   # …/site-packages/arrows
    return os.path.dirname(arrows_pkg_dir)              # …/site-packages


def ensure_energetics_data() -> str:
    """
    Ensure ``MP_Energetics.json`` exists in the installed ARROWS package.

    Downloads from GitHub LFS on first call and caches the file in
    ``<site-packages>/arrows/energetics/MP_Energetics.json``.

    Returns the site-packages directory path (needed for the CWD fix).

    Raises:
        ImportError  – ARROWS not installed.
        RuntimeError – download failed and no cached file exists.
    """
    site_packages = get_arrows_site_packages_dir()
    data_path = os.path.join(
        site_packages, "arrows", "energetics", "MP_Energetics.json"
    )

    if os.path.isfile(data_path) and os.path.getsize(data_path) > 1024:
        # Already downloaded (more than a pointer stub)
        return site_packages

    with _download_lock:
        # Re-check inside the lock (another thread may have downloaded it)
        if os.path.isfile(data_path) and os.path.getsize(data_path) > 1024:
            return site_packages

        import urllib.request
        try:
            urllib.request.urlretrieve(_MP_ENERGETICS_URL, data_path)
        except Exception as exc:
            # Clean up partial downloads
            if os.path.isfile(data_path):
                os.remove(data_path)
            raise RuntimeError(
                f"Failed to download MP_Energetics.json from GitHub LFS:\n{exc}\n"
                "You can manually download it from:\n"
                f"  {_MP_ENERGETICS_URL}\n"
                f"and save it to:\n  {data_path}"
            ) from exc

        if not os.path.isfile(data_path) or os.path.getsize(data_path) <= 1024:
            raise RuntimeError(
                "MP_Energetics.json was downloaded but appears to be a git LFS "
                "pointer stub rather than the real data file.  Please download "
                "it manually:\n"
                f"  curl -L {_MP_ENERGETICS_URL} -o \"{data_path}\""
            )

    return site_packages


@contextmanager
def arrows_cwd():
    """
    Context manager that temporarily sets the CWD to the site-packages
    directory so ARROWS' relative ``'arrows/energetics/MP_Energetics.json'``
    path resolves correctly, then restores the original CWD on exit.

    Also ensures MP_Energetics.json is present (downloads if needed).

    Usage::

        with arrows_cwd():
            pd_dict = energetics.get_pd_dict(precursors, temps)
    """
    site_packages = ensure_energetics_data()
    original_cwd = os.getcwd()
    try:
        os.chdir(site_packages)
        yield site_packages
    finally:
        os.chdir(original_cwd)
