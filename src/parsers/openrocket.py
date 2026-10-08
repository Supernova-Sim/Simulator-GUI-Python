import xml.etree.ElementTree as ET
from pathlib import Path
from configs.componentes import TuboSpec, MassaPontualSpec
from configs.especificacao import CoifaSpec, AletaSpec, ALETA_IREC
from configs.material import ALUMINIO_6061, COMPOSITO_EFETIVO

# Dicionário auxiliar para mapear densidades do XML para as nossas constantes
# (Isso pode ser extraído dinamicamente do XML também, mas é bom ter um fallback)
DENSIDADES = {
    "Aluminum": ALUMINIO_6061,
    "Fiberglass": COMPOSITO_EFETIVO,
}


def _extrair_densidade(elemento_material) -> float:
    """Extrai a densidade do nó <material> do OpenRocket."""
    dens_str = elemento_material.get("density")
    if dens_str:
        return float(dens_str)
    # Fallback: tenta achar pelo nome
    nome_mat = elemento_material.text
    return DENSIDADES.get(nome_mat, 1000.0)  # Retorna 1000 se não achar


def _extrair_geometria_aleta(finpoints) -> dict:
    """Calcula os parâmetros trapezoidais a partir dos pontos do polígono."""
    # Lógica para ler os 4 pontos e calcular root_chord, tip_chord, sweep, span
    # ...
    pass


def _parse_nosecone(elemento, pos_absoluta_top) -> CoifaSpec:
    """Traduz <nosecone> para CoifaSpec."""
    # ...
    pass


def _parse_bodytube(elemento, pos_absoluta_top, componentes_acumulados):
    """Traduz <bodytube> e seus subcomponentes recursivamente."""
    # ...
    pass


def carregar_openrocket(caminho_ork: str | Path) -> tuple[list, CoifaSpec, AletaSpec]:
    """
    Lê o arquivo .ork e retorna as specs prontas para serem usadas
    no resolver().
    """
    tree = ET.parse(caminho_ork)
    root = tree.getroot()

    # Achar o nó da coifa, aletas e iterar sobre os bodytubes
    # ...

    return lista_componentes, coifa_spec, aleta_spec