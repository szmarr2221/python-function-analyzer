from pygls.server import LanguageServer
from lsprotocol.types import ExecuteCommandParams
import os
import ast

# Provide name and version for the server
ls = LanguageServer(name="function-analyzer", version="1.0.0")

@ls.command('functionAnalyzer.countFunctions')
def count_functions(ls: LanguageServer, params: ExecuteCommandParams):
    folder_path = params.arguments[0] if params.arguments else None
    if not folder_path:
        ls.show_message('No folder path provided.', msg_type=1)
        return {}

    result = {}
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        tree = ast.parse(f.read())
                        count = sum(isinstance(node, ast.FunctionDef) for node in ast.walk(tree))
                        result[path] = count
                except Exception as e:
                    result[path] = f'Error: {str(e)}'
    return result

if __name__ == '__main__':
    print(">>> Starting Function Analyzer LSP server...")
    ls.start_io()
