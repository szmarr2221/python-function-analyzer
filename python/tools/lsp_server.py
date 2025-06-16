from pygls.server import LanguageServer
from lsprotocol.types import ExecuteCommandParams, MessageType
import os
import ast
import traceback

# Constants
EXECUTE_COMMAND = "workspace/executeCommand"
LSP_SERVER = LanguageServer(name="function_analyzer", version="v1.0.0")

@LSP_SERVER.feature(EXECUTE_COMMAND)
async def execute_command(ls: LanguageServer, params: ExecuteCommandParams):
    try:
        command = params.command
        args = params.arguments or []

        if not args:
            raise ValueError("No arguments provided to command.")

        folder_path = args[0]

        if command == "functionAnalyzer.countFunctions":
            result = count_functions(folder_path)
            return result

        elif command == "functionAnalyzer.scanFunctions":
            result = scan_functions(folder_path)
            return result

        else:
            raise KeyError(f"Unknown command: {command}")

    except Exception as e:
        error_msg = f"LSP command failed: {str(e)}\n{traceback.format_exc()}"
        ls.show_message_log(error_msg, msg_type=MessageType.Error)
        return {}

def count_functions(folder_path: str) -> dict:
    result = {}
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.endswith(".py"):
                full_path = os.path.join(root, file)
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        tree = ast.parse(f.read())
                    func_count = sum(isinstance(node, ast.FunctionDef) for node in tree.body)
                    result[full_path] = func_count
                except Exception:
                    continue
    return result

def scan_functions(folder_path: str) -> dict:
    result = {}
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.endswith(".py"):
                full_path = os.path.join(root, file)
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        tree = ast.parse(f.read())
                    functions = []
                    for node in tree.body:
                        if isinstance(node, ast.FunctionDef):
                            functions.append({
                                "name": node.name,
                                "lineno": node.lineno
                            })
                    result[full_path] = functions
                except Exception:
                    continue
    return result

def main():
    LSP_SERVER.start_io()

if __name__ == "__main__":
    main()
