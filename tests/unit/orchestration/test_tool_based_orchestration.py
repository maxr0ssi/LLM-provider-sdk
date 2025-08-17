"""Test the new tool-based orchestration architecture."""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from typing import Dict, Any, Optional

from steer_llm_sdk.orchestration import (
    Orchestrator,
    OrchestratorOptions,
    Tool,
    get_global_registry,
    EvidenceBundle,
    BundleMeta,
    BundleSummary,
    Replicate,
    ReplicateQuality
)
from steer_llm_sdk.streaming.manager import EventManager


class MockTool(Tool):
    """Mock tool for testing."""
    
    def __init__(self, name: str = "mock_tool", result: Any = None):
        self._name = name
        self._result = result or {"data": "mock result"}
        self.execute_called = False
        self.execute_args = None
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    async def execute(
        self,
        request: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None,
        event_manager: Optional[Any] = None
    ) -> Any:
        self.execute_called = True
        self.execute_args = (request, options, event_manager)
        return self._result


class MockBundleTool(Tool):
    """Mock bundle tool that returns Evidence Bundle."""
    
    @property
    def name(self) -> str:
        return "mock_bundle"
    
    async def execute(
        self,
        request: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None,
        event_manager: Optional[Any] = None
    ) -> EvidenceBundle:
        # Create mock evidence bundle
        replicates = [
            Replicate(
                id="r1",
                data={"result": "data1"},
                quality=ReplicateQuality(valid=True),
                usage={"total_tokens": 100}
            ),
            Replicate(
                id="r2",
                data={"result": "data2"},
                quality=ReplicateQuality(valid=True),
                usage={"total_tokens": 150}
            )
        ]
        
        return EvidenceBundle(
            meta=BundleMeta(
                task="test",
                k=2,
                model="mock-model",
                seeds=[11, 23]
            ),
            replicates=replicates,
            summary=BundleSummary(
                confidence=0.85,
                disagreements=[]
            ),
            usage_total={"total_tokens": 250},
            cost_total_usd=0.001
        )


