# LangGraph Architecture Blueprint - JARVIS MARK XXXIX

**Version:** 1.0  
**Last Updated:** 2026-06-10  
**Status:** Design Phase Complete

---

## Overview

This document provides the detailed architectural blueprint for the LangGraph-driven Multi-Agent Agentic AI system that will replace the current monolithic JARVIS implementation.

---

## 1. Core Architecture

### 1.1 System Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         JARVIS LANGGRAPH ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                        STATE MANAGEMENT LAYER                          │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐  │  │
│  │  │  AgentStateSchema (TypedDict)                                    │  │  │
│  │  │  - user_input, agent_response, current_tool                      │  │  │
│  │  │  - conversation_id, turn_count, error_history                    │  │  │
│  │  │  - plan, completed_steps, step_results                           │  │  │
│  │  │  - audio_bytes, files_uploaded, current_goal                     │  │  │
│  │  └──────────────────────────────────────────────────────────────────┘  │  │
│  │                             ▲                                           │  │
│  └─────────────────────────────┼───────────────────────────────────────────┘  │
│                                │ CHECKPOINTER                               │
│                           ┌────┴────┐                                        │
│                           │MemorySaver│                                       │
│                           └─────────┘                                        │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                        AGENT NODES LAYER                               │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │  │
│  │  │audio_input  │  │intent_class │  │rag_retrieval│  │ llm_generate│  │  │
│  │  │     node    │  │    node     │  │     node    │  │     node    │  │  │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  │  │
│  │         │                 │                 │                 │         │  │
│  │         └─────────────────┴─────────────────┴─────────────────┘         │  │
│  │                             │                                             │  │
│  │                             ▼                                             │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │  │
│  │  │ tool_router │  │parallel_tool│  │memory_update│  │audio_output │  │  │
│  │  │    node     │  │  executor   │  │     node    │  │     node    │  │  │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  │  │
│  │         │                 │                 │                 │         │  │
│  │         └─────────────────┴─────────────────┴─────────────────┘         │  │
│  │                             │                                             │  │
│  │                             ▼                                             │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │  │
│  │  │error_recover│  │auto_replan  │  │interrupthand│  │goal_tracker │  │  │
│  │  │    node     │  │    node     │  │    node     │  │    node     │  │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Node Responsibilities

| Node | Responsibility | Input State Keys | Output State Keys |
|------|----------------|------------------|-------------------|
| `audio_input` | Capture microphone input | `audio_in_queue` | `user_input`, `audio_bytes` |
| `intent_classifier` | Classify user intent | `user_input` | `user_intent` |
| `rag_retrieval` | Fetch memory context | `user_input` | `context`, `memory_facts` |
| `llm_generate` | Generate response | `context`, `memory_facts` | `agent_response` |
| `tool_router` | Select tool | `agent_response`, `user_intent` | `current_tool`, `tool_parameters` |
| `parallel_tool_executor` | Execute tools concurrently | `tools_to_run` | `step_results` |
| `memory_update` | Update conversation memory | `user_input`, `agent_response` | - |
| `audio_output` | Convert to speech | `agent_response` | - |
| `error_recovery` | Handle failures | `error_history` | `next_action` |
| `auto_replan` | Plan alternative approach | `failed_steps` | `plan` |

---

## 2. State Schema Specification

### 2.1 TypedDict Definition

