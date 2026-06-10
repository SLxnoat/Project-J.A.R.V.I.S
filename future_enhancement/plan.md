# LangGraph Migration Plan - JARVIS MARK XXXIX

**Version:** 1.0  
**Last Updated:** 2026-06-10  
**Status:** Planning Phase Complete

---

## Overview

This document outlines the comprehensive plan for migrating JARVIS from its current monolithic architecture to a LangGraph-driven Multi-Agent Agentic AI system.

---

## Migration Goals

| Priority | Goal | Success Criteria |
|----------|------|------------------|
| P0 | Maintain existing functionality | All current features work identically |
| P0 | Zero downtime migration | No service interruption during migration |
| P1 | Enable parallel tool execution | Multi-tool queries 4x faster |
| P1 | Implement autonomous self-correction | 60% reduction in user interruptions |
| P2 | Enable goal tracking | Multi-turn conversations maintain context |
| P2 | Context-aware interrupts | Natural conversation flow |
| P3 | Improve testability | 80%+ node-level test coverage |

---

## Phased Approach

### Phase 0: Foundation (Week 1)
**Objective:** Establish the LangGraph scaffolding

**Deliverables:**
- [ ] `langgraph/` directory structure created
- [ ] `types/state.py` with TypedDict schemas
- [ ] `graph.py` with basic workflow skeleton
- [ ] Integration test suite

**Risk:** Low  
**Breaking Changes:** None (parallel run)

---

### Phase 1: RAG Migration (Week 2)
**Objective:** Extract existing RAG into LangGraph nodes

**Deliverables:**
- [ ] `rag_retrieval_node` - wraps current RAG processor
- [ ] `llm_generate_node` - wraps current LLM generation
- [ ] `memory_update_node` - handles short-term memory

**Risk:** Medium  
**Breaking Changes:** None

---

### Phase 2: Tool Nodes (Week 3)
**Objective:** Create LangGraph-compatible tool wrappers

**Deliverables:**
- [ ] `tool_router_node` - routes to appropriate tools
- [ ] `parallel_tool_executor` - concurrent execution
- [ ] 17 action module wrappers as `langgraph/agents/tools/`

**Risk:** Medium  
**Breaking Changes:** Minor (import path changes)

---

### Phase 3: State Persistence (Week 4)
**Objective:** Add checkpointing for conversation memory

**Deliverables:**
- [ ] MemorySaver integration
- [ ] Goal tracking across turns
- [ ] Error history persistence

**Risk:** Medium  
**Breaking Changes:** Minor (state schema changes)

---

### Phase 4: Autonomous Features (Week 5)
**Objective:** Implement self-correction and parallel execution

**Deliverables:**
- [ ] `error_recovery_node` - autonomous error handling
- [ ] `auto_replan_node` - self-directed replanning
- [ ] Performance benchmarks

**Risk:** High  
**Breaking Changes:** Moderate

---

### Phase 5: Audio Integration (Week 6)
**Objective:** Replace current audio queue with LangGraph state

**Deliverables:**
- [ ] `audio_input_node` - microphone processing
- [ ] `audio_output_node` - speech generation
- [ ] Interrupt handling

**Risk:** High  
**Breaking Changes:** Yes (audio stream handling)

---

### Phase 6: Final Integration (Week 7)
**Objective:** Complete migration and retire old executor

**Deliverables:**
- [ ] `main.py` updated to use new executor
- [ ] `agent/executor.py` deprecated
- [ ] End-to-end testing
- [ ] Documentation

**Risk:** High  
**Breaking Changes:** High

---

## Technical Debt Reduction

| Current Issue | Migration Fix |
|--------------|---------------|
| `main.py` (942 lines) | Split into modular nodes (~200 lines each) |
| Hard-coded tool imports | Dynamic tool discovery |
| Sequential execution | Concurrent ToolNode |
| No state persistence | MemorySaver checkpointer |
| Circular dependencies | Clean separation of concerns |

---

## Rollback Strategy

| Phase | Rollback Method | Time Estimate |
|-------|-----------------|---------------|
| 0 | Delete `langgraph/` directory | < 1 min |
| 1 | Comment RAG routes | < 1 min |
| 2 | Disable tool routes | < 1 min |
| 3 | Disable checkpointer | < 1 min |
| 4 | Revert executor import | < 1 min |
| 5-6 | Restore old main.py backup | < 5 min |

---

## Success Metrics

| Metric | Baseline | Target | Measurement |
|--------|----------|--------|-------------|
| Response time (single tool) | 2.5s | 2.5s | APM monitoring |
| Response time (3 tools) | 7.5s | 2.0s | APM monitoring |
| User interruptions | 4.2/week | 1.5/week | Support logs |
| Node test coverage | 0% | 80% | pytest coverage |
| Code duplication | 35% | < 10% | SonarQube |

---

## Stakeholder Communication

| Audience | Update Frequency | Format |
|----------|------------------|--------|
| Development Team | Daily | Slack channel #jarvis-migration |
| Product Management | Weekly | Email summary |
| Users | Monthly | Release notes |

---

## Open Questions

1. Should we migrate the UI framework (PyQt6) or keep it separate?
2. What level of error recovery autonomy is appropriate?
3. Should we support multiple concurrent user sessions?

---

## Approval

| Role | Name | Date | Status |
|------|------|------|--------|
| Tech Lead | | | Pending |
| Project Owner | | | Pending |
| QA Lead | | | Pending |

---

## Appendix: Dependency Tree

```
langgraph/
├── types/
│   └── state.py (TypedDict)
├── nodes/
│   ├── audio_input.py
│   ├── intent_classifier.py
│   ├── rag_retrieval.py
│   ├── llm_generate.py
│   ├── tool_router.py
│   ├── parallel_executor.py
│   ├── memory_update.py
│   └── audio_output.py
├── agents/
│   ├── tools/
│   │   ├── open_app.py
│   │   ├── web_search.py
│   │   └── [15 more...]
│   ├── planner.py
│   ├── executor.py
│   └── memory.py
├── edges.py
├── graph.py
└── utils/
    ├── checkpointer.py
    ├── error_recovery.py
    └── metrics.py
```
