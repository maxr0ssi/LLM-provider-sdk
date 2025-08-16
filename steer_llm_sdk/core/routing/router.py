import os
import uuid
from typing import Any, AsyncGenerator, Dict, List, Union, Optional

# FastAPI imports moved to steer_llm_sdk.http.api

from ...models.conversation_types import ConversationMessage
from ...models.generation import GenerationParams, GenerationResponse, ProviderType
from ...providers.anthropic.adapter import anthropic_provider
from ...providers.openai.adapter import openai_provider
from ...providers.xai.adapter import xai_provider
from ...providers.base import ProviderError
from ...reliability import (
    EnhancedRetryManager, RetryPolicy, CircuitBreakerManager,
    CircuitBreakerConfig, CircuitState, StreamingRetryManager, StreamingRetryConfig
)
from .selector import (
    calculate_cache_savings,
    calculate_cost,
    calculate_exact_cost,
    check_lightweight_availability,
    get_available_models,
    get_config,
    get_default_hyperparameters,
    normalize_params,
)

# Router instance moved to steer_llm_sdk.http.api

class LLMRouter:
    """Router for LLM requests across different providers with conversation support."""
    
    def __init__(self):
        self.providers = {
            ProviderType.OPENAI: openai_provider,
            ProviderType.ANTHROPIC: anthropic_provider,
            ProviderType.XAI: xai_provider,
        }
        
        # Initialize reliability components
        self.retry_manager = EnhancedRetryManager(
            default_policy=RetryPolicy(
                max_attempts=3,
                initial_delay=0.5,
                backoff_factor=2.0,
                max_delay=30.0,
                respect_retry_after=True
            )
        )
        
        # Circuit breaker manager
        self.circuit_manager = CircuitBreakerManager()
        
        # Streaming retry manager
        self.streaming_retry_manager = StreamingRetryManager(self.retry_manager)
    
    def _get_circuit_breaker(self, provider_name: str):
        """Get or create circuit breaker for provider (lazy initialization)."""
        circuit_breaker = self.circuit_manager.get(provider_name)
        if not circuit_breaker:
            # Default circuit breaker config
            default_config = CircuitBreakerConfig(
                failure_threshold=5,
                success_threshold=2,
                timeout=60.0,
                window_size=60.0
            )
            circuit_breaker = self.circuit_manager.get_or_create(
                provider_name,
                default_config
            )
        return circuit_breaker
    
    def _get_retry_policy(self, provider: str, params: Dict[str, Any]) -> RetryPolicy:
        """Get retry policy for request."""
        # Check if custom retry policy is provided
        if 'retry_policy' in params:
            return params['retry_policy']
        
        # Use default policy
        return self.retry_manager.default_policy
    
    async def generate(self, 
                      messages: Union[str, List[ConversationMessage]], 
                      llm_model_id: str, 
                      raw_params: Dict[str, Any]) -> GenerationResponse:
        """Generate text using the appropriate provider with conversation support."""
        # Get model configuration
        config = get_config(llm_model_id)
        
        # Check availability
        bypass = os.getenv("STEER_SDK_BYPASS_AVAILABILITY_CHECK") == "true"
        if not bypass and not check_lightweight_availability(llm_model_id):
            raise ProviderError(
                f"Model {llm_model_id} is not available",
                provider="system",
                status_code=400
            )
        
        # Normalize parameters
        params = normalize_params(raw_params, config)
        
        # Get provider
        provider = self.providers.get(config.provider)
        if not provider:
            raise ProviderError(
                f"Provider {config.provider} not implemented",
                provider=str(config.provider),
                status_code=500
            )
        
        # Generate request ID for tracking and ensure in params
        request_id = raw_params.get('request_id', str(uuid.uuid4()))
        raw_params['request_id'] = request_id
        provider_name = config.provider.value
        
        # Get circuit breaker and retry policy
        circuit_breaker = self._get_circuit_breaker(provider_name)
        retry_policy = self._get_retry_policy(provider_name, raw_params)
        
        # Check if circuit breaker is enabled
        circuit_breaker_enabled = raw_params.get('circuit_breaker_enabled', True)
        
        async def _generate_internal():
            """Internal generation function for retry/circuit breaker."""
            # Execute through circuit breaker if enabled
            if circuit_breaker and circuit_breaker_enabled:
                return await circuit_breaker.call(
                    lambda: provider.generate(messages, params)
                )
            else:
                return await provider.generate(messages, params)
        
        # Generate response with retry
        try:
            response = await self.retry_manager.execute_with_retry(
                _generate_internal,
                request_id=request_id,
                provider=provider_name,
                policy=retry_policy
            )
            
            # Calculate exact cost if possible, fallback to estimated cost
            # Use the originally requested ID for capability/pricing lookup
            exact_cost = calculate_exact_cost(response.usage, llm_model_id)
            if exact_cost is not None:
                # Calculate cache savings for more accurate cost
                cache_savings = calculate_cache_savings(response.usage, llm_model_id)
                response.cost_usd = exact_cost - cache_savings
                
                # Add cost breakdown for transparency using model config
                prompt_tokens = response.usage.get("prompt_tokens", 0)
                completion_tokens = response.usage.get("completion_tokens", 0)
                
                # Calculate breakdown from model config pricing
                if config.input_cost_per_1k_tokens and config.output_cost_per_1k_tokens:
                    input_cost = (prompt_tokens / 1000) * config.input_cost_per_1k_tokens
                    output_cost = (completion_tokens / 1000) * config.output_cost_per_1k_tokens
                else:
                    # Fallback approximation for legacy pricing
                    input_cost = exact_cost / 2
                    output_cost = exact_cost / 2
                
                response.cost_breakdown = {
                    "input_cost": input_cost,
                    "output_cost": output_cost,
                    "cache_savings": cache_savings,
                    "total_cost": exact_cost - cache_savings
                }
                
            elif hasattr(config, 'cost_per_1k_tokens') and getattr(config, 'cost_per_1k_tokens'):
                response.cost_usd = calculate_cost(response.usage, config)
            
            return response
            
        except ProviderError as e:
            # Provider errors are already properly formatted
            raise
        except Exception as e:
            # Other errors
            raise ProviderError(
                f"Generation failed: {str(e)}",
                provider=provider_name,
                status_code=500
            )
    
    async def generate_stream(self, 
                            messages: Union[str, List[ConversationMessage]], 
                            llm_model_id: str, 
                            raw_params: Dict[str, Any],
                            return_usage: bool = False) -> AsyncGenerator[Union[str, tuple], None]:
        """Generate text with streaming using the appropriate provider with conversation support.
        
        Args:
            messages: Input messages
            llm_model_id: Model ID to use
            raw_params: Parameters for generation
            return_usage: If True, yields tuples of (chunk, usage_data) where usage_data
                         is None except for the final yield which contains the usage info
                         
        Yields:
            If return_usage=False: str chunks
            If return_usage=True: (chunk, usage_data) tuples
        """
        # Get model configuration
        config = get_config(llm_model_id)
        
        # Check availability
        bypass = os.getenv("STEER_SDK_BYPASS_AVAILABILITY_CHECK") == "true"
        if not bypass and not check_lightweight_availability(llm_model_id):
            raise ProviderError(
                f"Model {llm_model_id} is not available",
                provider="system",
                status_code=400
            )
        
        # Ensure request_id present and normalized for downstream
        raw_params = dict(raw_params or {})
        request_id = raw_params.get('request_id', str(uuid.uuid4()))
        raw_params['request_id'] = request_id
        
        # Normalize parameters
        params = normalize_params(raw_params, config)
        
        # Get provider
        provider = self.providers.get(config.provider)
        if not provider:
            raise ProviderError(
                f"Provider {config.provider} not implemented",
                provider=str(config.provider),
                status_code=500
            )
        
        # Generate request ID if not provided
        request_id = raw_params.get('request_id', str(uuid.uuid4()))
        provider_name = config.provider.value
        
        # Get circuit breaker
        circuit_breaker = self._get_circuit_breaker(provider_name)
        
        # Create streaming config based on streaming options or environment
        # Check for streaming_options in extra fields (Pydantic v2)
        extra_params = getattr(params, 'model_extra', {}) or getattr(params, 'kwargs', {})
        streaming_options = extra_params.get('streaming_options')
        if streaming_options:
            # Use values from StreamingOptions
            streaming_config = StreamingRetryConfig(
                max_connection_attempts=streaming_options.max_reconnect_attempts,
                connection_timeout=streaming_options.connection_timeout,
                read_timeout=streaming_options.read_timeout,
                reconnect_on_error=streaming_options.retry_on_connection_error,
                preserve_partial_response=streaming_options.partial_response_recovery
            )
        else:
            # Use environment variables or defaults
            streaming_config = StreamingRetryConfig(
                max_connection_attempts=int(os.getenv('STEER_STREAM_MAX_RECONNECTS', '3')),
                connection_timeout=float(os.getenv('STEER_STREAM_CONN_TIMEOUT', '30.0')),
                read_timeout=float(os.getenv('STEER_STREAM_READ_TIMEOUT', '300.0')),
                reconnect_on_error=os.getenv('STEER_STREAM_RETRY_ON_ERROR', 'true').lower() == 'true',
                preserve_partial_response=os.getenv('STEER_STREAM_PRESERVE_PARTIAL', 'true').lower() == 'true'
            )
        
        # Define the stream function for retry
        async def create_stream():
            # Check circuit breaker
            if circuit_breaker and circuit_breaker.is_open():
                raise ProviderError(
                    f"Circuit breaker for {provider_name} is OPEN",
                    provider=provider_name,
                    status_code=503
                )
            
            if return_usage and hasattr(provider, 'generate_stream_with_usage'):
                return provider.generate_stream_with_usage(messages, params)
            else:
                return provider.generate_stream(messages, params)
        
        # Stream with retry logic
        try:
            async for item in self.streaming_retry_manager.stream_with_retry(
                create_stream,
                request_id=request_id,
                provider=provider_name,
                config=streaming_config
            ):
                if return_usage and not hasattr(provider, 'generate_stream_with_usage'):
                    # Add None for usage if provider doesn't support it
                    yield (item, None)
                else:
                    yield item
                    
        except ProviderError:
            raise  # Re-raise provider errors
        except Exception as e:
            raise ProviderError(
                f"Streaming generation failed: {str(e)}",
                provider=provider_name,
                status_code=500
            )
    
    def get_provider_status(self) -> Dict[str, Dict[str, Any]]:
        """Get availability status of all providers including circuit breaker state."""
        status = {}
        for provider_type, provider in self.providers.items():
            provider_name = provider_type.value
            circuit_breaker = self._get_circuit_breaker(provider_name)
            
            status[provider_name] = {
                "available": provider.is_available(),
                "circuit_breaker_state": circuit_breaker.get_state().value if circuit_breaker else "none",
                "circuit_breaker_stats": {
                    "failure_rate": circuit_breaker.stats.get_failure_rate() if circuit_breaker else 0,
                    "consecutive_failures": circuit_breaker.stats.consecutive_failures if circuit_breaker else 0,
                    "total_requests": circuit_breaker.stats.total_requests if circuit_breaker else 0
                } if circuit_breaker else None
            }
        return status
    
    def get_retry_metrics(self) -> Dict[str, Any]:
        """Get retry metrics."""
        metrics = self.retry_manager.get_metrics()
        return {
            "retry_attempts": metrics.retry_attempts,
            "retry_successes": metrics.retry_successes,
            "retry_failures": metrics.retry_failures,
            "error_counts": {k.value: v for k, v in metrics.error_counts.items()},
            "total_retry_delay": metrics.total_retry_delay
        }


# Global router instance
llm_router = LLMRouter()

# FastAPI endpoints have been moved to steer_llm_sdk.http.api
# Import from there if you need HTTP endpoints