```python
# langgraph/types/state.py
from typing import TypedDict, Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum

class UserIntent(str, Enum):
    """User intent categories"""
    INFO_REQUEST = "info_request"
    TASK_DELEGATION = "task_delegation"
    SYSTEM_CONTROL = "system_control"
    MEMORY_QUERY = "memory_query"
    FILE_OPERATION = "file_operation"
    UTILITY = "utility"
    CONVERSATION = "conversation"
    UNKNOWN = "unknown"

class AgentState(str, Enum):
    """Agent state machine states"""
    LISTENING = "listening"
    THINKING = "thinking"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    EXECUTING = "executing"
    WAITING = "waiting"
    ERROR = "error"

class AgentStateSchema(TypedDict, total=False):
    """Core agent state - all keys are optional for flexibility"""
    
    # Session metadata
    session_id: str
    conversation_id: str
    turn_count: int
    user_id: str
    
    # Input state
    user_input: str
    user_intent: Optional[UserIntent]
    audio_bytes: Optional[bytes]
    audio_queue_item: Optional[Dict[str, Any]]
    
    # Processing state
    context: List[Dict[str, Any]]
    memory_facts: List[Dict[str, Any]]
    intent_classification_confidence: float
    current_tool: Optional[str]
    tool_parameters: Optional[Dict[str, Any]]
    tools_to_run: List[Dict[str, Any]]
    
    # Execution state
    plan: Optional[Dict[str, Any]]
    current_step: int
    completed_steps: List[Dict[str, Any]]
    step_results: Dict[str, Any]
    failed_steps: List[Dict[str, Any]]
    error_history: List[Dict[str, Any]]
    
    # Output state
    agent_response: str
    agent_state: AgentState
    next_action: Optional[str]
    
    # Memory state
    current_goal: Optional[str]
    previous_goal: Optional[str]
    goal_continuation: bool
    files_uploaded: List[str]
    
    # Streaming state
    audio_out_queue: Any  # Runtime type (asyncio.Queue)
    audio_in_queue: Any
    is_speaking: bool
    is_interrupted: bool
    
    # Performance metrics
    start_time: datetime
    response_time_ms: float
    nodes_executed: List[str]
```

### 2.2 State Transition Matrix

| Current State | Event | Next State | Trigger |
|---------------|-------|------------|---------|
| `listening` | audio_input | `thinking` | Audio stream |
| `listening` | text_input | `thinking` | Text input |
| `thinking` | intent_classified | `processing` | Intent detected |
| `thinking` | audio_complete | `processing` | Speech-to-text |
| `processing` | rag_retrieved | `processing` | Memory loaded |
| `processing` | llm_response | `executing` | Response generated |
| `executing` | tool_selected | `executing` | Router decision |
| `executing` | tool_executed | `executing` | Tool completed |
| `executing` | all_tools_done | `speaking` | Results ready |
| `speaking` | speech_complete | `listening` | Audio finished |
| `error` | recovery_succeeded | `executing` | Auto-recovery |
| `error` | recovery_failed | `waiting` | Manual intervention |
| `waiting` | user_input | `thinking` | User resumed |

---

## 3. Node Implementations

### 3.1 Audio Input Node

```python
# langgraph/nodes/audio_input.py
import asyncio
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from queue import Queue

from ..types.state import AgentStateSchema, AgentState

async def audio_input_node(state: AgentStateSchema) -> AgentStateSchema:
    """
    Capture microphone input and queue for processing.
    
    Reads from audio_in_queue and extracts text/audio.
    Sets state to listening when complete.
    """
    audio_in_queue = state.get("audio_in_queue")
    if audio_in_queue is None:
        return {**state, "agent_state": AgentState.LISTENING}
    
    try:
        # Non-blocking read with timeout
        queue_item = await asyncio.wait_for(
            audio_in_queue.get(),
            timeout=0.1
        )
        
        # Check if this is text or audio
        if "text" in queue_item:
            return {
                **state,
                "user_input": queue_item["text"],
                "agent_state": AgentState.THINKING
            }
        elif "data" in queue_item:
            # Audio data - store for later STT
            return {
                **state,
                "audio_bytes": queue_item["data"],
                "agent_state": AgentState.LISTENING
            }
            
    except asyncio.TimeoutError:
        pass
    
    return state
```

### 3.2 Intent Classifier Node

