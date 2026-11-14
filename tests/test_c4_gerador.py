# tests/test_c4_gerador.py
"""Testes unitários e de integridade do gerador C4 Nível 4 (centralControle/c4_gerador.py)."""
from __future__ import annotations

from unittest.mock import patch

from centralControle.c4_gerador import (
    DIR_GERADOS_C4,
    gerar_arquivo_c4,
    gerar_markdown_c4,
    gerar_todos,
    obter_binario_a2m,
)
from src.caminhos import RAIZ


def test_obter_binario_a2m() -> None:
    bin_path = obter_binario_a2m()
    assert bin_path is not None, "O binário a2m deve ser localizado em centralControle/bin/a2m ou no PATH"
    assert bin_path.is_file(), "O binário deve ser um arquivo existente"


def test_gerar_markdown_c4_especificacoes() -> None:
    caminho = RAIZ / "src" / "especificacoes.py"
    md = gerar_markdown_c4(caminho)
    assert "# ⚡ C4 Nível 4 (Código) — `src/especificacoes.py`" in md
    assert "classDiagram" in md
    assert "GrainSpec" in md
    assert "MotorSpec" in md
    assert "[🌐 Nível 1: Contexto](../c1-contexto.md)" in md
    assert "[📖 Guia de Visualização](../../../centralControle/GUIA_VISUALIZACAO.md)" in md


def test_gerar_markdown_c4_motor_com_impacto() -> None:
    caminho = RAIZ / "src" / "motor" / "derivador.py"
    md = gerar_markdown_c4(caminho)
    assert "# ⚡ C4 Nível 4 (Código) — `src/motor/derivador.py`" in md
    assert "flowchart LR" in md
    assert "classDiagram" in md
    assert "MotorDerivado" in md
    assert "derivar_motor" in md
    assert "Análise de Impacto Sistêmico" in md
    assert "Risco de Quebra Ascendente" in md
    assert "Atalhos Rápidos de Navegação" in md
    assert "Dependências Internas Navegáveis" in md
    assert "Diagrama de Sequência de Execução" in md
    assert "sequenceDiagram" in md


def test_fallback_quando_a2m_ausente() -> None:
    caminho = RAIZ / "src" / "motor" / "derivador.py"
    with patch("centralControle.c4_gerador.obter_binario_a2m", return_value=None):
        md = gerar_markdown_c4(caminho)
        # Não deve lançar exceção e deve conter a documentação básica AST
        assert "# ⚡ C4 Nível 4 (Código) — `src/motor/derivador.py`" in md
        assert "classDiagram" in md
        assert "derivar_motor" in md


def test_gerar_arquivo_c4_salva_no_disco() -> None:
    caminho = RAIZ / "src" / "simulacao" / "ambiente.py"
    saida = gerar_arquivo_c4(caminho)
    assert saida.is_file()
    assert saida.parent == DIR_GERADOS_C4
    assert saida.name == "src__simulacao__ambiente.c4.md"
    conteudo = saida.read_text(encoding="utf-8")
    assert "src/simulacao/ambiente.py" in conteudo


def test_gerar_todos_em_lote() -> None:
    gerados = gerar_todos()
    assert len(gerados) >= 15, f"Esperado ao menos 15 módulos gerados, obtido {len(gerados)}"
    for g in gerados:
        assert g.is_file()
        assert g.suffix == ".md"
