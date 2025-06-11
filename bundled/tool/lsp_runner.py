from pygls.server import LanguageServer
from pygls.workspace import Document
from lsprotocol.types import InitializeParams, MessageType

import os
import sys
import traceback
import json
import glob
import copy
from typing import Optional, Sequence

import lsp_utils as utils  # Make sure lsp_utils.py exists with run_module, RunResult, is_stdlib_file

LSP_SERVER = LanguageServer(name="function_analyzer", version="1.0.0")

# Settings
TOOL_MODULE = "scan_functions"
TOOL_ARGS = []

GLOBAL_SETTINGS = {}
WORKSPACE_SETTINGS = {}

@LSP_SERVER.feature("initialize")
def initialize(ls: LanguageServer, params: InitializeParams):
    log_to_output(f"🌐 CWD Server: {os.getcwd()}")
    paths = "\n   ".join(sys.path)
    log_to_output(f"🧠 sys.path:\n   {paths}")

    GLOBAL_SETTINGS.update(params.initialization_options.get("globalSettings", {}))
    settings = params.initialization_options.get("settings", [])
    _update_workspace_settings(settings)

    log_to_output(f"🔧 Workspace settings:\n{json.dumps(settings, indent=2)}")
    log_to_output(f"🌍 Global settings:\n{json.dumps(GLOBAL_SETTINGS, indent=2)}")

@LSP_SERVER.command("functionAnalyzer.scanFunctions")
def scan_functions(ls: LanguageServer, *args):
    if not args:
        ls.show_message("⚠️ Folder path not provided.", MessageType.Warning)
        return

    folder_path = args[0]
    if not os.path.exists(folder_path):
        ls.show_message(f"❌ Path does not exist: {folder_path}", MessageType.Error)
        return

    py_files = glob.glob(os.path.join(folder_path, "**", "*.py"), recursive=True)
    results = {}

    for file_path in py_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()
            doc = Document(uri=f"file://{file_path}", source=source)
            result = _run_tool_on_document(doc)
            if result and result.stdout.strip().isdigit():
                results[file_path] = int(result.stdout.strip())
        except Exception as e:
            log_error(f"Error analyzing {file_path}:\n{traceback.format_exc()}")

    return results

@LSP_SERVER.command("functionAnalyzer.countFunctions")
def count_functions(ls: LanguageServer, *args):
    if not args:
        ls.show_message("⚠️ No file path provided.", MessageType.Warning)
        return

    file_path = args[0]
    if not os.path.isfile(file_path):
        ls.show_message(f"❌ Not a file: {file_path}", MessageType.Error)
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()
        doc = Document(uri=f"file://{file_path}", source=source)
        result = _run_tool_on_document(doc)
        if result and result.stdout.strip().isdigit():
            return int(result.stdout.strip())
    except Exception:
        log_error(f"Error counting functions:\n{traceback.format_exc()}")

    return 0

def _update_workspace_settings(settings):
    if not settings:
        key = os.getcwd()
        WORKSPACE_SETTINGS[key] = {
            "cwd": key,
            "workspaceFS": key,
            "workspace": key,
            **_get_global_defaults(),
        }
        return

    for setting in settings:
        key = setting.get("workspace", os.getcwd())
        WORKSPACE_SETTINGS[key] = {
            "cwd": key,
            **setting,
            "workspaceFS": key,
        }

def _get_global_defaults():
    return {
        "path": GLOBAL_SETTINGS.get("path", []),
        "interpreter": GLOBAL_SETTINGS.get("interpreter", [sys.executable]),
        "args": GLOBAL_SETTINGS.get("args", []),
        "importStrategy": GLOBAL_SETTINGS.get("importStrategy", "useBundled"),
        "showNotifications": GLOBAL_SETTINGS.get("showNotifications", "off"),
    }

def _get_settings_by_document(document: Optional[Document]):
    if document is None or document.path is None:
        return list(WORKSPACE_SETTINGS.values())[0]
    key = document.path
    return WORKSPACE_SETTINGS.get(key, _get_global_defaults())

def _run_tool_on_document(
    document: Document,
    use_stdin: bool = False,
    extra_args: Optional[Sequence[str]] = None,
) -> Optional[utils.RunResult]:
    if extra_args is None:
        extra_args = []

    if str(document.uri).startswith("vscode-notebook-cell"):
        return None

    if utils.is_stdlib_file(document.path):
        return None

    settings = copy.deepcopy(_get_settings_by_document(document))
    cwd = settings["cwd"]

    argv = [TOOL_MODULE] + TOOL_ARGS + settings["args"] + extra_args
    if not use_stdin:
        argv.append(document.path)

    log_to_output(f"▶️ Running: {' '.join(argv)}")
    log_to_output(f"📂 CWD: {cwd}")

    try:
        result = utils.run_module(
            module=TOOL_MODULE,
            argv=argv,
            use_stdin=use_stdin,
            cwd=cwd,
            source=document.source,
        )
    except Exception:
        log_error(traceback.format_exc())
        return None

    if result.stderr:
        log_to_output(result.stderr)

    log_to_output(f"📄 Output from {document.uri}:\n{result.stdout}")
    return result

def log_to_output(message: str, msg_type: MessageType = MessageType.Log):
    LSP_SERVER.show_message_log(message, msg_type)

def log_error(message: str):
    LSP_SERVER.show_message_log(message, MessageType.Error)
    LSP_SERVER.show_message(message, MessageType.Error)

if __name__ == "__main__":
    try:
        print("🚀 Starting Function Analyzer LSP server...", file=sys.stderr)
        LSP_SERVER.start_io()
    except Exception:
        print("🔥 LSP Server crashed:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
