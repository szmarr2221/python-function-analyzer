// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import * as vscode from 'vscode';
import { LanguageClient } from 'vscode-languageclient/node';
import { registerLogger, traceError, traceLog, traceVerbose } from './common/log/logging';
import {
    checkVersion,
    getInterpreterDetails,
    initializePython,
    onDidChangePythonInterpreter,
    resolveInterpreter,
} from './common/python';
import { restartServer } from './common/server';
import { checkIfConfigurationChanged, getInterpreterFromSetting } from './common/settings';
import { loadServerDefaults } from './common/setup';
import { getLSClientTraceLevel } from './common/utilities';
import { createOutputChannel, onDidChangeConfiguration, registerCommand } from './common/vscodeapi';

// New command which is used to run external Python script
import * as cp from 'child_process';
// Used to join paths (like script path)
import * as path from 'path';

let lsClient: LanguageClient | undefined;

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
        if (interpreter && interpreter.length > 0) {
            if (checkVersion(await resolveInterpreter(interpreter))) {
                traceVerbose(`Using interpreter from ${serverInfo.module}.interpreter: ${interpreter.join(' ')}`);
                lsClient = await restartServer(serverId, serverName, outputChannel, lsClient);
            }
            return;
        }

        const interpreterDetails = await getInterpreterDetails();
        if (interpreterDetails.path) {
            traceVerbose(`Using interpreter from Python extension: ${interpreterDetails.path.join(' ')}`);
            lsClient = await restartServer(serverId, serverName, outputChannel, lsClient);
            return;
        }

        traceError(
            'Python interpreter missing:\r\n' +
                '[Option 1] Select python interpreter using the ms-python.python.\r\n' +
                `[Option 2] Set an interpreter using "${serverId}.interpreter" setting.\r\n` +
                'Please use Python 3.8 or greater.',
        );
    };

    context.subscriptions.push(
        onDidChangePythonInterpreter(async () => {
            await runServer();
        }),
        onDidChangeConfiguration(async (e: vscode.ConfigurationChangeEvent) => {
            if (checkIfConfigurationChanged(e, serverId)) {
                await runServer();
            }
        }),
        registerCommand(`${serverId}.restart`, async () => {
            await runServer();
        }),

        //  Command added to scan Python functions
        registerCommand('functionAnalyzer.scanFunctions', async () => {
            const workspaceFolders = vscode.workspace.workspaceFolders;
            if (!workspaceFolders || workspaceFolders.length === 0) {
                vscode.window.showErrorMessage('Please open a folder to analyze.');
                return;
            }

            const folderPath = workspaceFolders[0].uri.fsPath;
            const scriptPath = path.join(context.extensionPath, 'python', 'scan_functions.py'); // Python script location

            await vscode.window.withProgress(
                {
                    location: vscode.ProgressLocation.Notification,
                    title: 'Scanning Python functions...',
                    cancellable: false,
                },
                async () => {
                    return new Promise<void>((resolve, reject) => {
                        // Get interpreter from VS Code settings or fallback to 'python'
                        const pythonPath =
                            vscode.workspace.getConfiguration('python').get<string>('defaultInterpreterPath') ||
                            'python';

                        // command added to run the script: python scan_functions.py <folderPath>
                        const process = cp.spawn(pythonPath, [scriptPath, folderPath]);

                        let output = '';
                        let errorOutput = '';

                        process.stdout.on('data', (data) => {
                            output += data.toString();
                        });

                        process.stderr.on('data', (data) => {
                            errorOutput += data.toString();
                        });

                        process.on('close', (code) => {
                            if (code !== 0 || errorOutput) {
                                vscode.window.showErrorMessage(
                                    `Error: ${errorOutput || `Process exited with code ${code}`}`,
                                );
                                return reject();
                            }

                            try {
                                const result = JSON.parse(output); // To parse output from Python script

                                //  Show results in a Webview panel
                                const panel = vscode.window.createWebviewPanel(
                                    'functionAnalyzerResults',
                                    'Function Analysis Results',
                                    vscode.ViewColumn.One,
                                    {},
                                );

                                panel.webview.html = getWebviewContent(result); // Generate HTML
                                resolve();
                            } catch (e: any) {
                                vscode.window.showErrorMessage(`Failed to parse output: ${e.message}`);
                                reject();
                            }
                        });
                    });
                },
            );
        }),
    );

    setImmediate(async () => {
        const interpreter = getInterpreterFromSetting(serverId);
        if (interpreter === undefined || interpreter.length === 0) {
            traceLog(`Python extension loading`);
            await initializePython(context.subscriptions);
            traceLog(`Python extension loaded`);
        } else {
            await runServer();
        }
    });
}

// Generate HTML from function count results in a clean way
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

export async function deactivate(): Promise<void> {
    if (lsClient) {
        await lsClient.stop();
    }
}
