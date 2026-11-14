const vscode = require('vscode');
const path = require('path');
const fs = require('fs');
const cp = require('child_process');

function resolverPython(root) {
    const venvPy = path.join(root, '.venv', 'bin', 'python');
    if (fs.existsSync(venvPy)) {
        return venvPy;
    }
    return 'python3';
}

function activate(context) {
    let disposable = vscode.commands.registerCommand('hefesto.openVisualizer', async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showInformationMessage('Abra um arquivo Python (.py) primeiro.');
            return;
        }

        const currentFile = editor.document.fileName;
        const fileName = path.basename(currentFile);

        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders || workspaceFolders.length === 0) {
            vscode.window.showInformationMessage('Abra a pasta do projeto Hefesto.');
            return;
        }
        const root = workspaceFolders[0].uri.fsPath;
        const docsDir = path.join(root, 'docs', 'arquitetura');

        const isMotorRelated = currentFile.includes('motor') || currentFile.includes('seguranca');

        const c3MotorItem = {
            label: '🧩 C4 Nível 3 (Componentes) — Subsistema de Motor & Segurança',
            description: 'Curado (docs/arquitetura/c3-subsistema-motor.md)',
            action: 'md',
            path: path.join(docsDir, 'c3-subsistema-motor.md')
        };
        const c3VooItem = {
            label: '🧩 C4 Nível 3 (Componentes) — Pipeline de Execução e Voo',
            description: 'Curado (docs/arquitetura/c3-execucao-voo.md)',
            action: 'md',
            path: path.join(docsDir, 'c3-execucao-voo.md')
        };

        const choices = [
            {
                label: `⚡ C4 Nível 4 (Código) — ${fileName}`,
                description: 'Automático via AST (Classes, Funções e Grafo de Chamadas)',
                action: 'ast_c4',
                targetPy: currentFile
            },
            isMotorRelated ? c3MotorItem : c3VooItem,
            isMotorRelated ? c3VooItem : c3MotorItem,
            {
                label: '📦 C4 Nível 2 (Containers) — Camadas e Pastas do Repositório',
                description: 'Curado (docs/arquitetura/c2-containers.md)',
                action: 'md',
                path: path.join(docsDir, 'c2-containers.md')
            },
            {
                label: '🌐 C4 Nível 1 (Contexto) — Visão Geral do Sistema Hefesto',
                description: 'Curado (docs/arquitetura/c1-contexto.md)',
                action: 'md',
                path: path.join(docsDir, 'c1-contexto.md')
            }
        ];

        const selected = await vscode.window.showQuickPick(choices, {
            placeHolder: `Modelo C4 (${fileName}) — Escolha o nível de visualização para abrir ao lado:`
        });

        if (!selected) return;

        let mdPath = selected.path;
        if (selected.action === 'ast_c4') {
            try {
                // Se o arquivo tiver alterações não salvas, salva antes de analisar a AST
                if (editor.document.isDirty) {
                    await editor.document.save();
                }
                const pyBin = resolverPython(root);
                const stdout = cp.execFileSync(
                    pyBin,
                    ['-m', 'centralControle.c4_gerador', selected.targetPy],
                    { cwd: root, encoding: 'utf-8' }
                );
                mdPath = stdout.trim();
            } catch (err) {
                vscode.window.showErrorMessage(`Erro ao gerar C4 Nível 4 via AST: ${err.message}`);
                return;
            }
        }

        if (!mdPath || !fs.existsSync(mdPath)) {
            vscode.window.showErrorMessage(`Arquivo de arquitetura não encontrado: ${mdPath}`);
            return;
        }

        const uri = vscode.Uri.file(mdPath);
        await vscode.commands.executeCommand('markdown.showPreviewToSide', uri);
    });

    context.subscriptions.push(disposable);
}

function deactivate() {}

module.exports = {
    activate,
    deactivate
};