```python
# langgraph/nodes/intent_classifier.py
from ..types.state import AgentStateSchema, UserIntent

def intent_classifier_node(state: AgentStateSchema) -> AgentStateSchema:
    """
    Classify user intent using lightweight classification.
    
    Uses keyword matching + rule-based heuristics for speed.
    Falls back to LLM for ambiguous inputs.
    """
    user_input = state.get("user_input", "").lower()
    
    if not user_input:
        return {**state, "agent_state": AgentState.THINKING}
    
    # Keyword-based classification (fast)
    intent_map = {
        "weather": UserIntent.INFO_REQUEST,
        "forecast": UserIntent.INFO_REQUEST,
        "search": UserIntent.INFO_REQUEST,
        "google": UserIntent.INFO_REQUEST,
        "open": UserIntent.TASK_DELEGATION,
        "launch": UserIntent.TASK_DELEGATION,
        "play": UserIntent.TASK_DELEGATION,
        "file": UserIntent.FILE_OPERATION,
        "folder": UserIntent.FILE_OPERATION,
        "send": UserIntent.TASK_DELEGATION,
        "message": UserIntent.TASK_DELEGATION,
        "reminder": UserIntent.TASK_DELEGATION,
        "set": UserIntent.TASK_DELEGATION,
    }
    
    for keyword, intent in intent_map.items():
        if keyword in user_input:
            return {
                **state,
                "user_intent": intent,
                "agent_state": AgentState.PROCESSING,
                "intent_classification_confidence": 0.85
            }
    
    # Fallback: use LLM for classification
    return {
        **state,
        "current_tool": "classify_intent_llm",
        "agent_state": AgentState.THINKING
    }
```

### 3.3 RAG Retrieval Node

```python
# langgraph/nodes/rag_retrieval.py
from ..types.state import AgentStateSchema

def rag_retrieval_node(state: AgentStateSchema) -> AgentStateSchema:
    """
    Retrieve context from short-term and long-term memory.
    
    Uses existing JarvisRAGProcessor internally.
    """
    from memory.rag_processor import JarvisRAGProcessor
    
    processor = JarvisRAGProcessor()
    user_input = state.get("user_input", "")
    
    try:
        # Retrieve recent conversation
        context = processor._retrieve_recent_context()
        
        # Retrieve long-term facts
        memory_facts = processor._retrieve_long_term_facts(user_input)
        
        return {
            **state,
            "context": context,
            "memory_facts": memory_facts,
            "agent_state": AgentState.PROCESSING
        }
        
    except Exception as e:
        # Return empty results on error
        return {
            **state,
            "context": [],
            "memory_facts": [],
            "error_history": [
                *state.get("error_history", []),
                {"node": "rag_retrieval", "error": str(e)}
            ]
        }
```

### 3.4 LLM Generate Node

```python
# langgraph/nodes/llm_generate.py
from ..types.state import AgentStateSchema

def llm_generate_node(state: AgentStateSchema) -> AgentStateSchema:
    """
    Generate agent response using augmented LLM prompt.
    
    Combines context, memory, and user intent.
    """
    from memory.rag_processor import JarvisRAGProcessor
    
    processor = JarvisRAGProcessor()
    user_input = state.get("user_input", "")
    context = state.get("context", [])
    memory_facts = state.get("memory_facts", [])
    
    try:
        prompt = processor._build_augmented_prompt(
            user_input,
            context,
            memory_facts
        )
        
        response = processor._generate_response(prompt)
        
        return {
            **state,
            "agent_response": response or "I couldn't generate a response, sir.",
            "agent_state": AgentState.EXECUTING
        }
        
    except Exception as e:
        return {
            **state,
            "agent_response": "I encountered an error, sir.",
            "agent_state": AgentState.ERROR,
            "error_history": [
                *state.get("error_history", []),
                {"node": "llm_generate", "error": str(e)}
            ]
        }
```

### 3.5 Tool Router Node

```python
# langgraph/nodes/tool_router.py
from ..types.state import AgentStateSchema, UserIntent

def tool_router_node(state: AgentStateSchema) -> AgentStateSchema:
    """
    Route to appropriate tool based on intent and response.
    
    Returns list of tools to execute.
    """
    intent = state.get("user_intent")
    response = state.get("agent_response", "").lower()
    
    # Intent-based routing (primary)
    intent_tool_map = {
        UserIntent.INFO_REQUEST: ["web_search"],
        UserIntent.TASK_DELEGATION: ["web_search"],
        UserIntent.SYSTEM_CONTROL: ["computer_settings"],
        UserIntent.FILE_OPERATION: ["file_controller"],
        UserIntent.MEMORY_QUERY: ["rag_retrieval"],
    }
    
    if intent in intent_tool_map:
        return {
            **state,
            "tools_to_run": [{"name": t, "params": {}} for t in intent_tool_map[intent]],
            "agent_state": AgentState.EXECUTING
        }
    
    # Response-based routing (secondary)
    if "weather" in response:
        return {
            **state,
            "current_tool": "weather_report",
            "agent_state": AgentState.EXECUTING
        }
    elif "file" in response or "read" in response or "write" in response:
        return {
            **state,
            "current_tool": "file_controller",
            "agent_state": AgentState.EXECUTING
        }
    elif "screen" in response:
        return {
            **state,
            "current_tool": "screen_process",
            "agent_state": AgentState.EXECUTING
        }
    elif "youtube" in response or "video" in response:
        return {
            **state,
            "current_tool": "youtube_video",
            "agent_state": AgentState.EXECUTING
        }
    elif "open" in response or "launch" in response:
        return {
            **state,
            "current_tool": "open_app",
            "agent_state": AgentState.EXECUTING
        }
    
    # Default: no tool needed
    return {
        **state,
        "agent_state": AgentState.SPEAKING
    }
```