class TestToolBasedOrchestration:
    """Test the tool-based orchestration system."""
    
    @pytest.fixture(autouse=True)
    def clear_registry(self):
        """Clear the tool registry before each test."""
        registry = get_global_registry()
        registry.clear()
        yield
        registry.clear()
    
    @pytest.mark.asyncio
    async def test_tool_registration(self):
        """Test registering and retrieving tools."""
        registry = get_global_registry()
        tool = MockTool("test_tool")
        
        # Register tool
        registry.register_tool(tool)
        
        # Verify registration
        assert registry.has_tool("test_tool")
        retrieved = registry.get_tool("test_tool")
        assert retrieved is tool
        
        # List tools
        tools = registry.list_tools()
        assert "test_tool" in tools
        assert tools["test_tool"]["version"] == "1.0.0"
    
    @pytest.mark.asyncio
    async def test_orchestrator_executes_tool(self):
        """Test orchestrator executes registered tool."""
        # Register tool
        tool = MockTool("executor_test")
        registry = get_global_registry()
        registry.register_tool(tool)
        
        # Run orchestrator
        orchestrator = Orchestrator()
        result = await orchestrator.run(
            request={"query": "test"},
            tool_name="executor_test",
            tool_options={"k": 3}
        )
        
        # Verify tool was called
        assert tool.execute_called
        assert tool.execute_args[0] == {"query": "test"}
        assert tool.execute_args[1]["k"] == 3
        
        # Verify result
        assert result.status == "succeeded"
        assert result.content == {"data": "mock result"}
    
    @pytest.mark.asyncio
    async def test_orchestrator_with_evidence_bundle(self):
        """Test orchestrator handles Evidence Bundle results."""
        # Register bundle tool
        tool = MockBundleTool()
        registry = get_global_registry()
        registry.register_tool(tool)
        
        # Run orchestrator
        orchestrator = Orchestrator()
        result = await orchestrator.run(
            request="analyze this",
            tool_name="mock_bundle"
        )
        
        # Verify result processing
        assert result.status == "succeeded"
        assert "evidence_bundle" in result.content
        assert result.usage == {"total_tokens": 250}
        assert result.cost_usd == 0.001
        assert result.metadata["confidence"] == 0.85
        assert result.metadata["replicate_count"] == 2
    
    @pytest.mark.asyncio
    async def test_orchestrator_tool_not_found(self):
        """Test orchestrator handles missing tool."""
        orchestrator = Orchestrator()
        
        with pytest.raises(ValueError) as exc_info:
            await orchestrator.run(
                request="test",
                tool_name="nonexistent_tool"
            )
        
        assert "Tool 'nonexistent_tool' not found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_orchestrator_with_options(self):
        """Test orchestrator passes options correctly."""
        # Register tool
        tool = MockTool("options_test")
        registry = get_global_registry()
        registry.register_tool(tool)
        
        # Run with options
        orchestrator = Orchestrator()
        result = await orchestrator.run(
            request="test",
            tool_name="options_test",
            tool_options={"custom": "value"},
            options=OrchestratorOptions(
                max_parallel=5,
                budget={"tokens": 1000},
                trace_id="trace123"
            )
        )
        
        # Verify options were merged
        tool_options = tool.execute_args[1]
        assert tool_options["custom"] == "value"
        assert tool_options["max_parallel"] == 5
        assert tool_options["global_budget"] == {"tokens": 1000}
        assert tool_options["trace_id"] == "trace123"
        
        # Verify metadata
        assert result.metadata["trace_id"] == "trace123"
        assert result.metadata["budget"] == {"tokens": 1000}
    
    @pytest.mark.asyncio
    async def test_orchestrator_with_streaming(self):
        """Test orchestrator with streaming events."""
        # Register tool
        tool = MockTool("streaming_test")
        registry = get_global_registry()
        registry.register_tool(tool)
        
        # Create event manager
        events_captured = []
        
        async def capture_event(event):
            events_captured.append(event)
        
        event_manager = EventManager(
            on_start=capture_event,
            on_complete=capture_event
        )
        
        # Run with streaming
        orchestrator = Orchestrator()
        result = await orchestrator.run(
            request="test",
            tool_name="streaming_test",
            options=OrchestratorOptions(streaming=True),
            event_manager=event_manager
        )
        
        # Verify events were emitted
        assert len(events_captured) >= 2  # start and complete
        start_events = [e for e in events_captured if hasattr(e, 'provider')]
        assert any(e.metadata.get('tool_name') == 'streaming_test' for e in start_events)
    
    @pytest.mark.asyncio
    async def test_orchestrator_timeout(self):
        """Test orchestrator timeout handling."""
        # Create slow tool
        class SlowTool(Tool):
            @property
            def name(self) -> str:
                return "slow_tool"
            
            async def execute(self, request, options=None, event_manager=None):
                import asyncio
                await asyncio.sleep(2)  # Sleep longer than timeout
                return {"data": "should not reach here"}
        
        # Register tool
        tool = SlowTool()
        registry = get_global_registry()
        registry.register_tool(tool)
        
        # Run with timeout
        orchestrator = Orchestrator()
        with pytest.raises(Exception) as exc_info:
            await orchestrator.run(
                request="test",
                tool_name="slow_tool",
                options=OrchestratorOptions(timeout_ms=100)  # 100ms timeout
            )
        
        assert "BudgetExceeded" in str(type(exc_info.value))
    
    @pytest.mark.asyncio
    async def test_orchestrator_tool_error_handling(self):
        """Test orchestrator handles tool errors gracefully."""
        # Create failing tool
        class FailingTool(Tool):
            @property
            def name(self) -> str:
                return "failing_tool"
            
            async def execute(self, request, options=None, event_manager=None):
                raise RuntimeError("Tool execution failed")
        
        # Register tool
        tool = FailingTool()
        registry = get_global_registry()
        registry.register_tool(tool)
        
        # Run and expect error result
        orchestrator = Orchestrator()
        result = await orchestrator.run(
            request="test",
            tool_name="failing_tool"
        )
        
        # Verify error handling
        assert result.status == "failed"
        assert "error" in result.content
        assert result.errors["failing_tool"]["type"] == "RuntimeError"
        assert result.errors["failing_tool"]["message"] == "Tool execution failed"