"""
LLM Constants

Central location for all LLM-related constants including pricing, 
budget management, and model configuration parameters.
"""

# LLM Rubric Rate Limiting (per-user burst control)
RUBRIC_CALLS_PER_MINUTE = 5  # Max rubric calls per user per minute
RUBRIC_BURST_WINDOW_SECONDS = 60

# LLM Budget Management
DEFAULT_LLM_DAILY_BUDGET_USD = 0.50  # Default daily LLM budget per user (reduced from $1)
LLM_COST_WARNING_THRESHOLD = 0.8  # Warn at 80% of daily budget

# LLM Budget Limits (PER USER)
MIN_LLM_DAILY_BUDGET_USD = 0.05  # Minimum daily budget per user
MAX_LLM_DAILY_BUDGET_USD = 2.00  # Maximum daily budget per user (to keep total system < $10/day)
LLM_FAST_PATH_CONFIDENCE_THRESHOLD = 0.75  # Skip LLM if simple scorer > this

# System-wide Budget Control (MVP constraint: <$10/day total)
SYSTEM_DAILY_BUDGET_USD = 10.00  # Total system budget for all users combined
MAX_CONCURRENT_USERS_BUDGET = 20  # Assume max 20 active users = $0.50 each = $10 total

# GPT-4o-mini Pricing (per 1M tokens, as of 2024)
GPT4O_MINI_INPUT_COST_PER_1M = 0.15  # $0.15 per 1M input tokens
GPT4O_MINI_OUTPUT_COST_PER_1M = 0.60  # $0.60 per 1M output tokens
GPT4O_MINI_INPUT_COST_PER_1K = GPT4O_MINI_INPUT_COST_PER_1M / 1000  # $0.00015 per 1K
GPT4O_MINI_OUTPUT_COST_PER_1K = GPT4O_MINI_OUTPUT_COST_PER_1M / 1000  # $0.00060 per 1K

# GPT-4.1 nano Pricing (per 1M tokens, as of 2024) - More cost effective!
GPT41_NANO_INPUT_COST_PER_1M = 0.10  # $0.10 per 1M input tokens
GPT41_NANO_OUTPUT_COST_PER_1M = 0.40  # $0.40 per 1M output tokens  
GPT41_NANO_INPUT_COST_PER_1K = GPT41_NANO_INPUT_COST_PER_1M / 1000  # $0.0001 per 1K
GPT41_NANO_OUTPUT_COST_PER_1K = GPT41_NANO_OUTPUT_COST_PER_1M / 1000  # $0.0004 per 1K

# Realistic Cost Estimation by Complexity (based on actual token usage)
# Assumptions: 
# - Simple: ~200 input + 50 output tokens = ~$0.00005 with nano
# - Medium: ~400 input + 100 output tokens = ~$0.00008 with nano  
# - Complex: ~600 input + 200 output tokens = ~$0.00014 with mini
LLM_COST_SIMPLE = 0.00005   # GPT-4.1 nano for simple evaluations
LLM_COST_MEDIUM = 0.00008   # GPT-4.1 nano for medium evaluations
LLM_COST_COMPLEX = 0.00014  # GPT-4o mini for complex evaluations

# Model Selection Thresholds
SIMPLE_EVAL_THRESHOLD = 0.6   # Use nano for confidence > 60%
COMPLEX_EVAL_THRESHOLD = 0.8  # Use mini only for confidence > 80% or complex rubrics
