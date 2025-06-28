import os
import asyncio
from typing import Dict, Any, AsyncGenerator, Optional
from threading import Lock

from ...models.generation import GenerationParams, GenerationResponse


class LocalHFProvider:
    """Local HuggingFace transformers provider."""
    
    def __init__(self):
        self._models = {}
        self._model_lock = Lock()
        self._loading_lock = Lock()
    
    def _load_model(self, llm_model_id: str):
        """Load a model into memory (thread-safe)."""
        with self._loading_lock:
            if llm_model_id in self._models:
                return self._models[llm_model_id]
            
            try:
                import torch
                from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
                
                # Determine device
                device = "cuda" if torch.cuda.is_available() else "cpu"
                
                # Load tokenizer and model
                tokenizer = AutoTokenizer.from_pretrained(llm_model_id)
                
                # Add padding token if it doesn't exist
                if tokenizer.pad_token is None:
                    tokenizer.pad_token = tokenizer.eos_token
                
                # Load model with appropriate settings
                model_kwargs = {
                    "torch_dtype": torch.float16 if device == "cuda" else torch.float32,
                    "device_map": "auto" if device == "cuda" else None,
                }
                
                # For larger models, use quantization if available
                if "7b" in llm_model_id.lower() or "13b" in llm_model_id.lower():
                    try:
                        import bitsandbytes
                        model_kwargs.update({
                            "load_in_4bit": True,
                            "bnb_4bit_compute_dtype": torch.float16,
                            "bnb_4bit_use_double_quant": True,
                        })
                    except ImportError:
                        pass  # Fall back to regular loading
                
                model = AutoModelForCausalLM.from_pretrained(llm_model_id, **model_kwargs)
                
                # Create pipeline
                pipe = pipeline(
                    "text-generation",
                    model=model,
                    tokenizer=tokenizer,
                    device=device if device == "cpu" else None,
                    return_full_text=False,
                    pad_token_id=tokenizer.eos_token_id
                )
                
                self._models[llm_model_id] = pipe
                return pipe
                
            except Exception as e:
                raise Exception(f"Failed to load local model {llm_model_id}: {str(e)}")
    
    async def generate(self, prompt: str, params: GenerationParams) -> GenerationResponse:
        """Generate text using local HuggingFace model."""
        try:
            # Load model if not already loaded
            pipe = self._load_model(params.model)
            
            # Prepare generation parameters
            gen_kwargs = {
                "max_new_tokens": params.max_tokens,
                "temperature": params.temperature,
                "top_p": params.top_p,
                "do_sample": params.temperature > 0,
                "pad_token_id": pipe.tokenizer.eos_token_id,
            }
            
            if params.stop:
                gen_kwargs["stop_sequences"] = params.stop
            
            # Run generation in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                lambda: pipe(prompt, **gen_kwargs)
            )
            
            # Extract generated text
            generated_text = result[0]["generated_text"]
            
            # Estimate token usage (rough approximation)
            prompt_tokens = len(prompt.split()) * 1.3  # Rough estimate
            completion_tokens = len(generated_text.split()) * 1.3
            
            usage = {
                "prompt_tokens": int(prompt_tokens),
                "completion_tokens": int(completion_tokens),
                "total_tokens": int(prompt_tokens + completion_tokens)
            }
            
            return GenerationResponse(
                text=generated_text,
                model=params.model,
                usage=usage,
                provider="local",
                finish_reason="stop"
            )
            
        except Exception as e:
            raise Exception(f"Local model error: {str(e)}")
    
    async def generate_stream(self, prompt: str, params: GenerationParams) -> AsyncGenerator[str, None]:
        """Generate text using local model with streaming (simulated)."""
        try:
            # For now, simulate streaming by yielding the full response in chunks
            response = await self.generate(prompt, params)
            text = response.text
            
            # Yield text in chunks to simulate streaming
            chunk_size = 10
            words = text.split()
            
            for i in range(0, len(words), chunk_size):
                chunk = " ".join(words[i:i + chunk_size])
                if i > 0:
                    chunk = " " + chunk
                yield chunk
                await asyncio.sleep(0.1)  # Small delay to simulate streaming
                
        except Exception as e:
            raise Exception(f"Local streaming error: {str(e)}")
    
    def is_available(self) -> bool:
        """Check if local models are available."""
        try:
            import torch
            import transformers
            return True
        except ImportError:
            return False
    
    def unload_model(self, llm_model_id: str):
        """Unload a model from memory."""
        with self._model_lock:
            if llm_model_id in self._models:
                del self._models[llm_model_id]
                # Force garbage collection
                import gc
                gc.collect()
                try:
                    import torch
                    if hasattr(torch, 'cuda') and torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except ImportError:
                    pass  # torch not available


# Global instance
local_hf_provider = LocalHFProvider()
