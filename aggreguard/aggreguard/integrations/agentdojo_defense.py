"""AgentDojo integration — expose AggreGuard as a pluggable defense.

AgentDojo defenses are ``BasePipelineElement``s inserted into the agent pipeline
(see ``AgentPipeline.from_config``). The injection-detection component (C2) maps
naturally onto AgentDojo's ``PromptInjectionDetector``; we wrap our detector so it can
sit in the ``ToolsExecutionLoop`` and scrub/abort on injected tool outputs.

``build_aggreguard_pipeline`` assembles a full pipeline with that detector inserted —
the same shape as AgentDojo's built-in ``transformers_pi_detector`` defense, but using
AggreGuard's (configurable) detector. Provenance / task-alignment / action-gating
(C1/C3/C5) operate on structured tool *calls*; richer call-level enforcement is layered
in a later iteration via the shared ``AggreGuard`` facade.

Imports of AgentDojo are local to each function so importing this module stays cheap.
"""

from __future__ import annotations

from aggreguard.middleware.injection_detect import InjectionDetector, KeywordInjectionDetector


def make_pi_detector(
    detector: InjectionDetector | None = None,
    *,
    threshold: float = 0.5,
    raise_on_injection: bool = True,
):
    """Build an AgentDojo PromptInjectionDetector backed by an AggreGuard detector."""
    from agentdojo.agent_pipeline.pi_detector import PromptInjectionDetector

    base_detector = detector or KeywordInjectionDetector()

    class AggreGuardPIDetector(PromptInjectionDetector):
        def __init__(self):
            super().__init__(mode="message", raise_on_injection=raise_on_injection)
            self._detector = base_detector
            self._threshold = threshold
            self.name = "aggreguard_pi_detector"

        def detect(self, tool_output: str) -> tuple[bool, float]:
            score = self._detector.detect(tool_output)
            return (score >= self._threshold, score)

    return AggreGuardPIDetector()


def build_aggreguard_pipeline(
    llm,
    *,
    llm_name: str | None = None,
    system_message: str | None = None,
    detector: InjectionDetector | None = None,
    tool_output_format: str | None = None,
):
    """Assemble an AgentPipeline with the AggreGuard PI detector in the tools loop.

    ``llm`` is a constructed AgentDojo LLM pipeline element (or any BasePipelineElement).
    ``llm_name`` is the model string (e.g. "local", "gpt-4o-..."); it must appear in the
    pipeline name so AgentDojo's model-addressing attacks can resolve the model — mirror
    AgentDojo's own ``f"{llm_name}-{defense}"`` naming. Falls back to ``llm.name``.
    Mirrors the no-defense pipeline shape, inserting the detector after tool execution.
    """
    import json
    from functools import partial

    from agentdojo.agent_pipeline.agent_pipeline import AgentPipeline
    from agentdojo.agent_pipeline.basic_elements import InitQuery, SystemMessage
    from agentdojo.agent_pipeline.tool_execution import (
        ToolsExecutionLoop,
        ToolsExecutor,
        tool_result_to_str,
    )

    if tool_output_format == "json":
        formatter = partial(tool_result_to_str, dump_fn=json.dumps)
    else:
        formatter = tool_result_to_str

    sys_msg = SystemMessage(system_message) if system_message is not None else SystemMessage("")
    tools_loop = ToolsExecutionLoop([
        ToolsExecutor(formatter),
        make_pi_detector(detector),
        llm,
    ])
    name = llm_name or getattr(llm, "name", None) or "llm"
    pipeline = AgentPipeline([sys_msg, InitQuery(), llm, tools_loop])
    pipeline.name = f"{name}-aggreguard"
    return pipeline
