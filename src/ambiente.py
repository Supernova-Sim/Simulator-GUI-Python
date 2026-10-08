"""Fábricas de Environment. Nenhum objeto global é criado aqui."""
from rocketpy import Environment
from src.paths import ATMOSFERA

_DIC_NC = {                       # dicionário comum aos arquivos ERA5
    "time": "valid_time",
    "latitude": "latitude",
    "longitude": "longitude",
    "level": "pressure_level",
    "temperature": "t",
    "surface_geopotential_height": None,
    "geopotential_height": None,
    "geopotential": "z",
    "u_wind": "u",
    "v_wind": "v",
}


def build_irec() -> Environment:
    env = Environment(
        date=(2026, 6, 15, 12),
        latitude=32.94019, longitude=-106.92056, elevation=1401,
    )
    env.set_atmospheric_model(
        type="Reanalysis",
        file=str(ATMOSFERA / "irec" / "data_stream-oper_stepType-instant.nc"),
        dictionary=_DIC_NC,
    )
    return env

def build_irec_ensemble() -> Environment:
    env = Environment(
        date=(2026, 6, 15, 12),
        latitude=32.94019, longitude=-106.92056, elevation=1401,
    )
    env.set_atmospheric_model(
        type="Ensemble",
        file=str(ATMOSFERA / "irec" / "data_stream-enda_stepType-instantCerto.nc"),
        dictionary={"ensemble": "number", **_DIC_NC},
    )
    return env

# def build_lasc() -> Environment:
#     ...


def main() -> None:
    """Smoke test: monta o Environment do IREC."""
    env = build_irec()
    print(f"data:     {env.date}")
    print(f"lat/lon:  {env.latitude}, {env.longitude}")
    print(f"elev:     {env.elevation} m")

    assert env.elevation == 1401
    assert env.latitude == 32.94019
    print("\n✓ ambiente OK")


if __name__ == "__main__":
    main()