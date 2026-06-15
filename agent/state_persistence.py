"""
╔══════════════════════════════════════════════════════════════════════════════════╗
║       JARVIS MARK XXXIX — Phase 5: State Persistence Architecture              ║
║       Module : agent/state_persistence.py                                      ║
║                                                                                 ║
║  Architecture : MemorySaver + ChromaDB Integration                             ║
║  Purpose      : Persistent state across LangGraph executions                   ║
║  Features     : Cross-run memory, conversation history, agent state restore    ║
║  Integration  : Extends agent/tool_nodes.py architecture                       ║
╚══════════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict
from threading import Lock

# ── LangGraph Imports ─────────────────────────────────────────────────────────────
try:
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
    # BaseCheckpointSaver is not available in newer LangGraph versions
    # We use MemorySaver directly which implements the interface
    BaseCheckpointSaver = None
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    BaseCheckpointSaver = None
    MemorySaver = None
    JsonPlusSerializer = None

# ── ChromaDB Imports ──────────────────────────────────────────────────────────────
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    chromadb = None
    Settings = None

# ── Local Imports ─────────────────────────────────────────────────────────────────
try:
    import memory.memory_manager as memory_module
    MEMORY_MODULE_AVAILABLE = True
except ImportError:
    memory_module = None
    MEMORY_MODULE_AVAILABLE = False

# ── Agent Imports ─────────────────────────────────────────────────────────────────
try:
    from agent.tool_nodes import AgentState, create_all_tool_nodes, CrewEngineConfig
    TOOL_NODES_AVAILABLE = True
except ImportError:
    TOOL_NODES_AVAILABLE = False


# ════════════════════════════════════════════════════════════════════════════════
#  §1  STATE PERSISTENCE CONFIGURATION
# ════════════════════════════════════════════════════════════════════════════════

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = _get_base_dir()
MEMORY_DIR = BASE_DIR / "jarvis_memory"
PERSISTENT_STATE_DIR = MEMORY_DIR / "state_persistence"
STATE_CHECKPOINTS_DIR = PERSISTENT_STATE_DIR / "checkpoints"
AGENT_MEMORIES_DIR = PERSISTENT_STATE_DIR / "agent_memories"

# Ensure directories exist
for _dir in [PERSISTENT_STATE_DIR, STATE_CHECKPOINTS_DIR, AGENT_MEMORIES_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)


# ════════════════════════════════════════════════════════════════════════════════
#  §2  STATE PERSISTENCE MANAGER
# ════════════════════════════════════════════════════════════════════════════════

class StatePersistenceManager:
    """
    Manages persistent state for LangGraph agents across runs.
    Integrates with MemorySaver for checkpoint persistence and ChromaDB for
    long-term memory storage.
    """

    def __init__(
        self,
        memory_dir: Path = PERSISTENT_STATE_DIR,
        checkpoint_dir: Path = STATE_CHECKPOINTS_DIR,
        agent_memory_dir: Path = AGENT_MEMORIES_DIR,
        checkpoint_saver: Optional[BaseCheckpointSaver] = None,
    ):
        self.memory_dir = memory_dir
        self.checkpoint_dir = checkpoint_dir
        self.agent_memory_dir = agent_memory_dir

        # Ensure directories exist
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.agent_memory_dir.mkdir(parents=True, exist_ok=True)

        # Initialize checkpoint saver
        self.checkpoint_saver = checkpoint_saver or self._create_checkpoint_saver()

        # Initialize ChromaDB collection for agent memories
        self.chroma_client = None
        self.agent_memory_collection = None
        if CHROMADB_AVAILABLE:
            self._init_chroma_collection()

        # Conversation history
        self.conversation_history: List[Dict[str, Any]] = []

        # Lock for thread safety
        self._lock = Lock()

    def _create_checkpoint_saver(self):
        """Create a MemorySaver checkpoint saver for state persistence."""
        if not LANGGRAPH_AVAILABLE:
            raise RuntimeError("LangGraph not available. Install with: pip install langgraph")

        # Use MemorySaver with optional checkpoint_id for persistence
        # MemorySaver() creates in-memory checkpoint storage
        return MemorySaver()

    def _init_chroma_collection(self) -> None:
        """Initialize ChromaDB collection for agent memories."""
        if not CHROMADB_AVAILABLE:
            return

        try:
            # Use PersistentClient for disk-based storage
            self.chroma_client = chromadb.PersistentClient(
                path=str(self.agent_memory_dir)
            )

            self.agent_memory_collection = self.chroma_client.get_or_create_collection(
                name="agent_memories",
                metadata={"hnsw:space": "cosine"}
            )
            print(f"[StatePersistence] [OK] ChromaDB collection initialized: agent_memories")
        except Exception as exc:
            print(f"[StatePersistence] [WARN] Failed to initialize ChromaDB: {exc}")

    def save_checkpoint(
        self,
        checkpoint_id: str,
        state: AgentState,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Save a state checkpoint to disk.

        Args:
            checkpoint_id: Unique identifier for this checkpoint
            state: The AgentState to save
            metadata: Optional metadata to store with checkpoint

        Returns:
            Path to the saved checkpoint file
        """
        checkpoint_data = {
            "checkpoint_id": checkpoint_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "state": state,
            "metadata": metadata or {}
        }

        checkpoint_path = self.checkpoint_dir / f"{checkpoint_id}.json"
        try:
            with open(checkpoint_path, "w", encoding="utf-8") as f:
                json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)
            print(f"[StatePersistence] [OK] Checkpoint saved: {checkpoint_id}")
            return str(checkpoint_path)
        except Exception as exc:
            print(f"[StatePersistence] [WARN] Failed to save checkpoint: {exc}")
            return ""

    def load_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """
        Load a state checkpoint from disk.

        Args:
            checkpoint_id: The checkpoint identifier to load

        Returns:
            Checkpoint data dictionary or None if not found
        """
        checkpoint_path = self.checkpoint_dir / f"{checkpoint_id}.json"
        try:
            with open(checkpoint_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"[StatePersistence] ⚠️ [WARN] Checkpoint not found: {checkpoint_id}")
            return None
        except Exception as exc:
            print(f"[StatePersistence] ⚠️ [WARN] Failed to load checkpoint: {exc}")
            return None

    def list_checkpoints(self) -> List[str]:
        """List all available checkpoint IDs."""
        try:
            checkpoints = []
            for f in self.checkpoint_dir.glob("*.json"):
                checkpoints.append(f.stem)
            return sorted(checkpoints)
        except Exception as exc:
            print(f"[StatePersistence] ⚠️ [WARN] Failed to list checkpoints: {exc}")
            return []

    def save_agent_memory(
        self,
        agent_id: str,
        memory_type: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Save an agent memory fact to ChromaDB.

        Args:
            agent_id: ID of the agent this memory belongs to
            memory_type: Type/category of memory (e.g., "goal_tracking", "tool_usage")
            content: The memory content
            metadata: Optional metadata

        Returns:
            Memory ID or empty string on failure
        """
        if not CHROMADB_AVAILABLE or not self.agent_memory_collection:
            return ""

        memory_id = str(uuid.uuid4())

        try:
            self.agent_memory_collection.add(
                documents=[content],
                metadatas=[
                    {
                        "agent_id": agent_id,
                        "memory_type": memory_type,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        **(metadata or {})
                    }
                ],
                ids=[memory_id]
            )
            print(f"[StatePersistence] [OK] Agent memory saved: {memory_id[:8]}")
            return memory_id
        except Exception as exc:
            print(f"[StatePersistence] ⚠️ [WARN] Failed to save agent memory: {exc}")
            return ""

    def recall_agent_memories(
        self,
        agent_id: str,
        memory_type: Optional[str] = None,
        query: Optional[str] = None,
        n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Recall agent memories from ChromaDB.

        Args:
            agent_id: ID of the agent
            memory_type: Optional filter by memory type
            query: Optional query for semantic search
            n_results: Number of results to return

        Returns:
            List of matching memory entries
        """
        if not CHROMADB_AVAILABLE or not self.agent_memory_collection:
            return []

        try:
            if query:
                # Use ChromaDB's built-in embedder for semantic search
                # This ensures embedding dimensions match the collection's expectations
                results = self.agent_memory_collection.query(
                    query_texts=[query],
                    n_results=n_results,
                    where={"agent_id": agent_id},
                    include=["documents", "metadatas", "distances"]
                )
            else:
                # Filter by agent and memory type
                where = {"agent_id": agent_id}
                if memory_type:
                    where["memory_type"] = memory_type

                results = self.agent_memory_collection.get(
                    where=where,
                    limit=n_results,
                    include=["documents", "metadatas"]
                )

            # Parse results
            memories = []
            docs = results.get("documents", [[]])[0] if results.get("documents") else []
            metadatas = results.get("metadatas", [[]])[0] if results.get("metadatas") else []

            for doc, meta in zip(docs, metadatas):
                memories.append({
                    "content": doc,
                    "metadata": meta or {}
                })

            return memories
        except Exception as exc:
            print(f"[StatePersistence] [WARN] Failed to recall memories: {exc}")
            return []

    def add_conversation_turn(
        self,
        user_id: str,
        user_message: str,
        agent_message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add a conversation turn to persistent history.

        Args:
            user_id: Unique user identifier
            user_message: User's message
            agent_message: Agent's response
            context: Optional execution context
        """
        turn = {
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_message": user_message,
            "agent_message": agent_message,
            "context": context or {}
        }

        with self._lock:
            self.conversation_history.append(turn)

            # Trim history to last 100 turns
            if len(self.conversation_history) > 100:
                self.conversation_history = self.conversation_history[-100:]

    def get_conversation_history(
        self,
        user_id: str,
        n_turns: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get conversation history for a user.

        Args:
            user_id: User identifier
            n_turns: Number of turns to retrieve

        Returns:
            List of conversation turns (most recent first)
        """
        with self._lock:
            history = [
                t for t in self.conversation_history
                if t.get("user_id") == user_id
            ]
            return history[-n_turns:]

    def save_conversation_history(self, user_id: str) -> bool:
        """
        Save conversation history to disk.

        Args:
            user_id: User identifier

        Returns:
            True if successful, False otherwise
        """
        history = self.get_conversation_history(user_id)

        history_file = self.agent_memory_dir / f"{user_id}_conversation.json"
        try:
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
            return True
        except Exception as exc:
            print(f"[StatePersistence] ⚠️ [WARN] Failed to save conversation history: {exc}")
            return False

    def load_conversation_history(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Load conversation history from disk.

        Args:
            user_id: User identifier

        Returns:
            List of conversation turns
        """
        history_file = self.agent_memory_dir / f"{user_id}_conversation.json"
        try:
            if history_file.exists():
                with open(history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as exc:
            print(f"[StatePersistence] ⚠️ [WARN] Failed to load conversation history: {exc}")

        return []


# ════════════════════════════════════════════════════════════════════════════════
#  §3  LANGGRAPH CHECKPOINTER — MemorySaver Wrapper
# ════════════════════════════════════════════════════════════════════════════════

class LangGraphCheckpointer:
    """
    Wrapper around MemorySaver for LangGraph state persistence.
    Integrates with StatePersistenceManager for enhanced capabilities.
    """

    def __init__(
        self,
        manager: StatePersistenceManager,
        checkpoint_id: Optional[str] = None
    ):
        self.manager = manager
        self.checkpoint_id = checkpoint_id or str(uuid.uuid4())[:8]
        self._saver = manager.checkpoint_saver

    def get(self, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get checkpoint state by config."""
        if self._saver and hasattr(self._saver, "get"):
            return self._saver.get(config)
        return None

    def put(
        self,
        config: Dict[str, Any],
        checkpoint: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Save checkpoint state."""
        if self._saver and hasattr(self._saver, "put"):
            result = self._saver.put(config, checkpoint, metadata)
        else:
            # Fallback to manual save
            self.manager.save_checkpoint(self.checkpoint_id, checkpoint, metadata)
            result = {"checkpoint_id": self.checkpoint_id}

        return result

    def list(
        self,
        config: Dict[str, Any],
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """List checkpoints."""
        if self._saver and hasattr(self._saver, "list"):
            return self._saver.list(config, limit=limit)
        return []

    def get_checkpoint_id(self) -> str:
        """Get the current checkpoint ID."""
        return self.checkpoint_id

    def set_checkpoint_id(self, checkpoint_id: str) -> None:
        """Set a new checkpoint ID."""
        self.checkpoint_id = checkpoint_id


# ════════════════════════════════════════════════════════════════════════════════
#  §4  ENHANCED TOOL NODES ARCHITECTURE
# ════════════════════════════════════════════════════════════════════════════════

class EnhancedToolNodesArchitecture:
    """
    Extended ToolNodesArchitecture with state persistence capabilities.
    Integrates MemorySaver checkpointing and ChromaDB memory storage.
    """

    def __init__(
        self,
        config: Optional[CrewEngineConfig] = None,
        enable_memory: bool = True,
        enable_parallel: bool = True,
        enable_persistence: bool = True,
        checkpoint_id: Optional[str] = None,
    ):
        if not TOOL_NODES_AVAILABLE:
            raise RuntimeError(
                "Tool Nodes not available. Run: pip install langgraph langchain-core"
            )

        self.config = config
        self.enable_memory = enable_memory
        self.enable_parallel = enable_parallel
        self.enable_persistence = enable_persistence
        self.checkpoint_id = checkpoint_id or str(uuid.uuid4())[:8]

        # Initialize persistence manager
        self.persistence_manager = StatePersistenceManager()

        # Create tool nodes
        self._tool_nodes = create_all_tool_nodes(config)

        # Initialize checkpointer
        self.checkpointer = LangGraphCheckpointer(
            self.persistence_manager,
            self.checkpoint_id
        )

        # Build state graph with checkpointing
        self._graph = self._build_graph()

    def _build_graph(self) -> Any:
        """Build the LangGraph StateGraph with persistence."""
        if not LANGGRAPH_AVAILABLE:
            raise RuntimeError(
                "LangGraph not available. Run: pip install langgraph langchain-core"
            )

        from langgraph.graph import StateGraph
        from agent.tool_nodes import (
            AgentState,
            planning_node,
            executor_node,
            self_correction_node,
            memory_update_node,
            router_node,
            END
        )

        workflow = StateGraph(AgentState)

        # Define nodes
        workflow.add_node("planning", planning_node)
        workflow.add_node("executor", executor_node)
        workflow.add_node("self_correction", self_correction_node)
        workflow.add_node("memory_update", memory_update_node)

        # Define edges
        workflow.add_edge("planning", "executor")
        workflow.add_edge("executor", "self_correction")
        workflow.add_edge("self_correction", "planning")  # Loop on error
        workflow.add_edge("self_correction", "memory_update")
        workflow.add_edge("memory_update", END)

        # Set entry point
        workflow.set_entry_point("planning")

        # Compile with checkpointing
        if self.enable_persistence and self.checkpointer:
            return workflow.compile(
                checkpointer=self.checkpointer._saver if hasattr(self.checkpointer, "_saver") else None
            )

        return workflow.compile()

    def execute(
        self,
        goal: str,
        context: str = "",
        max_steps: int = 10,
        checkpoint_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a goal with state persistence.

        Args:
            goal: Natural language user goal
            context: Additional context for tool selection
            max_steps: Maximum planning iterations
            checkpoint_id: Optional checkpoint ID for resuming

        Returns:
            Execution result dictionary
        """
        import time

        start_time = time.perf_counter()

        # Initialize state
        state = {
            "goal": goal,
            "context": context,
            "max_steps": max_steps,
            "current_step": 0,
            "plan": {},
            "tool_inputs": [],
            "tool_results": {},
            "errors": [],
            "steps_executed": [],
            "tools_used": [],
            "_tool_nodes": self._tool_nodes,
        }

        # Load checkpoint if provided
        if checkpoint_id and self.enable_persistence:
            saved_state = self.persistence_manager.load_checkpoint(checkpoint_id)
            if saved_state:
                state = saved_state.get("state", state)

        try:
            # Run the graph
            result = self._graph.invoke(state)

            execution_time = time.perf_counter() - start_time

            # Save checkpoint if enabled
            if self.enable_persistence:
                self.persistence_manager.save_checkpoint(
                    self.checkpoint_id,
                    result,
                    {
                        "goal": goal,
                        "execution_time_seconds": execution_time
                    }
                )

            # Build result
            return {
                "success": result.get("success", False),
                "final_result": result.get("final_result", "Unknown"),
                "steps_executed": result.get("steps_executed", []),
                "tools_used": result.get("tools_used", []),
                "execution_time_seconds": execution_time,
                "error": result.get("error"),
                "checkpoint_id": self.checkpoint_id,
                "plan_history": [result.get("plan", {})],
            }

        except Exception as e:
            execution_time = time.perf_counter() - start_time
            print(f"[EnhancedToolNodes] [ERROR] Execution failed: {e}")

            return {
                "success": False,
                "final_result": f"Execution failed: {e}",
                "steps_executed": [],
                "tools_used": [],
                "execution_time_seconds": execution_time,
                "error": str(e),
                "checkpoint_id": self.checkpoint_id,
                "plan_history": [],
            }

    def resume_execution(self, checkpoint_id: str) -> Dict[str, Any]:
        """
        Resume execution from a saved checkpoint.

        Args:
            checkpoint_id: The checkpoint ID to resume from

        Returns:
            Execution result dictionary
        """
        self.checkpoint_id = checkpoint_id
        saved_state = self.persistence_manager.load_checkpoint(checkpoint_id)

        if not saved_state:
            return {
                "success": False,
                "final_result": f"[WARN] Checkpoint not found: {checkpoint_id}",
                "error": "Checkpoint not found"
            }

        # Reinitialize state with loaded data
        state = saved_state.get("state", {})

        try:
            result = self._graph.invoke(state)
            execution_time = time.perf_counter() - saved_state.get("metadata", {}).get("execution_time_seconds", 0)

            return {
                "success": result.get("success", False),
                "final_result": result.get("final_result", "Unknown"),
                "steps_executed": result.get("steps_executed", []),
                "tools_used": result.get("tools_used", []),
                "execution_time_seconds": execution_time,
                "error": result.get("error"),
                "checkpoint_id": checkpoint_id,
                "plan_history": [result.get("plan", {})],
            }

        except Exception as e:
            return {
                "success": False,
                "final_result": f"Resume failed: {e}",
                "error": str(e),
                "checkpoint_id": checkpoint_id,
            }


# ════════════════════════════════════════════════════════════════════════════════
#  §5  CONVENIENCE FACTORY
# ════════════════════════════════════════════════════════════════════════════════

def load_state_persistence_architecture(
    enable_memory: bool = True,
    enable_parallel: bool = True,
    enable_persistence: bool = True,
    checkpoint_id: Optional[str] = None,
) -> EnhancedToolNodesArchitecture:
    """
    Factory to create an EnhancedToolNodesArchitecture with state persistence.

    Auto-loads Gemini API key from api_keys.json or environment.

    Args:
        enable_memory: Whether to update ChromaDB memory
        enable_parallel: Enable parallel tool execution
        enable_persistence: Enable checkpoint persistence
        checkpoint_id: Optional checkpoint ID for resuming

    Returns:
        EnhancedToolNodesArchitecture ready for use
    """
    import os
    import json

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        api_keys_path = BASE_DIR / "config" / "api_keys.json"
        if api_keys_path.exists():
            try:
                data = json.loads(api_keys_path.read_text(encoding="utf-8"))
                api_key = data.get("gemini_api_key") or data.get("GEMINI_API_KEY") or ""
            except Exception:
                pass

    if not api_key:
        raise RuntimeError(
            "[StatePersistence] GEMINI_API_KEY not found in environment or config/api_keys.json."
        )

    from agent.crew_orchestration_engine import CrewEngineConfig

    config = CrewEngineConfig(
        gemini_api_key=api_key,
        model_name="gemini/gemini-2.5-flash",
        max_rpm=10,
        max_iter=5,
    )

    return EnhancedToolNodesArchitecture(
        config=config,
        enable_memory=enable_memory,
        enable_parallel=enable_parallel,
        enable_persistence=enable_persistence,
        checkpoint_id=checkpoint_id,
    )


# ════════════════════════════════════════════════════════════════════════════════
#  §6  STANDALONE ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="State Persistence Architecture Test")
    parser.add_argument("--goal", default="Search for current AI news and save to file")
    parser.add_argument("--checkpoint", action="store_true", help="Enable checkpointing")
    parser.add_argument("--resume", type=str, help="Checkpoint ID to resume from")

    args = parser.parse_args()

    print("=" * 80)
    print("  JARVIS State Persistence Architecture - Standalone Test")
    print("=" * 80)

    try:
        if args.resume:
            # Resume from checkpoint
            architecture = load_state_persistence_architecture(enable_persistence=True)
            result = architecture.resume_execution(args.resume)
        else:
            # Execute with persistence
            architecture = load_state_persistence_architecture(
                enable_memory=True,
                enable_parallel=True,
                enable_persistence=args.checkpoint,
            )

            result = architecture.execute(goal=args.goal, max_steps=10)

        print(f"\n[TEST] Goal: {args.goal}")
        print("-" * 40)
        print(f"\n[TEST] Result:")
        print(f"  Success: {result['success']}")
        print(f"  Execution time: {result['execution_time_seconds']:.2f}s")
        print(f"  Tools used: {result['tools_used']}")
        print(f"  Steps executed: {len(result['steps_executed'])}")
        print(f"  Final result: {result['final_result'][:200]}...")

        if result.get("checkpoint_id"):
            print(f"  Checkpoint ID: {result['checkpoint_id']}")

        if result.get("error"):
            print(f"  Error: {result['error']}")

    except ImportError as e:
        print(f"\n[ERROR] Required module not available: {e}")
        print("Run: pip install langgraph langchain-core chromadb")
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
