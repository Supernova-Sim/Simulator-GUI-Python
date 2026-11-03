#!/usr/bin/env bash
set -e

# setup_ide.sh — Ativa as extensões visuais (C4 e Graph-It-Live Runtime V2) no Positron/VS Code
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXT_DIR="$HOME/.positron/extensions"

mkdir -p "$EXT_DIR"
ln -sfn "$DIR/.vscode/extensions/hefesto-visualizer" "$EXT_DIR/hefesto-visualizer"

VSIX="$DIR/.vscode/extensions/hefesto-visualizer/hefesto-visualizer-1.1.0.vsix"
if command -v positron >/dev/null 2>&1 && [ -f "$VSIX" ]; then
    positron --install-extension "$VSIX" --force >/dev/null 2>&1 || true
elif [ -x "/usr/share/positron/bin/positron" ] && [ -f "$VSIX" ]; then
    /usr/share/positron/bin/positron --install-extension "$VSIX" --force >/dev/null 2>&1 || true
fi

GRAPHIT_SRC="$DIR/.vscode/extensions/magic5644.graph-it-live-1.21.3-universal"
if [ -d "$GRAPHIT_SRC" ]; then
    ln -sfn "$GRAPHIT_SRC" "$EXT_DIR/magic5644.graph-it-live-1.21.3-universal"
    echo "✓ Graph-It-Live (Runtime V2 Patched) linkado em $EXT_DIR/magic5644.graph-it-live-1.21.3-universal"
fi

echo "✓ Hefesto C4 Architecture Visualizer linkado e instalado em $EXT_DIR/hefesto-visualizer"

echo ""
echo "🎉 Tudo pronto! As extensões C4 e Graph-It-Live com tracer dinâmico estão prontas para uso no Positron."
