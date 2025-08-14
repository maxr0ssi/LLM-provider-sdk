"""
Structured logging utility for provider adapters.

This module provides a consistent logging interface for all provider adapters,
ensuring structured logging with standard fields like provider, model, and request_id.
"""

import logging
import time
import uuid
from contextlib import contextmanager
from typing import Any, Dict, Optional


class ProviderLogger:
    """Structured logger for provider adapters."""
    
    def __init__(self, provider_name: str):
        """
        Initialize logger for a specific provider.
        
        Args:
            provider_name: Name of the provider (e.g., "openai", "anthropic")
        """
        self.provider = provider_name
        self.logger = logging.getLogger(f"steer_llm_sdk.providers.{provider_name}")
    
    def _format_message(self, message: str, **kwargs) -> str:
        """Format message with structured fields."""
        fields = [f"provider={self.provider}"]
        
        # Add standard fields
        for key, value in kwargs.items():
            if value is not None:
                fields.append(f"{key}={value}")
        
        return f"[{' '.join(fields)}] {message}"
    
    def debug(self, message: str, model: Optional[str] = None, 
              request_id: Optional[str] = None, **kwargs):
        """Log debug message with structured fields."""
        self.logger.debug(
            self._format_message(message, model=model, request_id=request_id, **kwargs)
        )
    
    def info(self, message: str, model: Optional[str] = None,
             request_id: Optional[str] = None, **kwargs):
        """Log info message with structured fields."""
        self.logger.info(
            self._format_message(message, model=model, request_id=request_id, **kwargs)
        )
    
    def warning(self, message: str, model: Optional[str] = None,
                request_id: Optional[str] = None, **kwargs):
        """Log warning message with structured fields."""
        self.logger.warning(
            self._format_message(message, model=model, request_id=request_id, **kwargs)
        )
    
    def error(self, message: str, model: Optional[str] = None,
              request_id: Optional[str] = None, error: Optional[Exception] = None, **kwargs):
        """Log error message with structured fields."""
        if error:
            kwargs['error_type'] = type(error).__name__
            kwargs['error_msg'] = str(error)
        
        self.logger.error(
            self._format_message(message, model=model, request_id=request_id, **kwargs)
        )
    
    @contextmanager
    def track_request(self, method: str, model: str, request_id: Optional[str] = None):
        """
        Context manager to track request timing and log key events.
        
        Args:
            method: The method being called (e.g., "generate", "stream")
            model: The model being used
            request_id: Optional request ID (generated if not provided)
            
        Yields:
            Dict with request metadata including request_id
        """
        if request_id is None:
            request_id = str(uuid.uuid4())[:8]
        
        start_time = time.time()
        
        # Log request start
        self.debug(
            f"Starting {method} request",
            model=model,
            request_id=request_id,
            method=method
        )
        
        metadata = {
            'request_id': request_id,
            'model': model,
            'method': method,
            'start_time': start_time
        }
        
        try:
            yield metadata
            
            # Log successful completion
            duration = time.time() - start_time
            self.info(
                f"Completed {method} request",
                model=model,
                request_id=request_id,
                method=method,
                duration_ms=int(duration * 1000)
            )
            
        except Exception as e:
            # Log error
            duration = time.time() - start_time
            self.error(
                f"Failed {method} request",
                model=model,
                request_id=request_id,
                method=method,
                duration_ms=int(duration * 1000),
                error=e
            )
            raise
    
    def log_usage(self, usage: Dict[str, Any], model: str, request_id: str):
        """Log token usage information."""
        prompt_tokens = usage.get('prompt_tokens', 0)
        completion_tokens = usage.get('completion_tokens', 0)
        total_tokens = usage.get('total_tokens', 0)
        
        cache_info = usage.get('cache_info', {})
        # Guard against None values from providers/mocks
        try:
            cache_read = int(cache_info.get('cache_read_input_tokens') or 0)
        except Exception:
            cache_read = 0
        try:
            cache_creation = int(cache_info.get('cache_creation_input_tokens') or 0)
        except Exception:
            cache_creation = 0
        
        self.info(
            "Token usage",
            model=model,
            request_id=request_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cache_read_tokens=cache_read if cache_read > 0 else None,
            cache_creation_tokens=cache_creation if cache_creation > 0 else None
        )
    
    def log_streaming_metrics(self, chunks: int, total_chars: int, duration: float,
                            model: str, request_id: str):
        """Log streaming performance metrics."""
        chars_per_second = total_chars / duration if duration > 0 else 0
        
        self.info(
            "Streaming metrics",
            model=model,
            request_id=request_id,
            chunks=chunks,
            total_chars=total_chars,
            duration_ms=int(duration * 1000),
            chars_per_second=int(chars_per_second)
        )