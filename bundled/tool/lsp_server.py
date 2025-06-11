from pygls.server import LanguageServer 
from lsprotocol.types import InitializeParams, ExecuteCommandParams, MessageType
from pygls.workspace import Document

import os
import sys
import json
import ast
import traceback
from typing import Optional, Any

LSP_SERVER = LanguageServer(name="function_analyzer", version="1.0.0")

GLOBAL_SETTINGS = {}
WORKSPACE_SETTINGS = {}

def log_to_output(message: str, msg_type: MessageType = MessageType.Log) -> None:
    LSP_SERVER.show_message_log(message, msg_type)

def log_error(message: str) -> None:
    LSP_SERVER.show_message_log(message, MessageType.Error)
    LSP_SERVER.show_message(message, MessageType.Error)

def log(msg: str) -> None:
    print(f"[LSP] {msg}", file=sys.stderr)

@LSP_SERVER.command("functionAnalyzer.scanFunctions")
def scan_functions(ls: LanguageServer, params: ExecuteCommandParams) -> dict:
    log("✅ scanFunctions command received")

    if not params.arguments or not isinstance(params.arguments[0], str):
        log_error("❌ Invalid folder path.")
        return {}

    folder_path = params.arguments[0]
    result = {}

    try:
        for root, _, files in os.walk(folder_path):
            for file in files:
                if file.endswith(".py"):
                    full_path = os.path.join(root, file)
                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            source = f.read()
                        tree = ast.parse(source)
                        count = sum(isinstance(node, ast.FunctionDef) for node in tree.body)
                        result[full_path] = count
                    except Exception as e:
                        error_msg = f"Error: {str(e)}"
                        result[full_path] = error_msg
                        log_to_output(f"Error parsing {full_path}: {error_msg}", MessageType.Warning)
    except Exception as e:
        log_error(f"Scan failed: {e}")
        return {}

    log_to_output("✅ Scan completed.")
    return result

@LSP_SERVER.command("functionAnalyzer.countFunctions")
def count_functions(ls: LanguageServer, params: ExecuteCommandParams) -> Optional[int]:
    if not params.arguments or not isinstance(params.arguments[0], str):
        ls.show_message("⚠️ No valid file path provided.", msg_type=MessageType.Warning)
        return None

    file_path = params.arguments[0]

    if not os.path.isfile(file_path):
        ls.show_message(f"❌ File not found: {file_path}", msg_type=MessageType.Error)
        return None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        func_count = sum(isinstance(node, ast.FunctionDef) for node in tree.body)
        ls.show_message(f"{file_path} contains {func_count} top-level function(s).", msg_type=MessageType.Info)
        return func_count
    except Exception as e:
        log_error(f"Error counting functions in {file_path}:\n{traceback.format_exc()}")
        return None

@LSP_SERVER.feature("initialize")
def initialize(params: InitializeParams) -> None:
    log_to_output(f"📂 CWD Server: {os.getcwd()}")
    log_to_output(f"🧠 sys.path used by server:\n   " + "\n   ".join(sys.path))

    init_opts = params.initialization_options or {}
    GLOBAL_SETTINGS.update(init_opts.get("globalSettings", {}))
    settings = init_opts.get("settings", [])
    _update_workspace_settings(settings)

    log_to_output(f"🔧 Workspace settings:\n{json.dumps(settings, indent=4, ensure_ascii=False)}")
    log_to_output(f"🌍 Global settings:\n{json.dumps(GLOBAL_SETTINGS, indent=4, ensure_ascii=False)}")

@LSP_SERVER.feature("shutdown")
def on_shutdown(_params: Optional[Any] = None) -> None:
    log("🔌 Server shutdown")
    LSP_SERVER.stop()

@LSP_SERVER.feature("exit")
def on_exit(_params: Optional[Any] = None) -> None:
    log("❌ Server exit")
    LSP_SERVER.stop()

def _get_global_defaults():
    return {
        "path": GLOBAL_SETTINGS.get("path", []),
        "interpreter": GLOBAL_SETTINGS.get("interpreter", [sys.executable]),
        "args": GLOBAL_SETTINGS.get("args", []),
        "importStrategy": GLOBAL_SETTINGS.get("importStrategy", "useBundled"),
        "showNotifications": GLOBAL_SETTINGS.get("showNotifications", "off"),
    }

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

if __name__ == "__main__":
    try:
        log("🚀 Starting Function Analyzer LSP server...")
        LSP_SERVER.start_io()
    except Exception as e:
        log(f"🔥 LSP server failed to start:\n{traceback.format_exc()}")
