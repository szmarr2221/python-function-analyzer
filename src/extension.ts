import * as vscode from 'vscode';
import { LanguageClient, LanguageClientOptions, ServerOptions } from 'vscode-languageclient/node';
import { registerLogger, traceError, traceLog, traceVerbose } from './common/log/logging';
import { initializePython, onDidChangePythonInterpreter } from './common/python';
import { checkIfConfigurationChanged } from './common/settings';
import { loadServerDefaults } from './common/setup';
import { getLSClientTraceLevel } from './common/utilities';
import { createOutputChannel, onDidChangeConfiguration, registerCommand } from './common/vscodeapi';
import * as path from 'path';

let lsClient: LanguageClient | undefined;
const EXECUTE_COMMAND = 'workspace/executeCommand';

export async function activate(context: vscode.ExtensionContext): Promise<void> {
    const serverInfo = loadServerDefaults();
    const serverName = 'Function Analyzer';
    const serverId = 'functionAnalyzer';

    const outputChannel = createOutputChannel(serverName);
    context.subscriptions.push(outputChannel, registerLogger(outputChannel));

    const changeLogLevel = async (c: vscode.LogLevel, g: vscode.LogLevel) => {
        const level = getLSClientTraceLevel(c, g);
        await lsClient?.setTrace(level);
    };

    context.subscriptions.push(
        outputChannel.onDidChangeLogLevel(async (e) => {
            await changeLogLevel(e, vscode.env.logLevel);
        }),
        vscode.env.onDidChangeLogLevel(async (e) => {
            await changeLogLevel(outputChannel.logLevel, e);
        }),
    );

    traceLog(`Name: ${serverInfo.name}`);
    traceLog(`Module: ${serverInfo.module}`);
    traceVerbose(`Full Server Info: ${JSON.stringify(serverInfo)}`);

    const runServer = async () => {
        // ✅ HARDCODED PYTHON INTERPRETER
        const pythonPath = context.asAbsolutePath('.venv/Scripts/python.exe');
        vscode.window.showInformationMessage('Trying to start LSP server with: ' + pythonPath);

        const serverModule = 'C:\\Users\\samar\\python-function-analyzer\\python\\tools\\lsp_server.py';

        const serverOptions: ServerOptions = {
            command: pythonPath,
            args: [serverModule],
            options: { cwd: 'C:\\Users\\samar\\python-function-analyzer' },
        };

        const clientOptions: LanguageClientOptions = {
            documentSelector: [{ scheme: 'file', language: 'python' }],
        };

        lsClient = new LanguageClient(serverId, serverName, serverOptions, clientOptions);
        await lsClient.start();
    };

    context.subscriptions.push(
        onDidChangePythonInterpreter(runServer),
        onDidChangeConfiguration((e: vscode.ConfigurationChangeEvent) => {
            if (checkIfConfigurationChanged(e, serverId)) {
                runServer();
            }
        }),
        registerCommand(`${serverId}.restart`, runServer),

        registerCommand('functionAnalyzer.countFunctions', async () => {
            const workspaceFolders = vscode.workspace.workspaceFolders;
            if (!workspaceFolders || workspaceFolders.length === 0) {
                vscode.window.showErrorMessage('Please open a folder to analyze.');
                return;
            }

            const folderPath = workspaceFolders[0].uri.fsPath;

            if (!lsClient) {
                vscode.window.showErrorMessage('Language Server is not running.');
                return;
            }

            await vscode.window.withProgress(
                {
                    location: vscode.ProgressLocation.Notification,
                    title: 'Counting Python functions via LSP...',
                    cancellable: false,
                },
                async () => {
                    try {
                        const result = (await lsClient!.sendRequest(EXECUTE_COMMAND, {
                            command: 'functionAnalyzer.countFunctions',
                            arguments: [folderPath],
                        })) as Record<string, number> | undefined;

                        if (!result) {
                            vscode.window.showErrorMessage('Failed to retrieve function count results.');
                            return;
                        }

                        const panel = vscode.window.createWebviewPanel(
                            'functionAnalyzerResults',
                            'Function Count Results',
                            vscode.ViewColumn.One,
                            {},
                        );

                        panel.webview.html = getWebviewContent(result);
                    } catch (e: any) {
                        vscode.window.showErrorMessage(`LSP command failed: ${e.message}`);
                    }
                },
            );
        }),
    );

    setImmediate(async () => {
        await initializePython(context.subscriptions);
        await runServer();
    });
}

export async function deactivate(): Promise<void> {
    if (lsClient) {
        await lsClient.stop();
    }
}

function getWebviewContent(data: Record<string, number>): string {
    const folders: { [folder: string]: { [filename: string]: number } } = {};

    for (const filePath in data) {
        const parts = filePath.split(/[\\/]/);
        const fileName = parts.pop()!;
        const folder = parts.join('/') || 'root';

        if (!folders[folder]) {
            folders[folder] = {};
        }

        folders[folder][fileName] = data[filePath];
    }

    let html = '<h2>Function Count Results</h2><ul>';

    for (const folder in folders) {
        html += `<li><strong>${folder}/</strong><ul>`;
        for (const file in folders[folder]) {
            const count = folders[folder][file];
            html += `<li>${file}: ${count} function${count !== 1 ? 's' : ''}</li>`;
        }
        html += '</ul></li>';
    }

    html += '</ul>';

    return `
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Function Count</title>
        <style>
            body { font-family: sans-serif; padding: 1em; }
            ul { list-style: none; padding-left: 1em; }
            li::before { content: "\\2514\\2500 "; color: #888; }
        </style>
    </head>
    <body>
        ${html}
    </body>
    </html>
    `;
}
