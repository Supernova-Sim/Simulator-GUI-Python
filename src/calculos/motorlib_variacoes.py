# src/calculos/motorlib_variacoes.py
"""Variações programáticas do motor em memória (dot-path + wildcard).

Aplica overrides dot-path sobre o dicionário `props` do `.ric`, com suporte a
wildcard `*` (todos os grãos) e índice numérico específico.

Ordem de aplicação (quando ambos presentes):
  1. Wildcards primeiro ("grains.*.properties.coreDiameter")
  2. Índices específicos depois ("grains.4.properties.coreDiameter")
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from src.calculos.motorlib_wrapper import (
    MotorResultado,
    carregar_props,
    simular_props,
)


def _normalizar_path(path: str) -> str:
    """Substitui índices numéricos por '*' para comparação com a whitelist."""
    partes = path.split(".")
    return ".".join("*" if p.isdigit() else p for p in partes)


def validar_overrides(
    overrides: dict[str, Any],
    whitelist: set[str] | None = None,
) -> None:
    """Verifica se todos os paths de `overrides` pertencem à `whitelist`."""
    if whitelist is None:
        return

    invalidos = [
        path for path in overrides if _normalizar_path(path) not in whitelist
    ]
    if invalidos:
        linhas = ["Parâmetros fora da whitelist:"]
        for p in invalidos:
            linhas.append(f"  ✗ {p}")
        linhas.append("")
        linhas.append("Whitelist atual:")
        for w in sorted(whitelist):
            linhas.append(f"  ✓ {w}")
        raise ValueError("\n".join(linhas))


def _set_path(obj: Any, partes: list[str], valor: Any) -> None:
    """Aplica `valor` em `obj` seguindo `partes` (dot-path separado)."""
    if not partes:
        return

    chave = partes[0]
    resto = partes[1:]

    if not resto:
        if chave == "*":
            if not isinstance(obj, list):
                raise TypeError(f"'*' aplicado em objeto que não é lista: {type(obj)}")
            for i in range(len(obj)):
                obj[i] = valor
            return
        if chave.isdigit():
            idx = int(chave)
            if not isinstance(obj, list):
                raise TypeError(f"Índice {chave} aplicado em não-lista: {type(obj)}")
            obj[idx] = valor
            return
        if isinstance(obj, dict) and chave not in obj:
            raise KeyError(
                f"Chave final '{chave}' não existe no dict. "
                f"Disponíveis: {list(obj.keys())}"
            )
        obj[chave] = valor
        return

    if chave == "*":
        if not isinstance(obj, list):
            raise TypeError(f"'*' aplicado em objeto que não é lista: {type(obj)}")
        for item in obj:
            _set_path(item, resto, valor)
        return

    if chave.isdigit():
        idx = int(chave)
        if not isinstance(obj, list):
            raise TypeError(f"Índice {chave} aplicado em não-lista: {type(obj)}")
        _set_path(obj[idx], resto, valor)
        return

    if chave not in obj:
        raise KeyError(
            f"Chave '{chave}' não existe no dict. "
            f"Disponíveis: {list(obj.keys())}"
        )
    _set_path(obj[chave], resto, valor)


def _tem_indice_especifico(path: str) -> bool:
    return any(p.isdigit() for p in path.split("."))


def aplicar_overrides(
    props: dict,
    overrides: dict[str, Any],
) -> dict:
    """Retorna uma cópia profunda de `props` com `overrides` aplicados."""
    copia = copy.deepcopy(props)
    chaves_ordenadas = sorted(
        overrides.keys(),
        key=lambda k: (1 if _tem_indice_especifico(k) else 0),
    )
    for chave in chaves_ordenadas:
        _set_path(copia, chave.split("."), overrides[chave])
    return copia


def simular_variacao(
    ric_path: str | Path,
    overrides: dict[str, Any],
    *,
    whitelist: set[str] | None = None,
    nome: str | None = None,
) -> MotorResultado:
    """Carrega o `.ric`, valida e aplica `overrides` em memória e simula."""
    validar_overrides(overrides, whitelist)
    props = carregar_props(ric_path)
    props_mut = aplicar_overrides(props, overrides)
    return simular_props(props_mut, nome=nome)
