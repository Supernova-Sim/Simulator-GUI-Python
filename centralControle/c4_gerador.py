# centralControle/c4_gerador.py
"""Gerador automático de diagramas C4 Nível 4 (Código) via AST e motor a2m.

Regra fundamental do modelo C4 aplicada ao Hefesto:
- Níveis 1 (Contexto), 2 (Containers) e 3 (Componentes) são curados em
  `docs/arquitetura/`.
- O Nível 4 (Código) NUNCA é desenhado à mão: este módulo inspeciona a árvore
  sintática abstrata (AST) de qualquer arquivo `.py` sob demanda e enriquece
  com o motor `a2m` (quando disponível) para gerar um documento Markdown + Mermaid com:
    1. Fronteiras e dependências do arquivo (`flowchart LR`)
    2. Análise de Impacto Sistêmico (Quem consome vs. O que consome)
    3. Diagrama de Sequência de Execução (`sequenceDiagram` com loops/ifs)
    4. Diagrama de classes e contratos `@dataclass` (`classDiagram`)
    5. Grafo de chamadas entre funções do módulo (`flowchart TD`)
    6. Catálogo de símbolos com links diretos para as linhas do código-fonte

Uso via CLI:
    python -m centralControle.c4_gerador src/motor/derivador.py
    python -m centralControle.c4_gerador --todos
"""
from __future__ import annotations

import ast
import re
import shutil
import subprocess
import sys
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path

from src.caminhos import RAIZ

DIR_ARQUITETURA = RAIZ / "docs" / "arquitetura"
DIR_GERADOS_C4 = DIR_ARQUITETURA / "_gerados_c4"

PREFIXOS_INTERNOS = ("src", "configs", "scripts", "centralControle")
BIBLIOTECAS_PADRAO = {
    "__future__",
    "argparse",
    "ast",
    "contextlib",
    "copy",
    "csv",
    "dataclasses",
    "datetime",
    "hashlib",
    "io",
    "itertools",
    "json",
    "logging",
    "math",
    "os",
    "pathlib",
    "re",
    "shutil",
    "subprocess",
    "sys",
    "typing",
    "warnings",
}


@dataclass
class CampoInfo:
    nome: str
    tipo: str


@dataclass
class MetodoInfo:
    nome: str
    assinatura: str
    retorno: str
    lineno: int
    end_lineno: int
    doc: str
    is_property: bool = False


@dataclass
class ClasseInfo:
    nome: str
    lineno: int
    end_lineno: int
    doc: str
    is_dataclass: bool
    bases: list[str] = field(default_factory=list)
    campos: list[CampoInfo] = field(default_factory=list)
    metodos: list[MetodoInfo] = field(default_factory=list)


@dataclass
class FuncaoInfo:
    nome: str
    assinatura: str
    retorno: str
    lineno: int
    end_lineno: int
    doc: str
    chamadas: list[str] = field(default_factory=list)


def obter_binario_a2m() -> Path | None:
    """Localiza o binário `a2m` em `centralControle/bin/a2m` ou no PATH do sistema."""
    local_bin = RAIZ / "centralControle" / "bin" / "a2m"
    if local_bin.is_file() and os_is_executable(local_bin):
        return local_bin
    no_path = shutil.which("a2m")
    if no_path:
        p = Path(no_path)
        if p.is_file() and os_is_executable(p):
            return p
    return None


def os_is_executable(path: Path) -> bool:
    import os
    return os.access(path, os.X_OK)


def _limpar_tipo_mermaid(tipo_str: str) -> str:
    """Converte anotações de tipo Python para sintaxe segura no `classDiagram` do Mermaid."""
    s = tipo_str.replace('"', "").replace("'", "")
    s = s.replace(" | None", "?")
    s = s.replace(" | ", " or ")
    s = s.replace("[", "~").replace("]", "~")
    s = re.sub(r"\s+", " ", s).strip()
    return s or "Any"


def _resumo_doc(node: ast.AST) -> str:
    doc = ast.get_docstring(node) or ""
    primeira = doc.strip().splitlines()[0] if doc.strip() else "—"
    return primeira.replace("|", "\\|")


