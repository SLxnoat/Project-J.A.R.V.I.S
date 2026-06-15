"""
╔══════════════════════════════════════════════════════════════════════════════════╗
║       JARVIS MARK XXXIX — Tool Nodes Architecture Tests                        ║
║       Module : tests/test_tool_nodes.py                                        ║
║                                                                                 ║
║  Purpose      : Unit and integration tests for LangGraph Tool Nodes            ║
║  Architecture : StateGraph-based tool execution                                ║
╚══════════════════════════════════════════════════════════════════════════════════╝
"""

import unittest
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, MagicMock as Mock
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# LangGraph availability check will be done at test runtime


# ════════════════════════════════════════════════════════════════════════════════
#  Test Setup & Fixtures
# ════════════════════════════════════════════════════════════════════════════════

def mock_api_keys():
    """Create mock api_keys.json for testing."""
    config_dir = Path(__file__).resolve().parent.parent / "config"
    config_dir.mkdir(exist_ok=True)
    api_keys_path = config_dir / "api_keys.json"

    if not api_keys_path.exists():
        import json
        api_keys_path.write_text(
            json.dumps({
                "gemini_api_key": "test-gemini-key-12345",
                "openrouter_api_key": "test-or-key-67890",
                "serper_api_key": "test-serper-key-abcde"
            }, indent=2),
            encoding="utf-8"
        )

    return api_keys_path


# ════════════════════════════════════════════════════════════════════════════════
#  Test Cases
# ════════════════════════════════════════════════════════════════════════════════

class TestToolNodeState(unittest.TestCase):
    """Test state schema definitions."""

    def test_agent_state_has_required_fields(self):
        """AgentState should have all required fields for tool execution."""
        from agent.tool_nodes import AgentState

        # Check required fields exist in the TypedDict
        state = AgentState()
        self.assertIsInstance(state, dict)

        # Verify fields can be set
        state["goal"] = "Test goal"
        state["tool_inputs"] = []
        state["tool_results"] = {}
        state["steps_executed"] = []
        state["errors"] = []
        state["success"] = False
        state["final_result"] = ""

        self.assertEqual(state["goal"], "Test goal")
        self.assertEqual(state["success"], False)

    def test_tool_node_input_schema(self):
        """ToolNodeInput should validate correct parameters."""
        from agent.tool_nodes import ToolNodeInput

        # Valid input
        input_obj = ToolNodeInput(
            goal="Open Chrome and search for news",
            context="User prefers news about technology",
            max_steps=5
        )

        self.assertEqual(input_obj.goal, "Open Chrome and search for news")
        self.assertEqual(input_obj.context, "User prefers news about technology")
        self.assertEqual(input_obj.max_steps, 5)

        # Default values work
        input_obj2 = ToolNodeInput(goal="Test goal")
        self.assertEqual(input_obj2.max_steps, 10)

    def test_tool_node_output_schema(self):
        """ToolNodeOutput should validate execution results."""
        from agent.tool_nodes import ToolNodeOutput

        # Valid output with all fields
        output = ToolNodeOutput(
            success=True,
            final_result="Task completed successfully",
            steps_executed=["step 1", "step 2"],
            tools_used=["web_search", "open_app"],
            execution_time_seconds=1.5
        )

        self.assertTrue(output.success)
        self.assertEqual(len(output.steps_executed), 2)
        self.assertEqual(len(output.tools_used), 2)

        # Output with errors
        output2 = ToolNodeOutput(
            success=False,
            final_result="Error occurred",
            error="Test error",
            execution_time_seconds=0.5
        )

        self.assertFalse(output2.success)
        self.assertEqual(output2.error, "Test error")