### 3.6 Parallel Tool Executor Node

```python
# langgraph/nodes/parallel_tool_executor.py
import asyncio
from typing import Any
from ..types.state import AgentStateSchema

async def parallel_tool_executor_node(state: AgentStateSchema) -> AgentStateSchema:
    """
    Execute multiple tools concurrently.
    
    Uses asyncio.gather for parallel execution.
    """
    tools_to_run = state.get("tools_to_run", [])
    if not tools_to_run:
        return state
    
    async def execute_tool(tool: Dict[str, Any]) -> tuple[str, Any]:
        """Execute a single tool and return result."""
        name = tool.get("name")
        params = tool.get("params", {})
        
        # Import tool dynamically
        try:
            module_name = f"actions.{name}"
            module = __import__(module_name, fromlist=[""])
            
            # Call tool function
            if hasattr(module, f"{name}_action"):
                result = await asyncio.to_thread(
                    getattr(module, f"{name}_action"),
                    {"parameters": params}
                )
            else:
                result = await asyncio.to_thread(
                    getattr(module, name),
                    {"parameters": params}
                )
            
            return name, result
        except Exception as e:
            return name, {"error": str(e)}
    
    # Execute all tools in parallel
    results = await asyncio.gather(*[execute_tool(t) for t in tools_to_run])
    
    # Collect results
    step_results = {name: result for name, result in results}
    
    return {
        **state,
        "step_results": step_results,
        "completed_steps": [
            *state.get("completed_steps", []),
            {"tool": t.get("name"), "result": step_results.get(t.get("name"))}
            for t in tools_to_run
        ],
        "agent_state": AgentState.EXECUTING
    }
```

### 3.7 Memory Update Node

```python
# langgraph/nodes/memory_update.py
from ..types.state import AgentStateSchema

def memory_update_node(state: AgentStateSchema) -> AgentStateSchema:
    """
    Update conversation memory.
    
    Saves short-term interaction and extracts long-term facts.
    """
    from memory.memory_manager import JarvisMemory
    
    user_input = state.get("user_input", "")
    agent_response = state.get("agent_response", "")
    
    if not user_input and not agent_response:
        return state
    
    try:
        memory = JarvisMemory()
        
        # Save short-term interactions
        if user_input:
            memory.save_interaction("user", user_input)
        if agent_response:
            memory.save_interaction("jarvis", agent_response)
        
        # Auto-memory consolidation
        from memory.memory_manager import should_extract_memory, extract_memory
        if should_extract_memory(user_input, agent_response):
            extracted = extract_memory(user_input, agent_response)
            if extracted:
                memory.update_memory(extracted)
        
        return state  # Memory updates are side effects
    except Exception as e:
        return {
            **state,
            "error_history": [
                *state.get("error_history", []),
                {"node": "memory_update", "error": str(e)}
            ]
        }
```

### 3.8 Audio Output Node

```python
# langgraph/nodes/audio_output.py
from ..types.state import AgentStateSchema

def audio_output_node(state: AgentStateSchema) -> AgentStateSchema:
    """
    Convert agent response to speech and play.
    
    Uses existing audio output infrastructure.
    """
    agent_response = state.get("agent_response", "")
    audio_out_queue = state.get("audio_out_queue")
    
    if not agent_response or not audio_out_queue:
        return state
    
    try:
        # Queue audio for playback
        audio_out_queue.put_nowait({
            "text": agent_response,
            "action": "speak"
        })
        
        return {
            **state,
            "agent_state": AgentState.SPEAKING
        }
    except Exception as e:
        return {
            **state,
            "agent_state": AgentState.ERROR,
            "error_history": [
                *state.get("error_history", []),
                {"node": "audio_output", "error": str(e)}
            ]
        }
```

