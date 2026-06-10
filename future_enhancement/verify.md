# Verification & Validation - LangGraph Migration

**Version:** 1.0  
**Last Updated:** 2026-06-10  
**Status:** Ready for Testing

---

## Overview

This document defines the verification criteria, test suites, and validation methods for the LangGraph migration.

---

## Verification Approach

| Phase | Method | Tools | Owner |
|-------|--------|-------|-------|
| 1. Code Review | Manual inspection | GitHub PR reviews | Architect |
| 2. Unit Tests | Automated testing | pytest | QA Team |
| 3. Integration Tests | End-to-end scenarios | pytest | QA Team |
| 4. Performance Tests | Load & stress | Locust | DevOps |
| 5. User Acceptance | Manual validation | Test cases | Product Owner |
| 6. Production Smoke | Real-world traffic | Observability | SRE |

---

## Phase 0 Verification

### Code Review Checklist

| Check | Method | Pass Criteria |
|-------|--------|---------------|
| TypedDict structure | Review state.py | All fields documented |
| Node function signatures | Review nodes/*.py | Consistent typing |
| Edge routing logic | Review edges.py | All transitions covered |
| Graph construction | Review graph.py | No cycles detected |
| Import paths | Review __init__.py | No circular deps |

### Test Cases

| Test ID | Description | Pass Criteria | File |
|---------|-------------|---------------|------|
| V0-TC1 | State schema validation | All fields optional | test_state.py |
| V0-TC2 | Intent enum completeness | All intents defined | test_state.py |
| V0-TC3 | Graph instantiation | No errors on import | test_graph.py |
| V0-TC4 | Node registration | All nodes registered | test_graph.py |
| V0-TC5 | Edge routing | Correct transitions | test_edges.py |

### Acceptance Criteria

| Criterion | Status |
|-----------|--------|
| All code reviewed | [ ] |
| All unit tests passing | [ ] |
| Type checking passes | [ ] |
| No linting errors | [ ] |
| Documentation complete | [ ] |

---

## Phase 1 Verification

### Test Scenarios

| Scenario | Input | Expected Output | Test Type |
|----------|-------|-----------------|-----------|
| S1-TC1 | User: "What's the weather?" | Intent: INFO_REQUEST | Integration |
| S1-TC2 | User: "Open Chrome" | Intent: TASK_DELEGATION | Integration |
| S1-TC3 | User: "Check my files" | Intent: FILE_OPERATION | Integration |
| S1-TC4 | RAG retrieval | Context + memory returned | Integration |
| S1-TC5 | LLM generation | Response with context | Integration |

### Validation Methods

```python
# tests/langgraph/test_phase1_integration.py
import pytest
from langgraph.nodes.rag_retrieval import rag_retrieval_node
from langgraph.nodes.llm_generate import llm_generate_node

@pytest.mark.asyncio
async def test_rag_retrieval_comprehensive():
    """Test full RAG retrieval with various queries."""
    test_cases = [
        ("What is Python?", True),
        ("Hello", True),
        ("Tell me a joke", True),
    ]
    
    for query, should_return_facts in test_cases:
        state = {"user_input": query}
        result = await rag_retrieval_node(state)
        
        assert "context" in result
        assert "memory_facts" in result

@pytest.mark.asyncio
async def test_llm_generation():
    """Test LLM response generation."""
    state = {
        "user_input": "What is Python?",
        "context": [],
        "memory_facts": []
    }
    
    result = await llm_generate_node(state)
    assert "agent_response" in result
    assert len(result["agent_response"]) > 0
```

---

## Phase 2 Verification

### Tool Wrapper Validation

Each of the 17 action modules must have:

| Requirement | Validation Method |
|-------------|-------------------|
| Wrapper exists | File exists in `langgraph/agents/tools/` |
| Correct signature | `(state: dict) -> dict` |
| Error handling | Try/except with logging |
| Type hints | All parameters typed |

### Parallel Execution Test

```python
# tests/langgraph/test_parallel_execution.py
import asyncio
import time
from langgraph.nodes.parallel_tool_executor import parallel_tool_executor_node

@pytest.mark.asyncio
async def test_parallel_vs_sequential():
    """Compare parallel vs sequential execution time."""
    tools = [
        {"name": "weather_report", "params": {"city": "New York"}},
        {"name": "weather_report", "params": {"city": "London"}},
        {"name": "weather_report", "params": {"city": "Tokyo"}},
    ]
    
    # Sequential execution
    start_seq = time.time()
    for tool in tools:
        await asyncio.to_thread(  # Simulate execution
            lambda: time.sleep(0.5)
        )
    time_seq = time.time() - start_seq
    
    # Parallel execution (simulated)
    start_parallel = time.time()
    await asyncio.gather(*[
        asyncio.to_thread(lambda: time.sleep(0.5)) for _ in tools
    ])
    time_parallel = time.time() - start_parallel
    
    # Parallel should be faster
    assert time_parallel < time_seq * 0.8
```

---

## Phase 3 Verification

### Checkpointer Tests

| Test | Description | Pass Criteria |
|------|-------------|---------------|
| V3-TC1 | State persistence | Data written to checkpoint |
| V3-TC2 | State restoration | Data read correctly |
| V3-TC3 | Goal tracking | Goal persisted across turns |
| V3-TC4 | Error history | Errors stored in checkpoint |

```python
# tests/langgraph/test_checkpointer.py
import pytest
from langgraph.checkpoint import MemorySaver
from langgraph.types.state import AgentStateSchema

@pytest.mark.asyncio
async def test_checkpointer_persistence():
    """Test that state is persisted and can be restored."""
    checkpointer = MemorySaver()
    
    # Save state
    state = {
        "user_input": "Hello",
        "agent_response": "Hi there!",
        "current_goal": "Greeting",
    }
    await checkpointer.aput(
        thread_id="test",
        checkpoint={"v": 1, "ts": 1234567890, "data": state}
    )
    
    # Load state
    loaded = await checkpointer.aget(thread_id="test")
    assert loaded["data"]["user_input"] == "Hello"
```

### State Restoration Test

```python
# tests/langgraph/test_state_restoration.py
@pytest.mark.asyncio
async def test_goal_continuation():
    """Test that goals persist across conversation turns."""
    # Turn 1
    state_v1 = {
        "user_input": "Help me with Python",
        "current_goal": "Learn Python",
        "turn_count": 1,
    }
    
    # Save state
    checkpointer = MemorySaver()
    await checkpointer.aput(thread_id="user1", checkpoint={"v": 1, "data": state_v1})
    
    # Turn 2 (user continues)
    state_v2 = {
        "user_input": "Also JavaScript",
        "previous_goal": "Learn Python",
        "current_goal": "Learn Python and JavaScript",
        "turn_count": 2,
    }
    
    # Load and update
    loaded = await checkpointer.aget(thread_id="user1")
    loaded["data"].update(state_v2)
    await checkpointer.aput(thread_id="user1", checkpoint={"v": 2, "data": loaded["data"]})
    
    # Verify
    final = await checkpointer.aget(thread_id="user1")
    assert final["data"]["current_goal"] == "Learn Python and JavaScript"
```

---

## Phase 4 Verification

### Error Recovery Tests

| Test | Scenario | Expected Behavior |
|------|----------|-------------------|
| V4-TC1 | Network timeout | Retry with backoff |
| V4-TC2 | Permission error | Alternative approach proposed |
| V4-TC3 | Max retries reached | Report to user |
| V4-TC4 | LLM error | Fallback to web search |

```python
# tests/langgraph/test_error_recovery.py
import pytest
from langgraph.nodes.error_recovery import error_recovery_node

@pytest.mark.asyncio
async def test_error_recovery_timeout():
    """Test error recovery for timeout errors."""
    state = {
        "error_history": [
            {"node": "web_search", "error": "Connection timeout"}
        ],
        "turn_count": 1
    }
    
    result = error_recovery_node(state)
    assert result["next_action"] == "retry_with_backoff"

@pytest.mark.asyncio
async def test_error_recovery_max_retries():
    """Test error recovery when max retries exceeded."""
    state = {
        "error_history": [
            {"node": "web_search", "error": "Connection timeout"},
            {"node": "web_search", "error": "Connection timeout"},
            {"node": "web_search", "error": "Connection timeout"},
        ],
        "turn_count": 3
    }
    
    result = error_recovery_node(state)
    assert result["next_action"] == "report_to_user"
```

### Auto-Replan Tests

```python
# tests/langgraph/test_auto_replan.py
import pytest
from langgraph.nodes.auto_replan import auto_replan_node

@pytest.mark.asyncio
async def test_auto_replan_fresh_approach():
    """Test auto-replan with fresh approach."""
    state = {
        "failed_steps": [{"tool": "open_app", "params": {"app_name": "Chrome"}}],
        "error_history": [{"error": "App not found"}]
    }
    
    result = await auto_replan_node(state)
    assert "plan" in result
    assert result["plan"]["steps"] != state["failed_steps"]
```

---

## Phase 5 Verification

### Audio Integration Tests

| Test | Description | Pass Criteria |
|------|-------------|---------------|
| V5-TC1 | Audio input capture | Bytes stored in state |
| V5-TC2 | Text input capture | Text extracted from queue |
| V5-TC3 | Audio output queue | Speech queued correctly |
| V5-TC4 | Interrupt detection | Interrupt flag set |
| V5-TC5 | Resume after interrupt | Conversation resumes |

```python
# tests/langgraph/test_audio_integration.py
import pytest
from langgraph.nodes.audio_input import audio_input_node
from langgraph.nodes.audio_output import audio_output_node

@pytest.mark.asyncio
async def test_audio_to_text_conversion():
    """Test audio input processing."""
    state = {
        "audio_bytes": b"test audio data",
        "audio_in_queue": {"data": b"audio", "text": "Hello"}
    }
    
    result = await audio_input_node(state)
    assert result.get("user_input") == "Hello"

@pytest.mark.asyncio
async def test_audio_output_queue():
    """Test audio output queuing."""
    class MockQueue:
        def __init__(self):
            self.items = []
        def put_nowait(self, item):
            self.items.append(item)
    
    queue = MockQueue()
    state = {
        "agent_response": "Hello, sir.",
        "audio_out_queue": queue
    }
    
    result = audio_output_node(state)
    assert len(queue.items) == 1
    assert queue.items[0]["text"] == "Hello, sir."
```

---

## Phase 6 Verification

### End-to-End Test Suite

| Test | Description | Scenario | Pass Criteria |
|------|-------------|----------|---------------|
| V6-TC1 | Full conversational flow | User greeting | Complete response |
| V6-TC2 | Multi-tool query | "Check weather and open Chrome" | Both tools execute |
| V6-TC3 | Error recovery | Network failure | Auto-retry succeeds |
| V6-TC4 | Context preservation | Multi-turn goal | Goal tracked |
| V6-TC5 | Memory persistence | User facts | Stored in DB |

### Integration Test Matrix

| Input | Expected Output | Node Flow |
|-------|-----------------|-----------|
| "Hello" | "Hello, sir!" | audio → intent → rag → llm → audio |
| "What's the weather?" | Weather report | audio → intent → rag → llm → router → tool → audio |
| "Open Chrome" | Chrome opened | audio → intent → rag → llm → router → tool |
| "Search for Python" | Results page | audio → intent → rag → llm → router → tool → audio |

### Regression Test Suite

| Feature | Test Case | Pass/Fail |
|---------|-----------|-----------|
| Web search | Query with results | [ ] |
| Weather | City query | [ ] |
| File operations | File access | [ ] |
| Message sending | SMS/MMS | [ ] |
| Reminders | Timer setup | [ ] |
| Screen capture | Image analysis | [ ] |
| YouTube | Video play | [ ] |
| Open app | App launch | [ ] |

---

## Performance Validation

### Load Test Scenarios

| Load Level | Concurrent Users | Target Response | Pass Criteria |
|------------|------------------|-----------------|---------------|
| Baseline | 1 | <2s | [ ] |
| Normal | 5 | <2.5s | [ ] |
| Peak | 20 | <3s | [ ] |
| Spike | 50 | <4s | [ ] |

### Benchmark Suite

| Operation | Target | Max Allowable |
|-----------|--------|---------------|
| Audio input latency | <100ms | 200ms |
| Intent classification | <50ms | 100ms |
| RAG retrieval | <200ms | 500ms |
| LLM generation | <800ms | 1500ms |
| Tool execution | <500ms | 1000ms |
| End-to-end (single) | <2s | 3s |
| End-to-end (3 tools) | <2.5s | 4s |

### Stress Test Cases

| Test | Duration | Concurrency | Success Criteria |
|------|----------|-------------|------------------|
| S-T1 | 10 min | 100 | <1% error rate |
| S-T2 | 1 hour | 10 | <0.1% error rate |
| S-T3 | 24 hours | 5 | No memory leaks |

---

## Security & Safety Validation

| Check | Test | Pass Criteria |
|-------|------|---------------|
| API key exposure | Code scan | No keys in logs |
| Input sanitization | Malformed input | Graceful error |
| Rate limiting | High volume | Throttling applied |
| Error disclosure | Error response | No stack traces |
| Authentication | Auth bypass | 401 returned |

---

## Documentation Validation

| Artifact | Location | Status |
|----------|----------|--------|
| API docs | docs/langgraph/ | [ ] |
| Node specs | docs/nodes/ | [ ] |
| State schema | docs/state.md | [ ] |
| Architecture | docs/arch.md | [ ] |
| Migration guide | docs/migration.md | [ ] |

---

## Rollback Validation

| Rollback Action | Time Estimate | Verification |
|-----------------|---------------|--------------|
| Disable routing | <1 min | Test execution path |
| Remove checkpointer | <1 min | No checkpoint files |
| Restore backup | <5 min | All features working |

---

## Sign-off Checklist

### Development Phase
- [ ] All unit tests passing (95%+ coverage)
- [ ] All integration tests passing
- [ ] Performance benchmarks met
- [ ] Security review complete
- [ ] Documentation complete

### QA Phase
- [ ] Smoke tests passing
- [ ] Regression tests passing
- [ ] Load tests passing
- [ ] Error recovery tested

### Operations Phase
- [ ] Monitoring configured
- [ ] Alerting configured
- [ ] Rollback tested
- [ ] Runbook complete

### Product Phase
- [ ] User acceptance testing
- [ ] UX review complete
- [ ] Performance approval
- [ ] Documentation approval

---

## Approval Signatures

| Role | Name | Date | Signature |
|------|------|------|-----------|
| QA Lead | | | |
| DevOps Lead | | | |
| Product Owner | | | |
| Architect | | | |
| Security Reviewer | | | |

---

## Known Issues & Exceptions

| Issue ID | Description | Status | Workaround |
|----------|-------------|--------|------------|
| None | - | - | - |

---

## Revision History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-06-10 | Initial version | Architect |

---

*This validation document is the authoritative source for testing the LangGraph migration.*
