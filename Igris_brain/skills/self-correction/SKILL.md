---
name: self-correction
description: >-
  Self-correction and error recovery skill. USE WHEN: agent makes a
  mistake, code fails tests, output doesn't match requirements, or
  user points out an error. Trigger on 'xato', 'error', 'noto\'g\'ri',
  'yomon', 'broken', 'ishlamayapti', 'fix this', 'tuzat'.
---

# Self-Correction Skill

## When to Use

- Code produces errors
- Tests fail
- Output doesn't match requirements
- User points out a mistake
- Agent realizes own error

## Correction Workflow

### 1. Acknowledge
```python
# BAD: Defending the original code
# GOOD: Acknowledging the issue
print("You're right — that code has a bug. Let me fix it.")
```

### 2. Diagnose
```python
# Read the error message carefully
# Identify root cause, not just symptoms
# Check if the fix addresses the actual problem
```

### 3. Fix
```python
# Minimal change to fix the issue
# Don't over-engineer the fix
# Keep existing functionality intact
```

### 4. Verify
```python
# Run the code again
# Test edge cases
# Confirm the fix works
```

### 5. Learn
```python
# Document what went wrong
# Update tests to prevent regression
# Share the learning
```

## Common Error Patterns

| Error | Root Cause | Fix Pattern |
|-------|-----------|-------------|
| `NameError` | Undefined variable | Check scope, import |
| `TypeError` | Wrong argument type | Add type checking |
| `IndexError` | Array bounds | Add length check |
| `KeyError` | Missing dict key | Use `.get()` or check |
| `AttributeError` | Wrong method/attr | Check object type |
| `ValueError` | Invalid value | Add validation |
| `ImportError` | Missing dependency | Install or mock |

## Self-Correction Templates

### Code Error
```
Issue: [error message]
Root cause: [why it happened]
Fix: [what changed]
Verification: [how I confirmed it works]
```

### Wrong Approach
```
Original approach: [what I tried]
Why it failed: [reason]
New approach: [what I'm doing instead]
Impact: [what this affects]
```

### Requirement Mismatch
```
What was built: [current behavior]
What was needed: [actual requirement]
Gap: [difference]
Action: [how to bridge the gap]
```

## Prevention Checklist

Before submitting code:
- [ ] Run all tests
- [ ] Check edge cases (empty, null, zero, negative)
- [ ] Verify error handling
- [ ] Test with real data
- [ ] Review own code as if from outside
