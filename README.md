# Function Analyzer - VS Code Extension

The **Function Analyzer** is a Visual Studio Code extension that recursively scans Python files in a selected folder or workspace to count the number of top-level `def` functions in each `.py` file. It provides a simple and fast way to get a high-level overview of your Python project's function structure.

## 🛠 Features

- Adds a new command: `Function Analyzer: Scan Functions`
- Recursively scans all `.py` files in a folder
- Displays a count of top-level `def` functions per file in a WebView panel
- Runs a Python backend script (`scan_functions.py`) as a subprocess
- Clean and easy integration with VS Code UI

## 📦 Requirements

- [Visual Studio Code](https://code.visualstudio.com/) (version 1.64.0 or later)
- Python 3.9 or greater
- Node.js >= 18.17.0
- `npm` >= 8.19.0

## 🔧 Build and Run

1. Clone or download this repository:
    git clone https://github.com/your-username/function-analyzer-vscode.git

2. Navigate into the project folder:
    cd function-analyzer-vscode

3. Install the required Node.js packages:
    npm install

4. (Optional but recommended) Create a Python virtual environment:
    python -m venv .venv
    source .venv/bin/activate  # On Windows use: .venv\Scripts\activate

5. To just compile TypeScript manually: (npm run compile)

6. Press `F5` in VS Code to launch the extension in a new Extension Development Host window.

7. Open the file you want to run the extension on

8. Press (Crtrl+Shift+P) and type "Scan Python Functions".

## 🧪 How It Works

- When you run the command `Function Analyzer: Scan Functions`, a Python script (`scan_functions.py`) is executed in the background.
- This script recursively parses Python files using the `ast` module to count top-level function definitions.
- `sys`: for receiving command-line arguments
- The results are collected in a dictionary and returned to the VS Code extension.
- The output is shown in a styled WebView panel inside VS Code.

## 📤 Publishing
To publish your extension:

Update package.json fields like publisher, version, repository, keywords, and icon
Run:
npm run vsce-package




