---
name: agentic-loop
description: Multi-step reasoning with tool use — plan, act, observe, correct cycle for complex tasks
---

# Agentic Loop Skill

Use this skill when a task requires multiple steps of reasoning and tool use.

## When to Use
- Complex tasks that cannot be solved in one step
- Tasks requiring reading, writing, and running code
- Tasks that need verification and error correction

## The Loop (ReAct Pattern)

### 1. THINK
Before using any tool, analyze the task:
- What is the user asking?
- What files/tools do I need?
- What is the expected output?

### 2. PLAN
Create a short plan (1-5 steps):
- Step 1: Read/inspect relevant files
- Step 2: Make necessary changes
- Step 3: Verify the changes work
- Step 4: Report results

### 3. ACT
Execute each step using available tools:
- `read_file` — inspect code
- `write_file` — create/modify files
- `run_command` — execute commands
- `python_exec` — run code snippets
- `search_code` — find patterns in codebase

### 4. OBSERVE
After each tool call, check the result:
- Did it succeed? What did it return?
- Are there errors to fix?
- Is the output what we expected?

### 5. CORRECT
If something went wrong:
- Analyze the error
- Fix the issue
- Re-run the step

### 6. VERIFY
Before finishing:
- Run tests if they exist
- Check the output matches the request
- Ensure no regressions

## Example Flow

```
User: "Fix the bug in calculate_total function"

1. THINK: Need to find and fix a bug in calculate_total
2. PLAN: 
   - Find the function
   - Read the code
   - Identify the bug
   - Fix it
   - Test it
3. ACT: search_code("def calculate_total")
4. OBSERVE: Found in utils.py line 42
5. ACT: read_file("utils.py") 
6. OBSERVE: See the function, bug is in line 45
7. ACT: apply_patch with fix
8. OBSERVE: Patch applied
9. ACT: python_exec with test code
10. OBSERVE: Test passes
11. VERIFY: Run full test suite
12. DONE: "Fixed the bug in calculate_total - was a type error on line 45"
```

## Rules
- Always restate the problem before starting
- Execute one step at a time
- If a step fails, analyze why before retrying
- Never skip verification
- Summarize what was accomplished at the end