class TestPlanningNode(unittest.TestCase):
    """Test the planning node functionality."""

    def test_create_plan_from_goal_web_search(self):
        """Should create web_search plan for information queries."""
        from agent.tool_nodes import create_plan_from_goal

        goal = "What is the current Bitcoin price?"
        plan = create_plan_from_goal(goal, tools_available=["web_search"])

        self.assertIn("steps", plan)
        self.assertTrue(len(plan["steps"]) > 0)

        # Should select web_search for "current" + "price" query
        step_tools = [s.get("tool") for s in plan["steps"]]
        self.assertIn("web_search", step_tools)

    def test_create_plan_from_goal_open_app(self):
        """Should create open_app plan for application requests."""
        from agent.tool_nodes import create_plan_from_goal

        goal = "Open Chrome browser"
        plan = create_plan_from_goal(goal, tools_available=["open_app"])

        step_tools = [s.get("tool") for s in plan["steps"]]
        self.assertIn("open_app", step_tools)

    def test_create_plan_from_goal_weather(self):
        """Should create weather_report plan for weather queries."""
        from agent.tool_nodes import create_plan_from_goal

        goal = "What's the weather in New York?"
        plan = create_plan_from_goal(goal, tools_available=["weather_report"])

        step_tools = [s.get("tool") for s in plan["steps"]]
        self.assertIn("weather_report", step_tools)

    def test_planning_node_integration(self):
        """Planning node should correctly update state."""
        from agent.tool_nodes import planning_node, AgentState

        state = AgentState(
            goal="Open Spotify and play music",
            context="User likes rock music",
            max_steps=10
        )

        result = planning_node(state)

        self.assertIn("plan", result)
        self.assertIn("tool_inputs", result)
        self.assertEqual(result["current_step"], 0)


class TestExecutorNode(unittest.TestCase):
    """Test the executor node functionality."""

    def test_executor_node_no_steps(self):
        """Executor should handle empty plan gracefully."""
        from agent.tool_nodes import executor_node

        state = {
            "goal": "Test",
            "plan": {"steps": []},
            "current_step": 0,
            "tool_inputs": [],
            "tool_results": {},
            "errors": [],
            "steps_executed": [],
            "tools_used": []
        }

        result = executor_node(state)

        self.assertTrue(result["success"])
        self.assertIn("No steps to execute", result["final_result"])

    def test_executor_node_single_step(self):
        """Executor should handle single step execution."""
        from agent.tool_nodes import executor_node

        state = {
            "goal": "Test",
            "plan": {"steps": [
                {"step": 1, "tool": "web_search", "parameters": {"query": "test"}}
            ]},
            "current_step": 0,
            "tool_inputs": [],
            "tool_results": {},
            "errors": [],
            "steps_executed": [],
            "tools_used": []
        }

        result = executor_node(state)

        # Should have recorded the step
        self.assertGreater(len(result["steps_executed"]), 0)


class TestToolNodesArchitecture(unittest.TestCase):
    """Test the full ToolNodesArchitecture class."""

    def setUp(self):
        """Skip tests if LangGraph is not available."""
        import sys
        print("setUp: Checking LangGraph availability...", file=sys.stderr)
        try:
            from langgraph.graph import StateGraph
            self.langgraph_available = True
            print("setUp: LangGraph available", file=sys.stderr)
        except ImportError:
            self.langgraph_available = False
            print("setUp: LangGraph NOT available, skipping tests", file=sys.stderr)
            raise unittest.SkipTest("LangGraph not available")

    def test_creation_with_defaults(self):
        """Should create architecture with default configuration."""
        from agent.tool_nodes import ToolNodesArchitecture, CrewEngineConfig

        config = CrewEngineConfig(
            gemini_api_key="test-key",
            model_name="gemini/gemini-2.5-flash",
            max_rpm=10,
            max_iter=5
        )

        architecture = ToolNodesArchitecture(
            config=config,
            enable_memory=True,
            enable_parallel=True,
            checkpoint=True
        )

        self.assertIsNotNone(architecture._graph)

    def test_creation_without_checkpoint(self):
        """Should create architecture without checkpointing."""
        from agent.tool_nodes import ToolNodesArchitecture, CrewEngineConfig

        config = CrewEngineConfig(
            gemini_api_key="test-key",
            model_name="gemini/gemini-2.5-flash",
            max_rpm=10,
            max_iter=5
        )

        architecture = ToolNodesArchitecture(
            config=config,
            checkpoint=False
        )

        self.assertIsNotNone(architecture._graph)

    def test_execute_method(self):
        """Should execute a goal through the full pipeline."""
        from agent.tool_nodes import ToolNodesArchitecture, CrewEngineConfig

        config = CrewEngineConfig(
            gemini_api_key="test-key",
            model_name="gemini/gemini-2.5-flash",
            max_rpm=10,
            max_iter=5
        )

        architecture = ToolNodesArchitecture(config=config, checkpoint=False)

        result = architecture.execute(
            goal="Search for AI news",
            context="User is interested in technology",
            max_steps=5
        )

        self.assertIn("success", result)
        self.assertIn("execution_time_seconds", result)
        self.assertIn("tools_used", result)


