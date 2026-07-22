---
name: vibe-trending
description: Find trending GitHub repos matching the project context. Uses web_trending tool to sniff the vibe of what's hot.
pipeline_stage: Research
triggers: [research, planning, stack_decision, tool_discovery]
used_by: [reprompt-loop]
---

## Purpose
Before starting any implementation, check if there's a trending repo that already solves the problem or provides inspiration.

## Usage
When the task involves:
- Choosing a library or framework → `web_trending` with the topic
- Solving a common problem → check if a trending tool already exists
- Stack decisions → see what the community is using

## Example
For a React animation task, use:
```
web_trending topic="react animation library" language="javascript" since="monthly"
```
