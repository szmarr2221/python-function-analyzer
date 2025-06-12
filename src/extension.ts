import * as vscode from 'vscode';
import { LanguageClient, LanguageClientOptions, ServerOptions } from 'vscode-languageclient/node';
import { registerLogger, traceError, traceLog, traceVerbose } from './common/log/logging';
import {
    checkVersion,
    getInterpreterDetails,
    initializePython,
    onDidChangePythonInterpreter,
    resolveInterpreter,
} from './common/python';
import { checkIfConfigurationChanged, getInterpreterFromSetting } from './common/settings';
import { loadServerDefaults } from './common/setup';
import { getLSClientTraceLevel } from './common/utilities';
import { createOutputChannel, onDidChangeConfiguration, registerCommand } from './common/vscodeapi';
import * as path from 'path';

let lsClient: LanguageClient | undefined;
let commandRegistered = false;

export async function activate(context: vscode.ExtensionContext): Promise<void> {
    const serverInfo = loadServerDefaults();
    const serverName = serverInfo.name;
    const serverId = serverInfo.module;

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
        const interpreter = getInterpreterFromSetting(serverId);
        let pythonPath: string | undefined;

        if (interpreter && interpreter.length > 0) {
            pythonPath = interpreter[0];
            if (checkVersion(await resolveInterpreter(interpreter))) {
                traceVerbose(`Using interpreter from ${serverInfo.module}.interpreter: ${interpreter.join(' ')}`);
            }
        } else {
            const interpreterDetails = await getInterpreterDetails();
            if (interpreterDetails.path) {
                pythonPath = interpreterDetails.path[0];
                traceVerbose(`Using interpreter from Python extension: ${interpreterDetails.path.join(' ')}`);
            }
        }

        if (!pythonPath) {
            traceError(
                'Python interpreter missing:\r\n' +
                    '[Option 1] Select python interpreter using the ms-python.python.\r\n' +
                    `[Option 2] Set an interpreter using "${serverId}.interpreter" setting.\r\n` +
                    'Please use Python 3.8 or greater.',
            );
            return;
        }

        const pythonExecutable = path.join(context.extensionPath, '.venv', 'Scripts', 'python.exe');
        const serverModule = context.asAbsolutePath(path.join('bundled', 'tool', 'lsp_server.py'));

        const serverOptions: ServerOptions = {
            command: pythonExecutable,
            args: [serverModule],
            options: { cwd: context.extensionPath },
        };

        const clientOptions: LanguageClientOptions = {
            documentSelector: [{ scheme: 'file', language: 'python' }],
        };

        lsClient = new LanguageClient('functionAnalyzer', 'Function Analyzer LSP', serverOptions, clientOptions);
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

        registerCommand('functionAnalyzer.triggerScan', async () => {
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
                    title: 'Scanning Python functions via LSP...',
                    cancellable: false,
                },
                async () => {
                    try {
                        const result = (await lsClient!.sendRequest('workspace/executeCommand', {
                            command: 'functionAnalyzer.scanFunctions',
                            arguments: [folderPath],
                        })) as Record<string, number> | undefined;

                        if (!result) {
                            vscode.window.showErrorMessage('Failed to retrieve function count results.');
                            return;
                        }

                        const panel = vscode.window.createWebviewPanel(
                            'functionAnalyzerResults',
                            'Function Analysis Results',
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

    if (!commandRegistered) {
        context.subscriptions.push(
            vscode.commands.registerCommand('functionAnalyzer.scanFunctions', async () => {
                const folder = await getSelectedFolder();
                if (!folder) {
                    vscode.window.showWarningMessage('No folder selected.');
                    return;
                }

                if (!lsClient) {
                    vscode.window.showErrorMessage('Language Server is not running.');
                    return;
                }

                const result = await lsClient!.sendRequest('workspace/executeCommand', {
                    command: 'functionAnalyzer.scanFunctions',
                    arguments: [folder],
                });

                if (result && typeof result === 'object') {
                    const summary = Object.entries(result)
                        .map(([file, count]) => `${file}: ${count}`)
                        .join('\n');
                    vscode.window.showInformationMessage(`Scan result:\n${summary}`);
                }
            }),
        );
        commandRegistered = true;
    }

    setImmediate(async () => {
        const interpreter = getInterpreterFromSetting(serverId);
        if (!interpreter || interpreter.length === 0) {
            traceLog(`Python extension loading`);
            await initializePython(context.subscriptions);
            traceLog(`Python extension loaded`);
        } else {
            await runServer();
        }
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

    let html = '<h2>Function Count Analysis</h2><ul>';

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
            li::before { content: "└─ "; color: #888; }
        </style>
    </head>
    <body>
        ${html}
    </body>
    </html>
    `;
}

async function getSelectedFolder(): Promise<string | undefined> {
    const folders = vscode.workspace.workspaceFolders;
    return folders && folders.length > 0 ? folders[0].uri.fsPath : undefined;
}
