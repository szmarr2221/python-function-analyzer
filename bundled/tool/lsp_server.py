from pygls.server import LanguageServer
from pygls.lsp.types import InitializeParams, ExecuteCommandParams, MessageType
from pygls.lsp.methods import EXECUTE_COMMAND,INITIALIZE, SHUTDOWN, EXIT
from pygls.workspace import Document

import logging
import os
import sys
import json
import ast
import traceback
from typing import Optional, Any

logging.basicConfig(level=logging.DEBUG)

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

def scan_functions(folder_path: str) -> dict:
    log(f"🔍 Scanning functions in: {folder_path}")
    result = {}

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
                    log_to_output(f"⚠️ Error parsing {full_path}: {error_msg}", MessageType.Warning)
    return result

def count_functions(file_path: str) -> Optional[int]:
    if not os.path.isfile(file_path):
        log_error(f"❌ File not found: {file_path}")
        return None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        func_count = sum(isinstance(node, ast.FunctionDef) for node in tree.body)
        return func_count
    except Exception as e:
        log_error(f"Error counting functions in {file_path}:\n{traceback.format_exc()}")
        return None

@LSP_SERVER.feature(EXECUTE_COMMAND)
async def on_execute_command(ls: LanguageServer, params: ExecuteCommandParams) -> Any:
    try:
        command = params.command
        args = params.arguments or []

        if command == "functionAnalyzer.scanFunctions":
            if not args or not isinstance(args[0], str):
                log_error("❌ Invalid folder path.")
                return {}
            return scan_functions(args[0])

        elif command == "functionAnalyzer.countFunctions":
            if not args or not isinstance(args[0], str):
                log_error("❌ Invalid file path.")
                return None
            return count_functions(args[0])

        else:
            log_error(f"⚠️ Unknown command: {command}")
            return None

    except Exception as e:
        log_error(f"🔥 Error in command handler: {e}")
