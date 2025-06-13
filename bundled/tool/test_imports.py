# test_imports.py

from pygls.server import LanguageServer
from pygls.features import EXECUTE_COMMAND
from lsprotocol.types import InitializeParams, ExecuteCommandParams, MessageType

print("✅ All imports work fine")
