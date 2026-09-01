---
name: iteration-manager
description: Iteration management — track progress, prevent infinite loops, self-correct when stuck
---

# Iteration Manager Skill

Use this skill when executing multi-step tasks to track progress and prevent getting stuck.

## Core Concepts

### Iteration Tracking
- Each tool call is an iteration
- Maximum iterations: 8 (configurable)
- Maximum tool calls: 30 (configurable)

### Self-Correction
- If stuck, analyze what went wrong
- Try a different approach
- Don't repeat the same action

### Progress Monitoring
- Track which steps completed
- Identify blockers
- Adjust plan if needed

## Anti-Patterns to Avoid

### 1. Infinite Loops
```python
# BAD: Repeating the same failed action
while True:
    result = run_command("failing_command")
    # No analysis, no fix, just retry

# GOOD: Analyze and fix
result = run_command("failing_command")
if not result["ok"]:
    error = result["error"]
    # Analyze the error
    if "not found" in error:
        # Fix the path
        result = run_command("correct_command")
    elif "permission" in error:
        # Try different approach
        result = run_command("alternative_command")
```

### 2. Stuck in Planning
```python
# BAD: Planning forever without acting
plan = ["step1", "step2", "step3", "step4", "step5", "step6", "step7", "step8"]
# Never executes

# GOOD: Plan and execute
plan = ["step1", "step2", "step3"]
for step in plan:
    execute(step)
    if failed:
        replan_and_continue()
```

### 3. Ignoring Errors
```python
# BAD: Continuing despite errors
result1 = run_command("command1")  # fails
result2 = run_command("command2")  # also fails
# Never checked result1

# GOOD: Check and handle each result
result1 = run_command("command1")
if not result1["ok"]:
    fix_error(result1)
    result1 = run_command("command1")  # retry

result2 = run_command("command2")
if not result2["ok"]:
    fix_error(result2)
```

## Best Practices

### 1. Track State
```python
completed_steps = []
failed_steps = []

for step in steps:
    result = execute_step(step)
    if result["ok"]:
        completed_steps.append(step)
    else:
        failed_steps.append((step, result["error"]))
        # Analyze and fix before continuing
```

### 2. Use Checkpoints
```python
# Save progress periodically
save_checkpoint({
    "completed": completed_steps,
    "failed": failed_steps,
    "current_step": current_step
})

# Resume from checkpoint if interrupted
checkpoint = load_checkpoint()
if checkpoint:
    completed_steps = checkpoint["completed"]
```

### 3. Limit Retries
```python
max_retries = 2
retry_count = 0

while retry_count < max_retries:
    result = execute_step(step)
    if result["ok"]:
        break
    retry_count += 1
    # Analyze and fix
    analyze_error(result)
    fix_issue()

if retry_count >= max_retries:
    # Give up gracefully
    report_failure(step, "Max retries exceeded")
```

## Progress Reporting

### During Execution
```
Step 1/5: Reading files ✓
Step 2/5: Analyzing code ✓
Step 3/5: Fixing bug ✓
Step 4/5: Running tests ✗ (failed)
  - Retrying with different approach...
  - Retrying again...
Step 4/5: Running tests ✓
Step 5/5: Reporting results ✓
```

### At Completion
```
Task completed:
- 5 steps executed
- 12 tool calls made
- 1 retry needed
- Duration: 45 seconds
```

## Rules
- Always track which steps completed
- Don't repeat failed actions without analysis
- Use checkpoints for long tasks
- Report progress to the user
- Stop gracefully when stuck
