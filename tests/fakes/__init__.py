"""Deterministic fakes for models, stores and tools (no GPU, no network, no real client data).

Conventions the implementation is expected to honour (these are the contracts the integration and system tests rely on):

* **Models.** Agents obtain model clients only through `AgentContext.llm` (an `LLMClient`) and `vakeel_sahayak.models.*`
  interfaces. Plans and tool calls are requested with `json_schema=Model.model_json_schema()` (i.e.
  `orchestration.structured_output.constrained_generate`), so `ScriptedLLM` can dispatch on the schema *title*
  (the pydantic class name, e.g. "RetrievalPlan"). Free-text calls are dispatched on prompt substrings.
* **Stores.** Tools reach stores through `vakeel_sahayak.stores.registry.open_store(name, ...)`. `install_fake_stores`
  swaps that function (and every module-level alias of it) for the in-memory fakes in `fakes.stores`.
* **Tools.** `AgentContext.tools` maps tool names to callables with the *real* tool signatures. `fakes.toolbox.FakeToolbox`
  builds such a mapping over the in-memory stores so agents can be run without the on-disk stores.
* **Events.** Every tool call goes through `BaseAgent.call_tool` and appends TOOL_CALL then TOOL_RESULT events.
"""
