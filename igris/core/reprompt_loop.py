"""
igris.core.reprompt_loop
--------------------------
Two-stage pipeline: context-aware LLM chat for Q&A, agentic loop with tools
only when the user's request is a task (code_task, bug_fix, review).

Flow:
    A. intent.classify()         heuristic intent           [Planning]
    B. clarify gate              short-circuit if unsure    [Planning]
    C. context-aware chat        if Q&A, return directly    [Chat]
    D. agentic pipeline          only for task requests     [Agentic]
        1. complexity tier        task_analyzer.analyze()
        2. loop template          loop_generator.generate()
        3. skills                 deterministic routing
        4. context gather         targeted MCP calls
        5. spec synthesis         the actual "reprompt"
        6. execute + self-review  bounded retry loop / multi-agent

Every agentic stage is bounded (max_review_iterations, max_tool_iterations)
so the loop can never run away -- it always terminates with *something* to
show the user, even in the worst case.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import loop_generator, task_analyzer
from .execution_graph import ExecutionGraph
from .spec import TaskSpec, build_conversation_messages, synthesize_acceptance_criteria
from .memory2 import MemoryEngine


@dataclass
class LoopResult:
    final_response: str
    needs_clarification: bool = False
    clarifying_question: str = ""
    assumption_note: str = ""
    trace: list[tuple[str, str]] = field(default_factory=list)
    iterations: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0


class RepromptLoop:
    def __init__(self, config, llm, mcp_manager, skill_loader, context_engine, intent_resolver, memory):
        self.config = config
        self.llm = llm
        self.mcp_manager = mcp_manager
        self.skills = skill_loader
        self.context = context_engine
        self.intent_resolver = intent_resolver
        self.memory = memory
        self.trace_enabled = config.get("loop.trace", False)
        self._on_stage = None  # set per-run() call; async callback(stage, detail)
        self._preview = None   # PreviewSystem instance, created per run
        # Unified memory engine
        memory2_rel = config.get("memory2.dir")
        store_dir = (config.project_root / memory2_rel) if memory2_rel else config.project_root / ".igris" / "memory2"
        self.memory2 = MemoryEngine(store_dir, model_size=config.get("model.size", "7b"))

    async def _trace(self, trace: list, stage: str, detail: str) -> None:
        trace.append((stage, detail))
        if self.trace_enabled:
            print(f"[loop:{stage}] {detail}")
        if self._on_stage:
            await self._on_stage(stage, detail)

    def _format_llm_error(self, exc: Exception) -> str:
        msg = str(exc)
        err_lower = msg.lower()
        if "connecterror" in err_lower or "connection refused" in err_lower:
            return "I can't reach the AI model. Make sure Ollama is running (`ollama serve`) and check the host in Settings."
        if "500" in msg:
            return "The AI model returned an error. Try running the model manually to verify it works, then check Settings for the correct model name."
        if "401" in msg or "unauthorized" in err_lower:
            return "Authentication failed. Check your API key in Settings."
        if "timeout" in err_lower or "timed out" in err_lower:
            return "The AI model is taking too long to respond. Check that it's running and not overloaded."
        if "connect" in err_lower:
            return "Could not connect to the AI model provider. Check Settings for the correct host and port."
        if "model" in err_lower and "not found" in err_lower:
            return "The selected model wasn't found. Make sure it's downloaded and the name in Settings is correct."
        return "I'm having trouble connecting to the AI model. Check your provider settings or try again."

    async def _research_pipeline(self, user_input: str, conversation_context: str, trace: list) -> LoopResult:
        """Run the full 12-stage research pipeline for architecture requests."""
        await self._trace(trace, "research", "launching full research pipeline (12 stages)")
        try:
            from .research.pipeline import ResearchPipeline

            async def _on_stage(stage: str, detail: str) -> None:
                await self._trace(trace, f"research:{stage}", detail)

            pipeline = ResearchPipeline(
                llm=self.llm,
                max_queries_per_area=self.config.get("research.max_queries_per_area", 25),
                max_repos_for_patterns=self.config.get("research.max_repos", 50),
                min_claim_confidence=self.config.get("research.min_confidence", 0.4),
                on_stage=_on_stage,
            )

            result = await pipeline.run(user_input)

            # Format the result for the user
            response_parts = [result.full_architecture]

            if result.quality_issues:
                response_parts.append("\n## Quality Issues Found\n")
                for issue in result.quality_issues:
                    severity_icon = {"critical": "!", "warning": "~", "info": "i"}.get(issue.severity, "?")
                    response_parts.append(f"- [{severity_icon}] **{issue.category}**: {issue.description}")
                    response_parts.append(f"  Fix: {issue.suggestion}")

            if result.confidence_summary:
                response_parts.append("\n## Confidence Summary\n")
                for k, v in sorted(result.confidence_summary.items()):
                    if not k.startswith("__"):
                        response_parts.append(f"- {k}: {v:.0%}")

            response_text = "\n".join(response_parts)

            self.memory.log_turn("user", user_input, meta={"mode": "research_pipeline"})
            self.memory.log_turn("assistant", response_text)

            return LoopResult(
                final_response=response_text,
                trace=trace,
                prompt_tokens=0,
                completion_tokens=0,
            )

        except Exception as e:
            msg = self._format_llm_error(e)
            await self._trace(trace, "research:error", msg)
            return LoopResult(final_response=msg, trace=trace)

    async def _handle_greeting(self, intent: Intent, conversation_context: str, trace: list) -> LoopResult:
        """Hardcoded greeting responses -- no LLM call, no risk of connection error."""
        await self._trace(trace, "greeting", "hardcoded greeting response")
        responses = [
            "Hello! I'm igris, your coding assistant. How can I help you today?",
            "Hi there! What would you like me to work on?",
            "Hey! I'm ready to help you code. What's the task?",
            "Salom! Qanday yordam kerak?",
        ]
        import random
        resp = random.choice(responses)
        self.memory.log_turn("greeting", resp, meta={"mode": "greeting"})
        return LoopResult(final_response=resp, trace=trace)

    async def _simple_chat(self, user_input: str, conversation_context: str, trace: list) -> LoopResult:
        """Context-aware Q&A that deliberately stays outside the tool loop."""
        await self._trace(trace, "chat", "context-aware Q&A; no agentic pipeline or tools")
        try:
            result = await self.llm.chat(
                messages=build_conversation_messages(user_input, conversation_context)
            )
            self.memory.log_turn("user", user_input, meta={"mode": "simple_chat"})
            self.memory.log_turn("assistant", result.content)

            if self._on_chunk and len(result.content) > 500:
                from .data_manager import chunk_response, validate_output
                vr = validate_output(result.content)
                if vr.passed:
                    chunks = chunk_response(result.content)
                    for c in chunks:
                        await self._on_chunk(c)
                    await self._trace(trace, "chat:chunks", f"{len(chunks)} chunk(s) streamed")

            return LoopResult(
                final_response=result.content,
                trace=trace,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
            )
        except Exception as e:
            msg = self._format_llm_error(e)
            return LoopResult(
                final_response=msg,
                trace=trace,
            )

    async def run(self, user_input: str, on_stage=None, on_preview=None, on_chunk=None) -> LoopResult:
        """
        Two-stage dispatch:
          A. Intent classify (heuristic)
          B. If ambiguous → clarify gate
          C. If Q&A (question, research, greeting) → context-aware chat, return
          D. If task (code_task, bug_fix, review, command) → full agentic pipeline
        """
        self._on_stage = on_stage
        self._on_preview = on_preview
        self._on_chunk = on_chunk
        trace: list[tuple[str, str]] = []

        # Stage A -- intent classification (heuristic, LLM escalation only if unsure)
        intent = await self.intent_resolver.classify(user_input)
        await self._trace(trace, "intent", f"{intent.category} (confidence={intent.confidence})")

        # Stage B -- clarification gate (hard block)
        hard_block = self.config.get("loop.hard_block_confidence_threshold", 0.35)
        if intent.confidence < hard_block:
            question = self.intent_resolver.build_clarifying_question(user_input, intent)
            await self._trace(trace, "clarify", question)
            self.memory.log_turn("assistant_clarify", question, meta={"intent": intent.category})
            return LoopResult(
                final_response=question,
                needs_clarification=True,
                clarifying_question=question,
                trace=trace,
            )

        # Build one small context block for either destination. It remains in
        # the user message; operating instructions stay in a system message,
        # so prior conversation text cannot supersede them.
        snapshot = self.context.snapshot()
        conversation_context = snapshot.to_prompt_block()
        await self._trace(trace, "snapshot", snapshot.summary())

        # Stage C -- research pipeline for architecture/research requests
        RESEARCH_CATEGORIES = {"research", "code_task"}
        RESEARCH_KEYWORDS = [
            "build", "create", "design", "architecture", "crm", "saas", "platform",
            "system", "app", "application", "project", "stack", "tech",
        ]
        is_research = (
            intent.category in RESEARCH_CATEGORIES
            and any(kw in user_input.lower() for kw in RESEARCH_KEYWORDS)
            and self.config.get("research.enabled", True)
        )
        if is_research:
            return await self._research_pipeline(user_input, conversation_context, trace)

        # Stage D -- hardcoded greeting responses (no LLM call needed)
        if intent.category == "greeting":
            return await self._handle_greeting(intent, conversation_context, trace)

        # Stage E -- simple chat for research/question intents (no tools, no agentic loop)
        CHAT_CATEGORIES = {"question", "research"}
        if intent.category in CHAT_CATEGORIES:
            return await self._simple_chat(user_input, conversation_context, trace)

        # Stage E -- full agentic pipeline for task intents
        threshold = self.config.get("loop.clarify_confidence_threshold", 0.55)
        assumption_note = ""

        if intent.confidence < threshold:
            assumption_note = self.intent_resolver.build_assumption_note(user_input, intent)
            await self._trace(trace, "assumption", assumption_note)

        # D1 -- complexity tier; reuse the snapshot rather than gathering a
        # second, potentially inconsistent view of the project.
        complexity = task_analyzer.analyze(user_input, intent)
        await self._trace(trace, "complexity", f"{complexity.tier} ({'; '.join(complexity.reasons)})")

        # D2 -- loop template / parallel branches (Loop Generator)
        loop_plan = loop_generator.generate(intent.category, complexity)
        await self._trace(trace, "loop_plan", loop_plan.to_prompt_block().replace("\n", " | ")[:200])

        # D3 -- skill routing
        active_skills = self.skills.select(intent, user_input)
        await self._trace(trace, "skills", ", ".join(s.name for s in active_skills) or "(none matched)")

        # D4 -- targeted context gathering via MCP
        gathered = await self.context.gather(intent, user_input, snapshot, self.mcp_manager)
        await self._trace(trace, "gather", gathered.summary())

        # D5 -- spec synthesis (the actual reprompt)
        spec = TaskSpec(
            original_input=user_input,
            intent_category=intent.category,
            domain=complexity.domain,
            acceptance_criteria=synthesize_acceptance_criteria(intent.category, user_input),
            context_block=gathered.to_prompt_block(),
            conversation_context=conversation_context,
            skill_block=self.skills.prompt_block_for(active_skills),
            loop_block=loop_plan.to_prompt_block(),
        )
        await self._trace(trace, "spec", f"{spec.domain} task, {len(spec.acceptance_criteria)} acceptance criteria")

        # D6 -- mini work cycles via ExecutionGraph with bounded retry
        enable_review = self.config.get("loop.enable_self_review", True)
        max_tool_iters = self.config.get("loop.max_tool_iterations", 8)
        max_review_iters = self.config.get("loop.max_review_iterations", 3) if enable_review else 1
        total_attempts = 0
        total_prompt_tokens = 0
        total_completion_tokens = 0

        try:
            for review_attempt in range(max_review_iters):
                if loop_plan.has_parallel:
                    response_text, pt, ct, attempt = await self._run_parallel_cycles(
                        spec, loop_plan, max_tool_iters, trace
                    )
                else:
                    response_text, pt, ct, attempt = await self._run_sequential_cycles(
                        spec, loop_plan, max_tool_iters, enable_review, trace
                    )
                total_prompt_tokens += pt
                total_completion_tokens += ct
                total_attempts += attempt

                if not enable_review or not response_text.strip():
                    break

                review_passed, feedback, rev_pt, rev_ct = await self._self_review(spec, response_text)
                total_prompt_tokens += rev_pt
                total_completion_tokens += rev_ct
                await self._trace(trace, "final_review",
                    f"attempt={review_attempt+1} pass={review_passed} feedback={feedback[:120]}")

                if review_passed:
                    break

                if review_attempt < max_review_iters - 1:
                    spec = spec.with_feedback(feedback)
                else:
                    response_text += f"\n\n[Review note: {feedback}]"

            response_text = response_text or "(no output produced)"

        except Exception as e:
            msg = self._format_llm_error(e)
            await self._trace(trace, "error", msg)
            return LoopResult(final_response=msg, trace=trace)

        if assumption_note:
            response_text = f"_{assumption_note}_\n\n{response_text}"

        self.memory.log_turn("user", user_input, meta={"intent": intent.category, "complexity": complexity.tier})
        self.memory.log_turn("assistant", response_text, meta={"iterations": total_attempts})

        self.memory2.remember(user_input, session_id="default", question=user_input, answer=response_text[:2000])
        self.memory2.remember(
            f"[{intent.category}] {user_input[:200]} -> {response_text[:200]}",
            session_id="default", tags=["task", intent.category]
        )

        return LoopResult(
            final_response=response_text,
            trace=trace,
            iterations=total_attempts,
            assumption_note=assumption_note,
            prompt_tokens=total_prompt_tokens,
            completion_tokens=total_completion_tokens,
        )

    async def _run_sequential_cycles(
        self, spec: TaskSpec, loop_plan, max_tool_iters: int, enable_review: bool, trace: list
    ) -> tuple[str, int, int, int]:
        """Run mini work cycles one at a time. Each cycle gets a focused prompt and verified before next."""
        parts = []
        total_prompt_tokens = 0
        total_completion_tokens = 0
        full_tool_desc = self.mcp_manager.describe_tools() if self.mcp_manager else ""
        current_spec = spec

        self._preview = None

        for i, cycle in enumerate(loop_plan.cycles):
            if cycle.name in ("preview", "analyze_preview"):
                preview_part, ppt, pct = await self._run_preview_cycle(cycle, trace)
                parts.append(preview_part)
                total_prompt_tokens += ppt
                total_completion_tokens += pct
                await self._trace(trace, f"cycle_{cycle.name}", f"preview done, {len(preview_part)} chars")
                continue

            system = current_spec.to_system_prompt(tool_description=full_tool_desc)
            if current_spec.conversation_context:
                system += "\n\n## Workspace context\n" + current_spec.conversation_context
            previous = "\n".join(parts[-2:]) if parts else "This is the first cycle."
            cycle_prompt = (
                f"## Mini Work Cycle {i+1}/{len(loop_plan.cycles)}: {cycle.name}\n\n"
                f"**Goal:** {cycle.goal}\n"
                f"**Available tools:** {cycle.tool_group}\n\n"
                f"**Previous work:**\n{previous}\n\n"
                f"Focus ONLY on this cycle's goal. Do not do future work."
            )

            result = await self.llm.run_with_tools(
                system_prompt=system,
                user_prompt=cycle_prompt,
                mcp_manager=self.mcp_manager,
                max_iterations=max_tool_iters,
            )

            cycle_text = f"## Cycle {i+1}: {cycle.name}\n" + result.content
            parts.append(cycle_text)
            total_prompt_tokens += result.prompt_tokens

            if self._on_chunk and len(result.content) > 300:
                from .data_manager import chunk_response, validate_output
                vr = validate_output(result.content)
                if vr.passed:
                    chunks = chunk_response(result.content, chunk_callback=None)
                    for c in chunks:
                        await self._on_chunk(c)
            total_completion_tokens += result.completion_tokens

            cycle.result = result.content[:200]
            fallback_note = " (fallback)" if result.used_fallback_parsing else ""
            await self._trace(trace, f"cycle_{cycle.name}",
                f"done, {len(result.content)} chars, {result.tool_iterations} tool rounds, {result.prompt_tokens}+{result.completion_tokens} tokens{fallback_note}")

            if enable_review and i < len(loop_plan.cycles) - 1:
                ok, feedback, rpt, rct = await self._self_review(current_spec, result.content[:2000])
                total_prompt_tokens += rpt
                total_completion_tokens += rct
                if not ok:
                    await self._trace(trace, f"cycle_{cycle.name}_review", f"FAIL: {feedback[:100]}")
                    current_spec = current_spec.with_feedback(feedback)

        if self._preview:
            await self._preview.close()
            self._preview = None

        return "\n\n".join(parts), total_prompt_tokens, total_completion_tokens, len(loop_plan.cycles)

    async def _run_preview_cycle(self, cycle, trace: list) -> tuple[str, int, int]:
        """Run a preview or analyze_preview mini-cycle using the PreviewSystem.

        PreviewSystem auto-detects project type (web, API, CLI, desktop, etc.)
        and runs the appropriate tester(s). Results include screenshots for
        web/desktop, console logs for web, test reports for libraries, etc.
        """
        from .preview import PreviewSystem

        project_root = self.config.project_root

        if cycle.name == "preview":
            if self._preview is None:
                self._preview = PreviewSystem(project_root)

            ps = self._preview
            result = await ps.start_preview()

            if self._on_preview:
                await self._on_preview(result)

            output_parts = [f"### Live Test Results"]
            output_parts.append(result.to_text())

            return "\n".join(output_parts), 0, 0

        elif cycle.name == "analyze_preview":
            if self._preview is None:
                return "## Preview analysis\nNo test data available.", 0, 0

            return "## Preview analysis\nSee test results above.", 0, 0

        return "", 0, 0

    async def _run_parallel_cycles(
        self, spec: TaskSpec, loop_plan, max_tool_iters: int, trace: list
    ) -> tuple[str, int, int, int]:
        """
        Run independent subsystem branches concurrently via ExecutionGraph.
        Each subsystem runs one focused call (internal mini-cycle decomposition
        is prompt-level, not separate LLM calls).
        """
        from .execution_graph import ExecutionGraph

        full_tool_desc = self.mcp_manager.describe_tools() if self.mcp_manager else ""
        graph = ExecutionGraph()
        total_prompt_tokens = 0
        total_completion_tokens = 0

        for group in loop_plan.parallel_groups:
            prefix = group[0].name.split("_")[0]
            cycle_names = " -> ".join(f"{c.name.split('_')[-1]}:{c.goal}" for c in group)

            async def _run_branch(c_list=group, sub=prefix, stages=cycle_names):
                system = spec.to_system_prompt(tool_description=full_tool_desc)
                if spec.conversation_context:
                    system += "\n\n## Workspace context\n" + spec.conversation_context
                user = (
                    f"## Subsystem: {sub}\n\n"
                    f"**Internal stages:** {stages}\n\n"
                    f"**Acceptance criteria:**\n" + "\n".join(f"- {ac}" for ac in spec.acceptance_criteria)
                )
                result = await self.llm.run_with_tools(
                    system_prompt=system,
                    user_prompt=user,
                    mcp_manager=self.mcp_manager,
                    max_iterations=max_tool_iters,
                )
                return result

            runner = _run_branch
            runner.__name__ = f"run_{prefix}"
            graph.add(prefix, runner)

        results = await graph.run()
        for name, result in results.items():
            total_prompt_tokens += result.prompt_tokens
            total_completion_tokens += result.completion_tokens
            fallback_note = " (fallback)" if result.used_fallback_parsing else ""
            await self._trace(trace, f"branch_{name}",
                f"done, {len(result.content)} chars, {result.tool_iterations} tool rounds, {result.prompt_tokens}+{result.completion_tokens} tokens{fallback_note}")

        merged_parts = [f"## {name.capitalize()}\n{result.content}" for name, result in results.items()]
        return "\n\n".join(merged_parts), total_prompt_tokens, total_completion_tokens, len(results)

    async def _self_review(self, spec: TaskSpec, response_text: str) -> tuple[bool, str, int, int]:
        """
        LLM-as-judge pass: check the draft response against the spec's own
        acceptance criteria. Kept as a single short call with a forced
        PASS/FAIL first token so it's cheap and parseable. Returns
        (passed, feedback, prompt_tokens, completion_tokens).
        """
        criteria_block = "\n".join(f"- {c}" for c in spec.acceptance_criteria)
        review_prompt = (
            "Judge the DRAFT RESPONSE against the ACCEPTANCE CRITERIA. "
            "Reply on the first line with exactly PASS or FAIL, then on the "
            "next line give one short sentence of feedback (what to fix, if FAIL).\n\n"
            f"ACCEPTANCE CRITERIA:\n{criteria_block}\n\n"
            f"DRAFT RESPONSE:\n{response_text[:4000]}"
        )
        try:
            result = await self.llm.chat(
                messages=[
                    {"role": "system", "content": "You are a strict, terse quality reviewer."},
                    {"role": "user", "content": review_prompt},
                ]
            )
            lines = result.content.strip().splitlines()
            verdict = lines[0].strip().upper() if lines else "PASS"
            feedback = lines[1].strip() if len(lines) > 1 else ""
            return verdict.startswith("PASS"), feedback, result.prompt_tokens, result.completion_tokens
        except Exception as e:
            # Never let a review-call failure block the response from returning.
            return True, f"(review skipped: {e})", 0, 0