---

## 4. Edge Definitions

### 4.1 Conditional Edge Logic

```python
# langgraph/edges.py
from typing import Literal
from ..types.state import AgentStateSchema, UserIntent, AgentState

def route_after_intent(state: AgentStateSchema) -> Literal["rag_retrieval", "llm_generate", "tool_router"]:
    """Route after intent classification."""
    if state.get("user_intent"):
        return "rag_retrieval"
    return "llm_generate"

def route_after_rag(state: AgentStateSchema) -> Literal["llm_generate", "tool_router"]:
    """Route after RAG retrieval."""
    if state.get("memory_facts"):
        return "llm_generate"
    return "tool_router"

def route_after_llm(state: AgentStateSchema) -> Literal["tool_router", "audio_output"]:
    """Route after LLM generation."""
    response = state.get("agent_response", "")
    if "tool" in response.lower():
        return "tool_router"
    return "audio_output"

def route_on_error(state: AgentStateSchema) -> Literal["error_recovery", "audio_output"]:
    """Route when error occurs."""
    errors = state.get("error_history", [])
    if errors and len(errors) < 3:
        return "error_recovery"
    return "audio_output"
```

### 4.2 Graph Construction

```python
# langgraph/graph.py
from langgraph.graph import StateGraph, END
from .types.state import AgentStateSchema
from .nodes.audio_input import audio_input_node
from .nodes.intent_classifier import intent_classifier_node
from .nodes.rag_retrieval import rag_retrieval_node
from .nodes.llm_generate import llm_generate_node
from .nodes.tool_router import tool_router_node
from .nodes.parallel_tool_executor import parallel_tool_executor_node
from .nodes.memory_update import memory_update_node
from .nodes.audio_output import audio_output_node
from .nodes.error_recovery import error_recovery_node
from .nodes.auto_replan import auto_replan_node
from .edges import (
    route_after_intent,
    route_after_rag,
    route_after_llm,
    route_on_error
)

# Create workflow
workflow = StateGraph(AgentStateSchema)

# Add nodes
workflow.add_node("audio_input", audio_input_node)
workflow.add_node("intent_classifier", intent_classifier_node)
workflow.add_node("rag_retrieval", rag_retrieval_node)
workflow.add_node("llm_generate", llm_generate_node)
workflow.add_node("tool_router", tool_router_node)
workflow.add_node("parallel_tool_executor", parallel_tool_executor_node)
workflow.add_node("memory_update", memory_update_node)
workflow.add_node("audio_output", audio_output_node)
workflow.add_node("error_recovery", error_recovery_node)
workflow.add_node("auto_replan", auto_replan_node)

# Define edges
# Main flow
workflow.add_edge("audio_input", "intent_classifier")
workflow.add_edge("intent_classifier", "rag_retrieval")
workflow.add_conditional_edges(
    "rag_retrieval",
    route_after_rag,
    {
        "llm_generate": "llm_generate",
        "tool_router": "tool_router"
    }
)
workflow.add_conditional_edges(
    "llm_generate",
    route_after_llm,
    {
        "tool_router": "tool_router",
        "audio_output": "audio_output"
    }
)
workflow.add_conditional_edges(
    "tool_router",
    route_after_llm,  # Reuse - tools may generate response
    {
        "tool_router": "parallel_tool_executor",
        "audio_output": "audio_output"
    }
)
workflow.add_edge("parallel_tool_executor", "memory_update")
workflow.add_edge("memory_update", "audio_output")
workflow.add_edge("audio_output", END)

# Error handling flow
workflow.add_conditional_edges(
    "intent_classifier",
    route_on_error,
    {
        "error_recovery": "error_recovery",
        "rag_retrieval": "rag_retrieval"
    }
)
workflow.add_edge("error_recovery", "auto_replan")
workflow.add_edge("auto_replan", "llm_generate")

# Compile
app = workflow.compile(
    checkpointer=None,  # Can be MemorySaver() for persistence
    interrupt_before=[],
    interrupt_after=[]
)
```