def _formatar_args(args: ast.arguments) -> str:
    partes: list[str] = []
    todos_pos = list(args.posonlyargs) + list(args.args)
    for a in todos_pos:
        if a.arg in ("self", "cls"):
            continue
        if a.annotation:
            partes.append(f"{a.arg}: {ast.unparse(a.annotation)}")
        else:
            partes.append(a.arg)
    if args.vararg:
        partes.append(f"*{args.vararg.arg}")
    for a in args.kwonlyargs:
        if a.annotation:
            partes.append(f"{a.arg}: {ast.unparse(a.annotation)}")
        else:
            partes.append(a.arg)
    if args.kwarg:
        partes.append(f"**{args.kwarg.arg}")
    return ", ".join(partes)


def _extrair_chamadas(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """Extrai nomes de funções/métodos chamados diretamente no corpo de uma função."""
    chamadas: list[str] = []
    for sub in ast.walk(func_node):
        if isinstance(sub, ast.Call):
            nome_call: str | None = None
            if isinstance(sub.func, ast.Name):
                nome_call = sub.func.id
            elif isinstance(sub.func, ast.Attribute) and isinstance(sub.func.value, ast.Name):
                base = sub.func.value.id
                if base not in ("self", "cls", "math", "np", "plt", "json", "csv", "os", "sys", "Path"):
                    nome_call = f"{base}.{sub.func.attr}"
            if nome_call and nome_call not in chamadas:
                chamadas.append(nome_call)
    return chamadas


def _c4_filename(rel_path: str) -> str:
    """Calcula o nome do arquivo .c4.md correspondente a um caminho relativo."""
    if rel_path.endswith("/__init__.py"):
        base = rel_path[:-len("/__init__.py")]
    elif rel_path == "__init__.py":
        base = "init"
    elif rel_path.endswith(".py"):
        base = rel_path[:-3]
    else:
        base = rel_path
    return base.replace("/", "__") + ".c4.md"


def construir_mapa_modulos_c4() -> dict[str, str]:
    """Mapeia prefixos do a2m (ex.: 'relatorios_py', 'motor_derivador_py') para seus arquivos C4."""
    mapa: dict[str, str] = {}
    src_dir = RAIZ / "src"
    for p in src_dir.rglob("*.py"):
        rel = p.relative_to(RAIZ).as_posix()
        c4_name = _c4_filename(rel)
        prefixo = p.relative_to(src_dir).with_suffix("").as_posix().replace("/", "_") + "_py"
        mapa[prefixo] = c4_name
        mapa[f"src_{prefixo}"] = c4_name

    cc_dir = RAIZ / "centralControle"
    if cc_dir.exists():
        for p in cc_dir.glob("*.py"):
            rel = p.relative_to(RAIZ).as_posix()
            c4_name = _c4_filename(rel)
            prefixo = f"centralControle_{p.stem}_py"
            mapa[prefixo] = c4_name

    cfg_dir = RAIZ / "configs"
    if cfg_dir.exists():
        for p in cfg_dir.rglob("*.py"):
            rel = p.relative_to(RAIZ).as_posix()
            c4_name = _c4_filename(rel)
            prefixo = "configs_" + p.relative_to(cfg_dir).with_suffix("").as_posix().replace("/", "_") + "_py"
            mapa[prefixo] = c4_name
            mapa.setdefault(p.stem + "_py", c4_name)

    return mapa


def analisar_arquivo(caminho: Path) -> tuple[
    str,
    dict[str, list[str]],
    list[str],
    list[ClasseInfo],
    list[FuncaoInfo],
]:
    """Analisa a AST de `caminho` e retorna (docstring, imports_internos, imports_externos, classes, funcoes)."""
    codigo = caminho.read_text(encoding="utf-8")
    tree = ast.parse(codigo, filename=str(caminho))
    doc_modulo = ast.get_docstring(tree) or ""

    imports_internos: dict[str, list[str]] = {}
    imports_externos: list[str] = []

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                raiz_mod = alias.name.split(".")[0]
                if raiz_mod in PREFIXOS_INTERNOS:
                    imports_internos.setdefault(alias.name, [])
                elif raiz_mod not in BIBLIOTECAS_PADRAO and raiz_mod not in imports_externos:
                    imports_externos.append(raiz_mod)
        elif isinstance(node, ast.ImportFrom) and node.module:
            raiz_mod = node.module.split(".")[0]
            nomes = [a.name for a in node.names]
            if raiz_mod in PREFIXOS_INTERNOS:
                lista = imports_internos.setdefault(node.module, [])
                for n in nomes:
                    if n not in lista:
                        lista.append(n)
            elif raiz_mod not in BIBLIOTECAS_PADRAO and raiz_mod not in imports_externos:
                imports_externos.append(raiz_mod)

    classes: list[ClasseInfo] = []
    funcoes: list[FuncaoInfo] = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            is_dc = any(
                (isinstance(d, ast.Name) and d.id == "dataclass")
                or (isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == "dataclass")
                for d in node.decorator_list
            )
            bases = [ast.unparse(b) for b in node.bases]
            campos: list[CampoInfo] = []
            metodos: list[MetodoInfo] = []

            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    campos.append(
                        CampoInfo(
                            nome=item.target.id,
                            tipo=ast.unparse(item.annotation),
                        )
                    )
                elif isinstance(item, ast.FunctionDef):
                    is_prop = any(
                        isinstance(d, ast.Name) and d.id == "property"
                        for d in item.decorator_list
                    )
                    ret = ast.unparse(item.returns) if item.returns else "None"
                    metodos.append(
                        MetodoInfo(
                            nome=item.name,
                            assinatura=_formatar_args(item.args),
                            retorno=ret,
                            lineno=item.lineno,
                            end_lineno=item.end_lineno or item.lineno,
                            doc=_resumo_doc(item),
                            is_property=is_prop,
                        )
                    )

            classes.append(
                ClasseInfo(
                    nome=node.name,
                    lineno=node.lineno,
                    end_lineno=node.end_lineno or node.lineno,
                    doc=_resumo_doc(node),
                    is_dataclass=is_dc,
                    bases=bases,
                    campos=campos,
                    metodos=metodos,
                )
            )

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            ret = ast.unparse(node.returns) if node.returns else "None"
            funcoes.append(
                FuncaoInfo(
                    nome=node.name,
                    assinatura=_formatar_args(node.args),
                    retorno=ret,
                    lineno=node.lineno,
                    end_lineno=node.end_lineno or node.lineno,
                    doc=_resumo_doc(node),
                    chamadas=_extrair_chamadas(node),
                )
            )

    return doc_modulo, imports_internos, imports_externos, classes, funcoes


def _sub_c3_relacionado(rel_path: str) -> tuple[str, str]:
    """Retorna (titulo, caminho_relativo_em_docs_arquitetura) do C3 mais próximo."""
    if "motor" in rel_path or "seguranca" in rel_path:
        return ("C3: Subsistema de Motor & Segurança", "../c3-subsistema-motor.md")
    return ("C3: Pipeline de Execução & Voo", "../c3-execucao-voo.md")


def extrair_analise_impacto_a2m(
    caminho: Path,
    funcoes: list[FuncaoInfo],
    a2m_bin: Path,
    c4_atual: str,
) -> tuple[list[str], list[str]]:
    """Gera o diagrama de impacto estruturado (Ascendente/Descendente) e a sequência via a2m."""
    impacto_linhas: list[str] = []
    sequencia_linhas: list[str] = []

    # Escolhe a função candidata para impacto
    funcoes_publicas = [f for f in funcoes if not f.nome.startswith("_")]
    alvo_func: str | None = None
    if funcoes_publicas:
        alvo_func = funcoes_publicas[0].nome
    elif funcoes:
        alvo_func = funcoes[0].nome

    if not alvo_func:
        return impacto_linhas, sequencia_linhas

    # 1. Executa a2m impact
    src_dir = RAIZ / "src"
    try:
        proc_impact = subprocess.run(
            [str(a2m_bin), "impact", str(src_dir), "-t", alvo_func],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (subprocess.SubprocessError, OSError):
        proc_impact = None

    if proc_impact and proc_impact.returncode == 0 and "graph TD" in proc_impact.stdout:
        raw_lines = proc_impact.stdout.splitlines()
        nodes: dict[str, str] = {}
        edges: list[tuple[str, str]] = []
        target_id: str | None = None

        for line in raw_lines:
            l_str = line.strip()
            if not l_str or l_str.startswith(("%%", "graph")):
                continue
            m_edge = re.match(r"(\w+)\s*-->\s*(\w+)", l_str)
            if m_edge:
                edges.append((m_edge.group(1), m_edge.group(2)))
                continue
            m_target = re.match(r"(\w+)\(\([\"']?(.*?)(?: \(impacted\))?[\"']?\)\)", l_str)
            if m_target:
                target_id = m_target.group(1)
                nodes[target_id] = m_target.group(2).replace("fn ", "")
                continue
            m_node = re.match(r"(\w+)\[[\"']?(.*?)[\"']?\]", l_str)
            if m_node:
                nodes[m_node.group(1)] = m_node.group(2)

        if target_id:
            adj_down = defaultdict(list)
            adj_up = defaultdict(list)
            for u, v in edges:
                adj_down[u].append(v)
                adj_up[v].append(u)

            ancestors = set()
            q_up = deque([target_id])
            while q_up:
                curr = q_up.popleft()
                for p in adj_up[curr]:
                    if p not in ancestors:
                        ancestors.add(p)
                        q_up.append(p)

            descendants = set()
            q_down = deque([target_id])
            while q_down:
                curr = q_down.popleft()
                for c in adj_down[curr]:
                    if c not in descendants:
                        descendants.add(c)
                        q_down.append(c)

            impacto_linhas.extend([
                "### Análise de Impacto Sistêmico (`a2m impact`)",
                "",
                "> [!IMPORTANT]",
                f"> **Mapeamento de Efeito Cascata ao Modificar `{alvo_func}()`:**",
                "> - **Risco de Quebra Ascendente (Vermelho):** Funções e módulos externos que chamam esta lógica.",
                "> - **Impacto Descendente (Azul):** Rotinas internas e dependências consumidas.",
                "",
                "```mermaid",
                "%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%",
                "graph TD",
                "    classDef target fill:#ffe6cc,stroke:#d79b00,stroke-width:3px,color:#000",
                "    classDef upward fill:#f8cecc,stroke:#b85450,stroke-width:2px,color:#000",
                "    classDef downward fill:#dae8fc,stroke:#6c8ebf,stroke-width:1px,color:#000",
                "",
                f'    ALVO(("⭐ {alvo_func} (ALVO)")):::target',
                "",
            ])

            if ancestors:
                impacto_linhas.append('    subgraph Ascendente["🚨 Risco de Quebra Ascendente (Quem consome esta função)"]')
                for anc in ancestors:
                    lbl = nodes.get(anc, anc)
                    impacto_linhas.append(f'        {anc}["⚠️ {lbl}"]:::upward')
                impacto_linhas.append("    end")
                for u, v in edges:
                    if u in ancestors and v in ancestors:
                        impacto_linhas.append(f"    {u} --> {v}")
                    elif u in ancestors and v == target_id:
                        impacto_linhas.append(f"    {u} --> ALVO")

            if descendants:
                impacto_linhas.append('    subgraph Descendente["🧩 Impacto Descendente (Dependências consumidas)"]')
                for desc in descendants:
                    lbl = nodes.get(desc, desc)
                    impacto_linhas.append(f'        {desc}["{lbl}"]:::downward')
                impacto_linhas.append("    end")
                for u, v in edges:
                    if u == target_id and v in descendants:
                        impacto_linhas.append(f"    ALVO --> {v}")
                    elif u in descendants and v in descendants:
                        impacto_linhas.append(f"    {u} --> {v}")

            mapa_modulos = construir_mapa_modulos_c4()
            todos_nos = sorted(ancestors | descendants)
            links_tabela: list[tuple[str, str, str]] = []
            for nid in todos_nos:
                m_mod = re.match(r"^code_(.*?)__(?:function|struct|method)__", nid)
                if m_mod:
                    target_c4 = mapa_modulos.get(m_mod.group(1))
                    if target_c4 and target_c4 != c4_atual:
                        lbl = nodes.get(nid, nid)
                        impacto_linhas.append(f'    click {nid} href "{target_c4}" "Abrir C4 ({lbl})"')
                        tipo = "🚨 Risco Ascendente (Caller)" if nid in ancestors else "🧩 Impacto Descendente (Callee)"
                        if (tipo, lbl, target_c4) not in links_tabela:
                            links_tabela.append((tipo, lbl, target_c4))

            impacto_linhas.append("    linkStyle default stroke:#38bdf8,stroke-width:2px;")
            impacto_linhas.extend(["```", ""])

            if links_tabela:
                impacto_linhas.extend([
                    "#### 🧭 Atalhos Rápidos de Navegação (Impacto Sistêmico)",
                    "",
                    "| Relação | Símbolo / Função | Arquivo C4 Destino |",
                    "| :--- | :--- | :--- |",
                ])
                for tipo, lbl, target_c4 in links_tabela:
                    impacto_linhas.append(f"| {tipo} | `{lbl}` | [⚡ `{target_c4}`]({target_c4}) |")
                impacto_linhas.append("")

    # 2. Executa a2m sequence
    try:
        proc_seq = subprocess.run(
            [str(a2m_bin), "sequence", str(src_dir), "-t", alvo_func],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (subprocess.SubprocessError, OSError):
        proc_seq = None

    if proc_seq and proc_seq.returncode == 0 and "sequenceDiagram" in proc_seq.stdout:
        seq_code = proc_seq.stdout.strip()
        # Filtra resumo no final do a2m se houver
        linhas_seq = [
            l for l in seq_code.splitlines()
            if not l.startswith("sequence ") and not l.startswith("%%")
        ]
        sequencia_linhas.extend([
            f"### Diagrama de Sequência de Execução — `{alvo_func}()` (`sequenceDiagram`)",
            "",
            "> [!NOTE]",
            "> Mostra o fluxo sequencial real de controle de execução da função,",
            "> incluindo condicionais (`alt ... else`) e laços (`loop`).",
            "",
            "```mermaid",
            "%%{init: {'theme': 'dark', 'themeVariables': { 'signalColor': '#38bdf8', 'signalTextColor': '#f8fafc', 'actorBkg': '#1e293b', 'actorBorder': '#38bdf8', 'actorTextColor': '#f8fafc' }}}%%",
            "\n".join(linhas_seq),
            "```",
            "",
        ])

    return impacto_linhas, sequencia_linhas


def gerar_markdown_c4(caminho_py: str | Path) -> str:
    """Gera o conteúdo Markdown completo de C4 Nível 4 (Código) para `caminho_py`."""
    caminho = Path(caminho_py).resolve()
    try:
        rel = caminho.relative_to(RAIZ).as_posix()
    except ValueError:
        rel = caminho.name

    doc_mod, imp_int, imp_ext, classes, funcoes = analisar_arquivo(caminho)
    c3_titulo, c3_link = _sub_c3_relacionado(rel)
    rel_fonte = f"../../../{rel}"
    c4_atual = _c4_filename(rel)

    a2m_bin = obter_binario_a2m()
    impacto_md: list[str] = []
    seq_md: list[str] = []
    if a2m_bin and funcoes:
        impacto_md, seq_md = extrair_analise_impacto_a2m(caminho, funcoes, a2m_bin, c4_atual)

    linhas: list[str] = [
        f"# ⚡ C4 Nível 4 (Código) — `{rel}`",
        "",
        "> [!NOTE]",
        "> **Gerado automaticamente a partir da AST do código-fonte e motor a2m.**",
        "> Pela regra do modelo C4, o Nível 4 nunca é desenhado manualmente — ele reflete",
        f"> em tempo real as classes, funções, impacto e chamadas presentes em [`{caminho.name}`]({rel_fonte}).",
        "",
        "**Navegação na Hierarquia C4:**",
        (
            "[🌐 Nível 1: Contexto](../c1-contexto.md) · "
            "[📦 Nível 2: Containers](../c2-containers.md) · "
            f"[🧩 {c3_titulo}]({c3_link}) · "
            f"**⚡ Nível 4: `{caminho.name}`** · "
            "[📖 Guia de Visualização](../../../centralControle/GUIA_VISUALIZACAO.md)"
        ),
        "",
        "---",
        "",
        "## 1. Propósito do Módulo",
        "",
    ]

    if doc_mod:
        linhas.append(doc_mod.strip())
    else:
        linhas.append(f"Módulo `{rel}`.")
    linhas.extend(["", "---", ""])

    # ------------------------------------------------------------------
    # Seção 2: Fronteiras e Dependências (Imports)
    # ------------------------------------------------------------------
    linhas.extend([
        "## 2. Fronteiras e Dependências do Arquivo",
        "",
        "```mermaid",
        "%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%",
        "flowchart LR",
        f'    MOD["📄 {rel}"]',
    ])

    if not imp_int and not imp_ext:
        linhas.append('    NONE["Sem dependências externas (Python puro)"]')
        linhas.append("    NONE --> MOD")
    else:
        for i, (mod_name, simbolos) in enumerate(imp_int.items()):
            resumo_simb = ", ".join(simbolos[:4])
            if len(simbolos) > 4:
                resumo_simb += ", ..."
            label = f"{mod_name}\\n({resumo_simb})" if resumo_simb else mod_name
            linhas.append(f'    INT_{i}["🧩 {label}"] --> MOD')
            c4_target = mod_name.replace(".", "__") + ".c4.md"
            linhas.append(f'    click INT_{i} href "{c4_target}" "Abrir C4 de {mod_name}"')
        for j, ext_name in enumerate(imp_ext):
            linhas.append(f'    EXT_{j}["📚 {ext_name} ( lib externa )"] -.-> MOD')

    linhas.append("    linkStyle default stroke:#38bdf8,stroke-width:2px;")
    linhas.extend(["```", ""])

    if imp_int:
        linhas.extend([
            "#### 🧭 Dependências Internas Navegáveis",
            "",
            "| Dependência | Símbolos Importados | Documento C4 |",
            "| :--- | :--- | :--- |",
        ])
        for mod_name, simbolos in sorted(imp_int.items()):
            c4_target = mod_name.replace(".", "__") + ".c4.md"
            simb_str = ", ".join(f"`{s}`" for s in simbolos[:5])
            if len(simbolos) > 5:
                simb_str += ", ..."
            linhas.append(f"| `🧩 {mod_name}` | {simb_str or '*(módulo completo)*'} | [⚡ `{c4_target}`]({c4_target}) |")
        linhas.append("")

    linhas.extend(["---", ""])

    # ------------------------------------------------------------------
    # Seção 3: Análise de Impacto Sistêmico & Sequência (se disponível)
    # ------------------------------------------------------------------
    if impacto_md or seq_md:
        linhas.append("## 3. Impacto Sistêmico e Fluxo de Execução")
        linhas.append("")
        if impacto_md:
            linhas.extend(impacto_md)
        if seq_md:
            linhas.extend(seq_md)
        linhas.extend(["---", ""])

    # ------------------------------------------------------------------
    # Seção 4: Diagrama de Classes / Contratos (se houver classes)
    # ------------------------------------------------------------------
    sec_num_classes = 4 if (impacto_md or seq_md) else 3
    if classes:
        linhas.extend([
            f"## {sec_num_classes}. Estrutura de Classes e Contratos (`classDiagram`)",
            "",
            "```mermaid",
            "%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%",
            "classDiagram",
        ])
        nomes_classes_locais = {c.nome for c in classes}
        relacoes: list[str] = []

        for c in classes:
            linhas.append(f"    class {c.nome} {{")
            if c.is_dataclass:
                linhas.append("        <<dataclass>>")
            for campo in c.campos:
                t_limpo = _limpar_tipo_mermaid(campo.tipo)
                linhas.append(f"        +{campo.nome} : {t_limpo}")
                for outro_nome in nomes_classes_locais:
                    if outro_nome != c.nome and re.search(rf"\b{outro_nome}\b", campo.tipo):
                        rel_str = f"    {c.nome} *-- {outro_nome} : {campo.nome}"
                        if rel_str not in relacoes:
                            relacoes.append(rel_str)
            for m in c.metodos:
                vis = "-" if m.nome.startswith("_") and m.nome != "__post_init__" else "+"
                ret_limpo = _limpar_tipo_mermaid(m.retorno)
                linhas.append(f"        {vis}{m.nome}() {ret_limpo}")
            linhas.append("    }")

        linhas.extend(relacoes)
        linhas.extend(["```", "", "---", ""])

    # ------------------------------------------------------------------
    # Seção 5: Fluxo de Chamadas Internas (se houver funções)
    # ------------------------------------------------------------------
    sec_num_fluxo = (sec_num_classes + 1) if classes else sec_num_classes
    if funcoes:
        linhas.extend([
            f"## {sec_num_fluxo}. Fluxo Lógico de Funções Locais (`flowchart TD`)",
            "",
            "```mermaid",
            "%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%",
            "flowchart TD",
        ])
        nomes_classes_locais = {c.nome for c in classes}
        simbolos_importados = {
            s: mod for mod, lista in imp_int.items() for s in lista
        }

        for idx, f in enumerate(funcoes):
            fid = f"F_{idx}"
            if f.nome.startswith("_"):
                linhas.append(f'    {fid}["🔒 {f.nome}()"]')
            else:
                linhas.append(f'    {fid}["🟢 {f.nome}()"]')

        mapa_id = {f.nome: f"F_{idx}" for idx, f in enumerate(funcoes)}
        nos_externos_criados: dict[str, str] = {}

        for f in funcoes:
            src_id = mapa_id[f.nome]
            for call_name in f.chamadas:
                if call_name in mapa_id and call_name != f.nome:
                    linhas.append(f"    {src_id} --> {mapa_id[call_name]}")
                elif call_name in nomes_classes_locais:
                    cid = nos_externos_criados.get(call_name)
                    if not cid:
                        cid = f"CLS_{call_name}"
                        nos_externos_criados[call_name] = cid
                        linhas.append(f'    {cid}(["📦 {call_name}"])')
                    linhas.append(f"    {src_id} -. instancia .-> {cid}")
                elif call_name in simbolos_importados:
                    eid = nos_externos_criados.get(call_name)
                    if not eid:
                        eid = f"EXTCALL_{len(nos_externos_criados)}"
                        nos_externos_criados[call_name] = eid
                        mod_orig = simbolos_importados[call_name]
                        linhas.append(f'    {eid}["🔗 {call_name}()\\n({mod_orig})"]')
                        c4_target = mod_orig.replace(".", "__") + ".c4.md"
                        linhas.append(f'    click {eid} href "{c4_target}" "Abrir C4 de {mod_orig}"')
                    linhas.append(f"    {src_id} --> {eid}")

        chamadas_ext_tabela: list[tuple[str, str, str]] = []
        for call_name, eid in nos_externos_criados.items():
            if eid.startswith("EXTCALL_") and call_name in simbolos_importados:
                mod_orig = simbolos_importados[call_name]
                c4_target = mod_orig.replace(".", "__") + ".c4.md"
                chamadas_ext_tabela.append((call_name, mod_orig, c4_target))

        linhas.append("    linkStyle default stroke:#38bdf8,stroke-width:2px;")
        linhas.extend(["```", ""])

        if chamadas_ext_tabela:
            linhas.extend([
                "#### 🧭 Chamadas Externas Identificadas",
                "",
                "| Chamada Local | Módulo de Origem | Documento C4 |",
                "| :--- | :--- | :--- |",
            ])
            for call_name, mod_orig, c4_target in chamadas_ext_tabela:
                linhas.append(f"| `🔗 {call_name}()` | `{mod_orig}` | [⚡ `{c4_target}`]({c4_target}) |")
            linhas.append("")

        linhas.extend(["---", ""])

    # ------------------------------------------------------------------
    # Seção 6: Catálogo Clicável de Símbolos
    # ------------------------------------------------------------------
    sec_num_cat = (sec_num_fluxo + 1) if funcoes else sec_num_fluxo
    linhas.extend([
        f"## {sec_num_cat}. Catálogo de Símbolos (Links Diretos para o Código)",
        "",
    ])

    if classes:
        linhas.extend([
            "### Classes / Contratos",
            "",
            "| Classe | Linhas | Tipo | Resumo |",
            "| :--- | :--- | :--- | :--- |",
        ])
        for c in classes:
            link = f"[`{c.nome}`]({rel_fonte}#L{c.lineno}-L{c.end_lineno})"
            tipo_c = "`@dataclass`" if c.is_dataclass else "Classe"
            linhas.append(f"| {link} | `L{c.lineno}–L{c.end_lineno}` | {tipo_c} | {c.doc} |")
        linhas.append("")

    if funcoes:
        linhas.extend([
            "### Funções do Módulo",
            "",
            "| Função | Linhas | Retorno | Resumo |",
            "| :--- | :--- | :--- | :--- |",
        ])
        for f in funcoes:
            link = f"[`{f.nome}`]({rel_fonte}#L{f.lineno}-L{f.end_lineno})"
            ret_code = f"`{f.retorno}`"
            linhas.append(f"| {link} | `L{f.lineno}–L{f.end_lineno}` | {ret_code} | {f.doc} |")
        linhas.append("")

    return "\n".join(linhas)


def gerar_arquivo_c4(caminho_py: str | Path) -> Path:
    """Gera e salva o arquivo `.md` de Nível 4 em `docs/arquitetura/_gerados_c4/`."""
    caminho = Path(caminho_py).resolve()
    try:
        rel = caminho.relative_to(RAIZ).as_posix()
    except ValueError:
        rel = caminho.name

    nome_saida = _c4_filename(rel)
    DIR_GERADOS_C4.mkdir(parents=True, exist_ok=True)
    destino = DIR_GERADOS_C4 / nome_saida
    conteudo = gerar_markdown_c4(caminho)
    destino.write_text(conteudo, encoding="utf-8")
    return destino


def gerar_todos() -> list[Path]:
    """Gera a documentação C4 Nível 4 para todos os módulos `.py` de `src/`, `centralControle/` e `configs/`."""
    if DIR_GERADOS_C4.exists():
        for antigo in DIR_GERADOS_C4.glob("*.c4.md"):
            antigo.unlink()

    alvos: list[Path] = []
    for p in sorted((RAIZ / "src").rglob("*.py")):
        if p.name == "__init__.py" and p.stat().st_size < 50:
            continue
        alvos.append(p)

    alvos.extend(sorted((RAIZ / "centralControle").glob("*.py")))

    cfg_dir = RAIZ / "configs"
    if cfg_dir.exists():
        for p in sorted(cfg_dir.rglob("*.py")):
            if p.name == "__init__.py" and p.stat().st_size < 50:
                continue
            alvos.append(p)

    gerados: list[Path] = []
    for alvo in alvos:
        gerados.append(gerar_arquivo_c4(alvo))
    return gerados


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python -m centralControle.c4_gerador <caminho_arquivo.py | --todos>", file=sys.stderr)
        sys.exit(1)

    arg = sys.argv[1]
    if arg in ("--todos", "-a", "todos"):
        gerados = gerar_todos()
        print(f"✅ {len(gerados)} diagramas C4 Nível 4 gerados com sucesso em {DIR_GERADOS_C4}:")
        for g in gerados:
            print(f"  - {g.name}")
    else:
        destino = gerar_arquivo_c4(arg)
        print(destino)


if __name__ == "__main__":
    main()
