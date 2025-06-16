from pygls.server import LanguageServer
from lsprotocol.types import ExecuteCommandParams, MessageType
import os
import ast
import traceback

EXECUTE_COMMAND = "workspace/executeCommand"

LSP_SERVER = LanguageServer(name="function_analyzer", version="v0.1")

@LSP_SERVER.feature(EXECUTE_COMMAND)
async def execute_command(ls: LanguageServer, params: ExecuteCommandParams):
    try:
        command = params.command
        args = params.arguments or []

        if command == "functionAnalyzer.countFunctions":
            folder_path = args[0] if args else ""
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

        elif command == "functionAnalyzer.scanFunctions":
            folder_path = args[0] if args else ""
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

        else:
            raise KeyError(f"Unknown command: {command}")

    except Exception as e:
        ls.show_message_log(f"LSP command failed: {str(e)}\n{traceback.format_exc()}", msg_type=MessageType.Error)
        return {}

def main():
    LSP_SERVER.start_io()

if __name__ == "__main__":
    main()
