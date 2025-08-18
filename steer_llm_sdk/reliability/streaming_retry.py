"""
Streaming-specific retry manager.

This module handles retry logic for streaming connections,
including connection resilience and partial response recovery.
"""

from dataclasses import dataclass
from typing import Optional, AsyncGenerator, Callable, Any, TypeVar, Dict
import asyncio
import logging
import time
import os

from .enhanced_retry import AdvancedRetryManager
from .state import StreamState
from ..providers.base import ProviderError
from ..reliability.error_classifier import ErrorClassifier, ErrorCategory

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class StreamingRetryConfig:
    """Configuration for streaming retries."""
    max_connection_attempts: int = 3
    connection_timeout: float = 30.0
    read_timeout: float = 300.0
    reconnect_on_error: bool = True
    preserve_partial_response: bool = True
    backoff_multiplier: float = 1.5
    initial_backoff: float = 0.5
    max_backoff: float = 30.0


class StreamingRetryManager:
    """
    Handles retry logic for streaming connections.
    
    Works in conjunction with AdvancedRetryManager to provide
    streaming-specific retry capabilities.
    """
    
    def __init__(self, retry_manager: AdvancedRetryManager):
        self.retry_manager = retry_manager
        self.stream_states: Dict[str, StreamState] = {}
        self._state_ttl_seconds: float = float(os.getenv('STEER_STREAMING_STATE_TTL', '900'))  # 15 minutes default
        
    async def stream_with_retry(
        self,
        stream_func: Callable[[], AsyncGenerator[T, None]],
        request_id: str,
        provider: str,
        config: Optional[StreamingRetryConfig] = None
    ) -> AsyncGenerator[T, None]:
        """
        Execute streaming function with retry and recovery.
        
        Args:
            stream_func: Async function that returns a stream generator
            request_id: Unique request identifier
            provider: Provider name for tracking
            config: Optional streaming retry configuration
            
        Yields:
            Stream chunks with automatic retry on failure
            
        Raises:
            Last exception if all retry attempts fail
        """
        config = config or StreamingRetryConfig()
        self._cleanup_expired_states()
        state = StreamState(request_id=request_id, provider=provider)
        self.stream_states[request_id] = state
        
        attempt = 0
        backoff = config.initial_backoff
        
        while attempt < config.max_connection_attempts:
            try:
                # Log connection attempt
                if attempt > 0:
                    logger.info(
                        f"Retrying stream connection for {request_id}",
                        extra={
                            "request_id": request_id,
                            "provider": provider,
                            "attempt": attempt + 1,
                            "chunks_received": len(state.chunks)
                        }
                    )
                
                # Attempt connection with timeout
                stream = await self._connect_with_timeout(
                    stream_func,
                    config.connection_timeout,
                    request_id
                )
                
                # Stream chunks with read timeout
                try:
                    async for chunk in self._read_with_timeout(
                        stream,
                        config.read_timeout,
                        state
                    ):
                        yield chunk
                    
                    # Success - clean up
                    del self.stream_states[request_id]
                    return
                except Exception as e:
                    # Re-raise to be caught by outer exception handler
                    raise
                
            except asyncio.TimeoutError as e:
                attempt += 1
                if attempt >= config.max_connection_attempts:
                    # Don't delete state yet - leave it for partial response retrieval
                    raise ProviderError(
                        f"Stream connection timeout after {attempt} attempts",
                        provider=provider,
                        status_code=504  # Gateway Timeout
                    )
                
                # Log timeout and prepare for retry
                await self._handle_stream_error(
                    "Connection timeout",
                    state,
                    attempt,
                    config,
                    backoff
                )
                
                # Update backoff
                backoff = min(backoff * config.backoff_multiplier, config.max_backoff)
                
                # Wait before retry
                await asyncio.sleep(backoff)
                
            except Exception as error:
                # Classify the error
                classification = ErrorClassifier.classify_error(error, provider)
                
                attempt += 1
                if not config.reconnect_on_error or \
                   attempt >= config.max_connection_attempts or \
                   not classification.is_retryable:
                    # Don't delete state yet - leave it for partial response retrieval
                    raise
                
                # Handle reconnection
                await self._handle_stream_error(
                    str(error),
                    state,
                    attempt,
                    config,
                    backoff
                )
                
                # Update backoff
                backoff = min(backoff * config.backoff_multiplier, config.max_backoff)
                
                # Wait before retry
                await asyncio.sleep(backoff)
        
        # Should not reach here, but just in case
        del self.stream_states[request_id]
        raise ProviderError(
            f"Max streaming retry attempts ({config.max_connection_attempts}) exceeded",
            provider=provider,
            status_code=503  # Service Unavailable
        )
    
    async def _connect_with_timeout(
        self,
        stream_func: Callable,
        timeout: float,
        request_id: str
    ) -> AsyncGenerator:
        """Attempt to establish streaming connection with timeout."""
        try:
            # Create the stream generator with timeout
            async with asyncio.timeout(timeout):
                stream = await stream_func()
                return stream
        except asyncio.TimeoutError:
            logger.error(
                f"Stream connection timeout for {request_id}",
                extra={"request_id": request_id, "timeout": timeout}
            )
            raise
    
    async def _read_with_timeout(
        self,
        stream: AsyncGenerator,
        timeout: float,
        state: StreamState
    ) -> AsyncGenerator[Any, None]:
        """Read from stream with timeout on each chunk."""
        consecutive_timeouts = 0
        max_consecutive_timeouts = 3
        
        try:
            while True:
                try:
                    # Wait for next chunk with timeout
                    chunk = await asyncio.wait_for(
                        stream.__anext__(),
                        timeout=timeout
                    )
                    
                    # Reset timeout counter on successful read
                    consecutive_timeouts = 0
                    
                    # Record chunk in state
                    state.record_chunk(str(chunk))
                    
                    # Create checkpoint periodically
                    if len(state.chunks) % 10 == 0:
                        state.create_checkpoint()
                    
                    yield chunk
                    
                except asyncio.TimeoutError:
                    consecutive_timeouts += 1
                    if consecutive_timeouts >= max_consecutive_timeouts:
                        raise ProviderError(
                            f"Read timeout: No data received for {timeout * max_consecutive_timeouts} seconds",
                            provider=state.provider,
                            status_code=504  # Gateway Timeout
                        )
                    logger.warning(
                        f"Read timeout {consecutive_timeouts}/{max_consecutive_timeouts} for stream",
                        extra={
                            "request_id": state.request_id,
                            "provider": state.provider,
                            "chunks_received": len(state.chunks)
                        }
                    )
                    # After timeout, the stream is likely broken, so we need to re-raise
                    # to trigger a retry with a new stream
                    raise ProviderError(
                        f"Stream read timeout after {consecutive_timeouts} attempts",
                        provider=state.provider,
                        status_code=504
                    )
                    
        except StopAsyncIteration:
            # Normal stream completion
            pass
        except Exception:
            # Re-raise other exceptions for retry handling
            raise
        finally:
            # Ensure stream is properly closed
            if hasattr(stream, 'aclose'):
                try:
                    await stream.aclose()
                except Exception as e:
                    logger.debug(f"Error closing stream: {e}")
    
    async def _handle_stream_error(
        self,
        error_msg: str,
        state: StreamState,
        attempt: int,
        config: StreamingRetryConfig,
        backoff: float
    ):
        """Handle streaming error and prepare for retry."""
        chunks_received = len(state.chunks)
        partial_response = state.get_partial_response()[:100] + "..." if chunks_received > 0 else "None"
        
        logger.warning(
            f"Stream error, preparing retry",
            extra={
                "request_id": state.request_id,
                "provider": state.provider,
                "error": error_msg,
                "attempt": attempt,
                "chunks_received": chunks_received,
                "partial_response": partial_response,
                "backoff": backoff,
                "can_resume": state.can_resume()
            }
        )
        
        # If we have partial response and config allows, prepare for resume
        if config.preserve_partial_response and state.can_resume():
            logger.info(
                f"Will attempt to resume stream from chunk {state.get_resume_position()}",
                extra={
                    "request_id": state.request_id,
                    "resume_position": state.get_resume_position()
                }
            )
    
    def get_stream_state(self, request_id: str) -> Optional[StreamState]:
        """Get current stream state."""
        return self.stream_states.get(request_id)
    
    def has_partial_response(self, request_id: str) -> bool:
        """Check if partial response exists for request."""
        state = self.get_stream_state(request_id)
        return state is not None and len(state.chunks) > 0
    
    def get_partial_response(self, request_id: str) -> Optional[str]:
        """Get partial response for request."""
        state = self.get_stream_state(request_id)
        return state.get_partial_response() if state else None

    def cleanup_old_states(self) -> int:
        """
        Remove states older than TTL.
        
        Returns:
            Number of states cleaned up
        """
        current_time = time.time()
        expired = [k for k, v in self.stream_states.items() 
                   if current_time - v.start_time > self._state_ttl_seconds]
        for key in expired:
            del self.stream_states[key]
        return len(expired)
    
    def _cleanup_expired_states(self) -> None:
        """Cleanup old stream states to avoid memory growth."""
        now = time.time()
        expired = []
        for rid, state in self.stream_states.items():
            if (now - state.start_time) > self._state_ttl_seconds:
                expired.append(rid)
        for rid in expired:
            try:
                del self.stream_states[rid]
            except Exception:
                pass