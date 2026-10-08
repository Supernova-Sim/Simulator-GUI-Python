# sitecustomize.py
"""Ajustes globais do Python carregados automaticamente."""
import os
os.environ.setdefault("MPLBACKEND", "Agg")

try:
    import matplotlib
    matplotlib.use("Agg")
    _orig_use = matplotlib.use
    def _safe_use(backend=None, *args, **kwargs):
        if backend and "qt" in str(backend).lower():
            return
        return _orig_use(backend, *args, **kwargs)
    matplotlib.use = _safe_use
except ImportError:
    pass