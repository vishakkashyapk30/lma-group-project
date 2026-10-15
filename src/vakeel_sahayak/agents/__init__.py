"""The six agents; one subpackage each (plan §3.2). LLM calls go through vakeel_sahayak.models only.

Shared machinery lives in `agents.base` (`BaseAgent`, `AgentContext`) and `agents.registry` (`get_agent_class`,
`create_agent`). Importing this package does not import the agent subpackages.
"""
