# src/smoke.py
"""Executa a suíte automatizada de testes e validação de contratos (pytest)."""
from __future__ import annotations

import pytest

from src.paths import RAIZ


def main() -> None:
    tests_dir = RAIZ / "tests"
    code = pytest.main(["-v", str(tests_dir)])
    if code != 0:
        raise SystemExit(int(code))


if __name__ == "__main__":
    main()
