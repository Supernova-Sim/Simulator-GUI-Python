---
component_id: 3
component_name: Rocket Motor Variant Configurations
---

# Rocket Motor Variant Configurations

## Component Description

Rocket motor variation definitions and custom parameter configuration factories.

---

## Key References:

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/configs/foguetes/hefesto/motor_variacoes.py (lines 35-47)
```
def criar_variacao(
    overrides: dict[str, Any],
    *,
    nome: str | None = None,
) -> MotorSpec:
    """Cria um `MotorSpec` do Hefesto com `overrides` validados contra `PARAMS_LIVRES`."""
    validar_overrides(overrides, PARAMS_LIVRES)
    nome_final = nome or f"{MOTOR_IREC.nome} (var {len(overrides)}p)"
    return dataclasses.replace(
        MOTOR_IREC,
        overrides=dict(overrides),
        nome=nome_final,
    )
```


## Source Files:

- `configs/foguetes/hefesto/motor_variacoes.py`
- `sitecustomize.py`

