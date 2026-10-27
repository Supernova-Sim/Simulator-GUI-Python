# src/viz.py
"""Configura matplotlib para plots interativos. Importe antes de plotar."""
import matplotlib


def _set_backend():
    if matplotlib.get_backend().lower() not in ("agg", "module://matplotlib_inline.backend_inline"):
        return
    for _b in ("QtAgg", "TkAgg"):
        try:
            matplotlib.use(_b)
            # Se pyplot já estava carregado, .use() pode ser no-op.
            # Força via switch_backend().
            if matplotlib.get_backend().lower() != _b.lower():
                import matplotlib.pyplot as plt
                plt.switch_backend(_b)
            break
        except (ImportError, RuntimeError, ValueError) as e:
            print(f"[viz] falhou {_b}: {e}")
            continue


_set_backend()
print(f"[viz] backend: {matplotlib.get_backend()}")