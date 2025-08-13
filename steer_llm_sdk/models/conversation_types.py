from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Any, Optional
from uuid import UUID
from enum import Enum


class TurnRole(str, Enum):
    """Conversation turn roles."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageBase(BaseModel):
    """Base class for conversation messages."""
    
    role: TurnRole
    content: str
    llm_model_id: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ConversationMessage(MessageBase):
    """Message format for LLM providers."""
    pass


class ConversationTurn(MessageBase):
    """Persisted turn in a conversation."""
    id: Optional[UUID] = None
    conversation_id: UUID
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    api_cost_usd: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow) 