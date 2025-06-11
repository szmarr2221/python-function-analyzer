# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Utility functions and classes for use with running tools over LSP."""

import contextlib
import io
import os
import runpy
import site
import subprocess
import sys
import threading
from dataclasses import dataclass
from typing import Any, Callable, List, Sequence, Tuple, Union


# ---- Data Classes ----
@dataclass
class RunResult:
    """Object to hold result from running tool."""
    stdout: str
    stderr: str


# ---- Helpers ----
def as_list(content: Union[Any, List[Any], Tuple[Any]]) -> Union[List[Any], Tuple[Any]]:
    """Ensures we always get a list."""
    if isinstance(content, (list, tuple)):
        return content
    return [content]


def is_same_path(file_path1: str, file_path2: str) -> bool:
    """Returns true if two paths are the same."""
    return os.path.normcase(os.path.normpath(file_path1)) == os.path.normcase(
        os.path.normpath(file_path2)
    )


def is_current_interpreter(executable: str) -> bool:
    """Returns true if the executable path is same as the current interpreter."""
    return is_same_path(executable, sys.executable)


_site_paths = tuple(
    os.path.normcase(os.path.normpath(p))
    for p in (as_list(site.getsitepackages()) + as_list(site.getusersitepackages()))
)


def is_stdlib_file(file_path: str) -> bool:
    """Return True if the file belongs to standard library."""
    return os.path.normcase(os.path.normpath(file_path)).startswith(_site_paths)


# ---- Context Managers ----
SERVER_CWD = os.getcwd()
CWD_LOCK = threading.Lock()


@contextlib.contextmanager
def substitute_attr(obj: Any, attribute: str, new_value: Any):
    """Temporarily substitute an attribute of an object."""
    old_value = getattr(obj, attribute)
    setattr(obj, attribute, new_value)
    try:
        yield
    finally:
        setattr(obj, attribute, old_value)


@contextlib.contextmanager
def redirect_io(stream: str, new_stream):
    """Redirect stdio streams to a custom stream."""
    old_stream = getattr(sys, stream)
    setattr(sys, stream, new_stream)
    try:
        yield
    finally:
        setattr(sys, stream, old_stream)


@contextlib.contextmanager
def change_cwd(new_cwd: str):
    """Temporarily change working directory."""
    os.chdir(new_cwd)
    try:
        yield
    finally:
        os.chdir(SERVER_CWD)


# ---- Custom IO ----
class CustomIO(io.TextIOWrapper):
    """Custom stream object to replace stdio."""

    name = None

    def __init__(self, name, encoding="utf-8", newline=None):
        self._buffer = io.BytesIO()
        self._buffer.name = name
        super().__init__(self._buffer, encoding=encoding, newline=newline)

    def close(self):
        """Custom close method (no-op)."""
        pass

    def get_value(self) -> str:
        """Returns value from the buffer as string."""
        self.seek(0)
        return self.read()


# ---- Run Code Helpers ----
def _run_module(
    module: str, argv: Sequence[str], use_stdin: bool, source: str = None
) -> RunResult:
    """Runs as a module with optional stdin."""
    str_output = CustomIO("<stdout>")
    str_error = CustomIO("<stderr>")

    with contextlib.suppress(SystemExit):
        with substitute_attr(sys, "argv", argv):
            with redirect_io("stdout", str_output), redirect_io("stderr", str_error):
                if use_stdin and source is not None:
                    str_input = CustomIO("<stdin>", newline="\n")
                    with redirect_io("stdin", str_input):
                        str_input.write(source)
                        str_input.seek(0)
                        runpy.run_module(module, run_name="__main__")
                else:
                    runpy.run_module(module, run_name="__main__")

    return RunResult(str_output.get_value(), str_error.get_value())


def run_module(
    module: str, argv: Sequence[str], use_stdin: bool, cwd: str, source: str = None
) -> RunResult:
    """Public method to run a Python module as if from CLI."""
    with CWD_LOCK:
        if is_same_path(os.getcwd(), cwd):
            return _run_module(module, argv, use_stdin, source)
        with change_cwd(cwd):
            return _run_module(module, argv, use_stdin, source)


def run_path(
    argv: Sequence[str], use_stdin: bool, cwd: str, source: str = None
) -> RunResult:
    """Run a Python script at the given path using subprocess."""
    if use_stdin:
        with subprocess.Popen(
            argv,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            cwd=cwd,
        ) as process:
            return RunResult(*process.communicate(input=source))
    else:
        result = subprocess.run(
            argv,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            cwd=cwd,
        )
        return RunResult(result.stdout, result.stderr)


def _run_api(
    callback: Callable[[Sequence[str], CustomIO, CustomIO, CustomIO | None], None],
    argv: Sequence[str],
    use_stdin: bool,
    source: str = None,
) -> RunResult:
    """Internal API-based code runner."""
    str_output = CustomIO("<stdout>")
    str_error = CustomIO("<stderr>")

    with contextlib.suppress(SystemExit):
        with substitute_attr(sys, "argv", argv):
            with redirect_io("stdout", str_output), redirect_io("stderr", str_error):
                if use_stdin and source is not None:
                    str_input = CustomIO("<stdin>", newline="\n")
                    with redirect_io("stdin", str_input):
                        str_input.write(source)
                        str_input.seek(0)
                        callback(argv, str_output, str_error, str_input)
                else:
                    callback(argv, str_output, str_error)

    return RunResult(str_output.get_value(), str_error.get_value())


def run_api(
    callback: Callable[[Sequence[str], CustomIO, CustomIO, CustomIO | None], None],
    argv: Sequence[str],
    use_stdin: bool,
    cwd: str,
    source: str = None,
) -> RunResult:
    """Run a callback-based API function in a specific cwd context."""
    with CWD_LOCK:
        if is_same_path(os.getcwd(), cwd):
            return _run_api(callback, argv, use_stdin, source)
        with change_cwd(cwd):
            return _run_api(callback, argv, use_stdin, source)
