---
name: error-recovery
description: Automatic error recovery — diagnose failures, retry with fixes, self-correct when things go wrong
---

# Error Recovery Skill

Use this skill when a tool call fails or the agent encounters an error.

## Error Categories

### 1. File Errors
- `FileNotFoundError` → Check path, use `list_files` to find correct location
- `PermissionError` → Check file permissions, try different approach
- `IsADirectoryError` → Path is a directory, not a file

### 2. Command Errors
- `Command not found` → Check if tool is installed, try alternative
- `Exit code non-zero` → Read stderr, fix the command
- `Timeout` → Increase timeout or simplify the command

### 3. Code Errors
- `SyntaxError` → Fix the syntax
- `NameError` → Check variable definitions
- `ImportError` → Install missing package or fix import

### 4. Network Errors
- `Connection refused` → Check if server is running
- `Timeout` → Retry with longer timeout
- `DNS error` → Check URL/domain

## Recovery Strategy

### Step 1: Capture Full Error
```python
# Always capture the complete error message
result = run_command("some_command")
if not result["ok"]:
    error = result["error"]
    stderr = result.get("stderr", "")
    print(f"Error: {error}\nStderr: {stderr}")
```

### Step 2: Diagnose the Root Cause
- Read the error message carefully
- Check if it's a simple typo or missing dependency
- Look at the context (what was the tool trying to do?)

### Step 3: Apply Fix
- Fix the obvious issue first
- If multiple issues, fix them one at a time
- Document what you changed

### Step 4: Retry
- Re-run the original command
- If still fails, try a different approach
- Don't repeat the same mistake

## Common Fixes

### File Not Found
```bash
# Find the file first
search_code("function_name")
list_files("src/")
# Then use correct path
```

### Command Not Found
```bash
# Check if installed
run_command("which python")
run_command("pip list | grep package_name")
# Install if needed
run_command("pip install package_name")
```

### Import Error
```bash
# Check requirements
read_file("requirements.txt")
# Install missing
run_command("pip install missing_package")
```

### Syntax Error
```python
# Read the file
content = read_file("broken_file.py")
# Find the syntax error
python_exec("import ast; ast.parse(open('broken_file.py').read())")
# Fix it
apply_patch("broken_file.py", "- old_line\n+ new_line")
```

## Rules
- Never give up after first error
- Always capture the full error message
- Fix one issue at a time
- Document what you changed
- Verify the fix works
