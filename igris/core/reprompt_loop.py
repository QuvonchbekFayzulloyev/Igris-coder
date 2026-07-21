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

    async def _trace(self, trace: list, stage: str, detail: str) -> None:
        trace.append((stage, detail))
        if self.trace_enabled:
            print(f"[loop:{stage}] {detail}")
        if self._on_stage:
            await self._on_stage(stage, detail)

    def _format_llm_error(self, exc: Exception) -> str:
        msg = str(exc)
        if "ConnectError" in msg or "Connection refused" in msg:
            return "Ollama is not running. Start it with `ollama serve`."
        if "500" in msg:
            return "Ollama returned an error. Test it manually: `ollama run qwen3` in a terminal. If that works, check that the model name and host in Settings match exactly (default host: http://localhost:11434, default model: qwen3)."
        if "401" in msg or "Unauthorized" in msg:
            return "Invalid API key. Check your provider settings."
        if "timeout" in msg.lower():
            return "The LLM provider timed out. Check that the server is running and reachable."
        return f"LLM error: {msg}"

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

    async def _simple_chat(self, user_input: str, conversation_context: str, trace: list) -> LoopResult:
        """Context-aware Q&A that deliberately stays outside the tool loop."""
        await self._trace(trace, "chat", "context-aware Q&A; no agentic pipeline or tools")
        try:
            result = await self.llm.chat(
                messages=build_conversation_messages(user_input, conversation_context)
            )
            self.memory.log_turn("user", user_input, meta={"mode": "simple_chat"})
            self.memory.log_turn("assistant", result.content)
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

    async def run(self, user_input: str, on_stage=None) -> LoopResult:
        """
        Two-stage dispatch:
          A. Intent classify (heuristic)
          B. If ambiguous → clarify gate
          C. If Q&A (question, research, greeting) → context-aware chat, return
          D. If task (code_task, bug_fix, review, command) → full agentic pipeline
        """
        self._on_stage = on_stage
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

        # Stage D -- simple chat for Q&A intents (no tools, no agentic loop)
        QA_CATEGORIES = {"question", "greeting"}
        if intent.category in QA_CATEGORIES:
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
            acceptance_criteria=synthesize_acceptance_criteria(intent.category, user_input),
            context_block=gathered.to_prompt_block(),
            conversation_context=conversation_context,
            skill_block=self.skills.prompt_block_for(active_skills),
            loop_block="" if loop_plan.is_multi_branch else loop_plan.to_prompt_block(),
        )
        await self._trace(trace, "spec", f"{len(spec.acceptance_criteria)} acceptance criteria synthesized")

        # D6 -- bounded execute + self-review, or parallel multi-agent branches
        max_reviews = self.config.get("loop.max_review_iterations", 2)
        enable_review = self.config.get("loop.enable_self_review", True)
        max_tool_iters = self.config.get("loop.max_tool_iterations", 12)
        tool_desc = self.mcp_manager.describe_tools() if self.mcp_manager else ""

        try:
            if loop_plan.is_multi_branch:
                response_text, branch_prompt_tokens, branch_completion_tokens = await self._run_multi_agent(
                    spec, loop_plan, tool_desc, max_tool_iters, trace
                )
                total_prompt_tokens = branch_prompt_tokens
                total_completion_tokens = branch_completion_tokens
                attempt = 1
                if enable_review:
                    review_passed, feedback, rev_pt, rev_ct = await self._self_review(spec, response_text)
                    total_prompt_tokens += rev_pt
                    total_completion_tokens += rev_ct
                    await self._trace(trace, "review_1", f"pass={review_passed} feedback={feedback[:120]}")
            else:
                attempt = 0
                response_text = ""
                total_prompt_tokens = 0
                total_completion_tokens = 0
                while attempt < max(max_reviews, 1):
                    attempt += 1
                    result = await self.llm.run_with_tools(
                        system_prompt=spec.to_system_prompt(tool_desc),
                        user_prompt=spec.to_user_prompt(),
                        mcp_manager=self.mcp_manager,
                        max_iterations=max_tool_iters,
                    )
                    response_text = result.content
                    total_prompt_tokens += result.prompt_tokens
                    total_completion_tokens += result.completion_tokens
                    fallback_note = " (used JSON-text tool-call fallback -- consider `ollama pull qwen3` for reliability)" if result.used_fallback_parsing else ""
                    await self._trace(trace, f"attempt_{attempt}", f"{len(response_text)} chars, {result.tool_iterations} tool rounds, {result.prompt_tokens}+{result.completion_tokens} tokens{fallback_note}")

                    if not enable_review:
                        break

                    review_passed, feedback, rev_pt, rev_ct = await self._self_review(spec, response_text)
                    total_prompt_tokens += rev_pt
                    total_completion_tokens += rev_ct
                    await self._trace(trace, f"review_{attempt}", f"pass={review_passed} feedback={feedback[:120]}")

                    if review_passed or attempt >= max_reviews:
                        break
                    spec = spec.with_feedback(feedback)
        except Exception as e:
            msg = self._format_llm_error(e)
            await self._trace(trace, "error", msg)
            return LoopResult(final_response=msg, trace=trace)

        if assumption_note:
            response_text = f"_{assumption_note}_\n\n{response_text}"

        self.memory.log_turn("user", user_input, meta={"intent": intent.category, "complexity": complexity.tier})
        self.memory.log_turn("assistant", response_text, meta={"iterations": attempt})

        return LoopResult(
            final_response=response_text,
            trace=trace,
            iterations=attempt,
            assumption_note=assumption_note,
            prompt_tokens=total_prompt_tokens,
            completion_tokens=total_completion_tokens,
        )

    async def _run_multi_agent(self, spec: TaskSpec, loop_plan, tool_desc: str, max_tool_iters: int, trace: list) -> tuple[str, int, int]:
        """
        Execution Graph path: each subsystem branch from the Loop Generator
        gets its own scoped TaskSpec and runs concurrently (branches are
        independent by construction -- loop_generator only produces them
        for complexity=multi_agent, where the subsystems were named
        explicitly and separately in the request). Results are merged
        under per-branch headings; a single review pass then judges the
        merged whole against the original acceptance criteria. Returns
        (merged_text, total_prompt_tokens, total_completion_tokens).
        """
        graph = ExecutionGraph()

        def make_branch_runner(branch_name: str, stages: list[str]):
            branch_spec = TaskSpec(
                original_input=f"[{branch_name} subsystem] {spec.original_input}",
                intent_category=spec.intent_category,
                acceptance_criteria=spec.acceptance_criteria,
                constraints=spec.constraints,
                context_block=spec.context_block,
                conversation_context=spec.conversation_context,
                skill_block=spec.skill_block,
                loop_block=f"Follow this stage sequence for the {branch_name} subsystem: {' -> '.join(stages)}",
            )

            async def _run():
                return await self.llm.run_with_tools(
                    system_prompt=branch_spec.to_system_prompt(tool_desc),
                    user_prompt=branch_spec.to_user_prompt(),
                    mcp_manager=self.mcp_manager,
                    max_iterations=max_tool_iters,
                )

            return _run

        for branch_name, stages in loop_plan.branches.items():
            graph.add(branch_name, make_branch_runner(branch_name, stages))

        results = await graph.run()
        await self._trace(trace, "multi_agent", f"ran {len(results)} branches concurrently: {', '.join(results.keys())}")

        merged_parts = [f"## {name.capitalize()}\n{result.content}" for name, result in results.items()]
        total_prompt_tokens = sum(r.prompt_tokens for r in results.values())
        total_completion_tokens = sum(r.completion_tokens for r in results.values())
        return "\n\n".join(merged_parts), total_prompt_tokens, total_completion_tokens

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