class TestToolNodeFactory(unittest.TestCase):
    """Test the tool node factory functions."""

    def test_create_tool_node(self):
        """Should create a tool node for a valid tool name."""
        from agent.tool_nodes import create_tool_node, CrewEngineConfig

        config = CrewEngineConfig(
            gemini_api_key="test-key",
            model_name="gemini/gemini-2.5-flash",
            max_rpm=10,
            max_iter=5
        )

        # Test valid tools
        valid_tools = ["web_search", "open_app", "weather_report"]

        for tool_name in valid_tools:
            with self.subTest(tool=tool_name):
                node = create_tool_node(tool_name, config)
                self.assertIsNotNone(node)
                self.assertEqual(node.tool_name, tool_name)

    def test_create_tool_node_invalid(self):
        """Should raise error for invalid tool name."""
        from agent.tool_nodes import create_tool_node, CrewEngineConfig

        config = CrewEngineConfig(
            gemini_api_key="test-key",
            model_name="gemini/gemini-2.5-flash",
            max_rpm=10,
            max_iter=5
        )

        with self.assertRaises(ValueError):
            create_tool_node("invalid_tool", config)

    def test_create_all_tool_nodes(self):
        """Should create all tool nodes."""
        from agent.tool_nodes import create_all_tool_nodes, CrewEngineConfig

        config = CrewEngineConfig(
            gemini_api_key="test-key",
            model_name="gemini/gemini-2.5-flash",
            max_rpm=10,
            max_iter=5
        )

        nodes = create_all_tool_nodes(config)

        # Should have nodes for all defined tools
        expected_tools = ["web_search", "open_app", "weather_report"]
        for tool in expected_tools:
            self.assertIn(tool, nodes)


class TestMemoryUpdateNode(unittest.TestCase):
    """Test the memory update node."""

    def test_memory_update_node(self):
        """Should update memory with execution results."""
        from agent.tool_nodes import memory_update_node

        # Create state with execution results
        state = {
            "tools_used": ["web_search", "open_app"],
            "success": True,
            "steps_executed": [
                {"step": 1, "tool": "web_search", "status": "success"}
            ]
        }

        result = memory_update_node(state)

        # Should return state (memory update may or may not succeed depending on environment)
        self.assertEqual(result, state)

    def test_memory_update_node_error_handling(self):
        """Should handle memory update errors gracefully."""
        from agent.tool_nodes import memory_update_node

        # Create state with empty tools list
        state = {"tools_used": [], "success": True}
        result = memory_update_node(state)

        # Should still return state without raising
        self.assertEqual(result, state)


# ════════════════════════════════════════════════════════════════════════════════
#  Test Suite Runner
# ════════════════════════════════════════════════════════════════════════════════

def run_tests():
    """Run all tests with verbose output."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestToolNodeState))
    suite.addTests(loader.loadTestsFromTestCase(TestPlanningNode))
    suite.addTests(loader.loadTestsFromTestCase(TestExecutorNode))
    suite.addTests(loader.loadTestsFromTestCase(TestToolNodesArchitecture))
    suite.addTests(loader.loadTestsFromTestCase(TestToolNodeFactory))
    suite.addTests(loader.loadTestsFromTestCase(TestMemoryUpdateNode))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    print("=" * 80)
    print("  JARVIS Tool Nodes Architecture - Test Suite")
    print("=" * 80)

    # Setup test environment
    mock_api_keys()

    success = run_tests()

    print("\n" + "=" * 80)
    if success:
        print("  ALL TESTS PASSED")
    else:
        print("  SOME TESTS FAILED")
    print("=" * 80)

    sys.exit(0 if success else 1)
