class AgentError(Exception):
    pass


class ProviderError(AgentError):
    pass


class SchemaError(AgentError):
    pass


class ToolError(AgentError):
    pass


class TimeoutError(AgentError):
    pass


class BudgetExceededError(AgentError):
    pass


