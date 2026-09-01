---
name: code-generation
description: Full code generation pipeline — from requirements to working code with tests
---

# Code Generation Skill

Use this skill when the user asks to write code, create a program, or build an application.

## Workflow

### 1. Understand Requirements
- What language/framework?
- What functionality?
- Any constraints or preferences?

### 2. Plan the Structure
- Main files needed
- Function/module breakdown
- Dependencies

### 3. Generate Code
- Write clean, commented code
- Follow language conventions
- Include error handling

### 4. Test the Code
- Run the code to verify it works
- Fix any issues
- Add unit tests if requested

### 5. Deliver
- Provide the working code
- Explain how to run it
- Suggest improvements

## Language-Specific Guides

### Python
```python
# Structure
- main.py or app.py (entry point)
- requirements.txt (dependencies)
- tests/ (test files)

# Run
python main.py
python -m pytest tests/
```

### JavaScript/TypeScript
```javascript
// Structure
- src/ (source files)
- package.json (dependencies)
- index.js or src/index.ts (entry point)

// Run
npm install
npm start
npm test
```

### HTML/CSS/JS
```html
<!-- Structure -->
- index.html (main page)
- style.css (styles)
- script.js (logic)

<!-- Run -->
# Open index.html in browser
# Or: python -m http.server 8000
```

## Code Quality Rules

### 1. Write Simple Code
- Clear variable names
- Short functions
- Minimal complexity

### 2. Add Comments
- Explain "why", not "what"
- Document tricky parts
- Include examples

### 3. Handle Errors
- Try/catch blocks
- Input validation
- Graceful degradation

### 4. Test
- Run the code after writing
- Fix errors immediately
- Add tests for critical paths

## Example

```
User: "Write a Python function to calculate factorial"

1. Understand: Need a factorial function in Python
2. Plan: Single function, handle edge cases
3. Generate:
```python
def factorial(n: int) -> int:
    """Calculate factorial of n."""
    if n < 0:
        raise ValueError("n must be non-negative")
    if n <= 1:
        return 1
    return n * factorial(n - 1)
```
4. Test:
```python
assert factorial(0) == 1
assert factorial(5) == 120
assert factorial(10) == 3628800
```
5. Deliver: "Here's the factorial function with tests"
```

## Rules
- Always verify code works before delivering
- Keep it simple and readable
- Handle edge cases
- Provide clear documentation
