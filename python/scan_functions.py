import os      
import ast     # For parsing Python code to extract function definitions
import sys     # For accessing command-line arguments
import json    

def count_top_level_functions(filepath):                    # Function to count top-level functions
    try:                                                    
        with open(filepath, 'r', encoding='utf-8') as file: # Open the file in read mode with UTF-8 encoding
            node = ast.parse(file.read(), filename=filepath)# Parse the entire file content into an AST 
                                                            
        return sum(isinstance(n, ast.FunctionDef) for n in node.body)# Count top-level nodes in the AST body are function definitions
    except Exception as e:
        return f"Error: {str(e)}"                           # If parsing fails return the error as a string

def scan_directory(directory):                              #recursively scan a directory for .py files and count functions
    result = {}                                             # Dictionary to hold file path->function count
    for root, _, files in os.walk(directory):               # Recursively walk through all folders
        for file in files:
            if file.endswith('.py'):                          # Only process Python files
                full_path = os.path.join(root, file)  
                count = count_top_level_functions(full_path)  
                result[os.path.relpath(full_path, directory)] = count
    return result

if __name__ == "__main__":
    if len(sys.argv) != 2:              # Ensure exactly one argument (the directory path) is passed
        print(json.dumps({"error": "Usage: python analyze_functions.py <directory>"}))
        sys.exit(1)

    folder_path = sys.argv[1]           # The directory to scan is passed as the first argument
    data = scan_directory(folder_path)  # Scan the directory and get results
    print(json.dumps(data))             # converts data dictionary to json and prints it to stdout