---

## 5. Integration with Existing System

### 5.1 Adapter Pattern

```python
# langgraph/adapters.py
from .graph import app

class LangGraphExecutor:
    """Adapter for existing main.py to use new LangGraph system."""
    
    def __init__(self):
        self.app = app
        self.checkpointer = None  # Configurable
    
    async def execute(self, state: dict) -> dict:
        """Execute the graph with given state."""
        # Merge with default state
        full_state = {
            "session_id": state.get("session_id"),
            "turn_count": state.get("turn_count", 0),
            **state
        }
        
        # Run graph
        result = await self.app.ainvoke(full_state)
        return result
    
    async def execute_streaming(self, state: dict):
        """Execute with streaming output."""
        async for output in self.app.astream(state):
            yield output
```

### 5.2 Gradual Migration Strategy

```python
# main.py - Migration section
import asyncio

# Both executors exist during migration
from agent.executor import AgentExecutor as OldExecutor
from langgraph.adapters import LangGraphExecutor

class HybridExecutor:
    """Runs both old and new executors for comparison."""
    
    def __init__(self):
        self.old_executor = OldExecutor()
        self.new_executor = LangGraphExecutor()
        self.migration_percentage = 0.5  # 50% traffic to new
    
    async def execute(self, goal: str, **kwargs):
        """Execute using hybrid approach."""
        if random.random() < self.migration_percentage:
            # Route to new executor
            return await self.new_executor.execute({"user_input": goal})
        else:
            # Route to old executor
            return await self.old_executor.execute(goal, **kwargs)
```

---

## 6. Performance Targets

| Operation | Target Latency | Current Latency | Improvement |
|-----------|----------------|-----------------|-------------|
| Single tool query | <1.5s | 2.5s | 40% |
| Multi-tool query (3) | <2.0s | 7.5s | 73% |
| Memory retrieval | <0.5s | 0.8s | 37% |
| Response generation | <1.0s | 1.5s | 33% |
| End-to-end | <2.5s | 4.5s | 44% |

---

## 7. Testing Strategy

### 7.1 Unit Tests (per node)

```python
# tests/langgraph/test_nodes.py
import pytest
from langgraph.nodes.audio_input import audio_input_node
from langgraph.types.state import AgentStateSchema

@pytest.mark.asyncio
async def test_audio_input_node_with_text():
    state = {
        "user_input": "Hello",
        "agent_state": "listening"
    }
    result = await audio_input_node(state)
    assert result["agent_state"] == "thinking"

@pytest.mark.asyncio
async def test_audio_input_node_with_audio():
    state = {
        "audio_bytes": b"test audio",
        "agent_state": "listening"
    }
    result = await audio_input_node(state)
    assert result["agent_state"] == "listening"
```

### 7.2 Integration Tests

| Test | Description | Pass Criteria |
|------|-------------|---------------|
| `test_end_to_end_flow` | Full workflow execution | <5s completion |
| `test_parallel_tools` | Multiple tool execution | All tools run concurrently |
| `test_error_recovery` | Auto-recovery from failure | Success on retry |
| `test_state_persistence` | Checkpointer works | State restored after restart |

---

## 8. Rollback Plan

If issues are detected, the following rollback actions are available:

1. **Disable LangGraph routing** in `main.py` (30s)
2. **Remove checkpointer** (10s)
3. **Delete `langgraph/`** directory (5s)

---

## 9. Deployment Checklist

- [ ] All unit tests passing (>80% coverage)
- [ ] All integration tests passing
- [ ] Performance benchmarks met
- [ ] Error recovery tested
- [ ] Checkpointer tested
- [ ] Documentation complete
- [ ] Rollback tested
- [ ] Monitoring configured

---

## 10. Success Criteria

| Criterion | Target | Measurement |
|-----------|--------|-------------|
| System uptime during migration | 99.9% | Uptime monitoring |
| Response time improvement | >40% | APM comparison |
| Error rate reduction | >50% | Error tracking |
| User satisfaction | >4.5/5 | Survey results |

---

*This blueprint is the authoritative source for the LangGraph migration. All implementations must follow this design.*
