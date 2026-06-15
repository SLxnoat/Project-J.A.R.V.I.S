"""
╔══════════════════════════════════════════════════════════════════════════════════╗
║       JARVIS MARK XXXIX — Phase 5: State Persistence Tests                     ║
║       Module : tests/test_state_persistence.py                                 ║
║                                                                                 ║
║  Purpose      : Unit and integration tests for State Persistence               ║
║  Architecture : MemorySaver + ChromaDB integration                             ║
╚══════════════════════════════════════════════════════════════════════════════════╝
"""

import unittest
import sys
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


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

class TestStatePersistenceManager(unittest.TestCase):
    """Test the StatePersistenceManager class."""

    def setUp(self):
        """Set up test fixtures with temporary directories."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.checkpoint_dir = self.test_dir / "checkpoints"
        self.agent_memory_dir = self.test_dir / "agent_memories"

        # Create test directories
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.agent_memory_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        """Clean up test directories."""
        try:
            shutil.rmtree(self.test_dir)
        except Exception:
            pass

    def test_init_creates_directories(self):
        """Should create necessary directories on initialization."""
        from agent.state_persistence import StatePersistenceManager

        manager = StatePersistenceManager(
            memory_dir=self.test_dir,
            checkpoint_dir=self.checkpoint_dir,
            agent_memory_dir=self.agent_memory_dir
        )

        self.assertTrue(self.checkpoint_dir.exists())
        self.assertTrue(self.agent_memory_dir.exists())

    def test_save_and_load_checkpoint(self):
        """Should save and load state checkpoints."""
        from agent.state_persistence import StatePersistenceManager

        manager = StatePersistenceManager(
            checkpoint_dir=self.checkpoint_dir
        )

        checkpoint_id = "test_checkpoint"
        test_state = {
            "goal": "Test goal",
            "steps_executed": [],
            "tools_used": [],
            "success": False
        }

        # Save checkpoint
        path = manager.save_checkpoint(checkpoint_id, test_state)
        self.assertTrue(len(path) > 0)
        self.assertTrue(Path(path).exists())

        # Load checkpoint
        loaded = manager.load_checkpoint(checkpoint_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["state"]["goal"], "Test goal")

    def test_list_checkpoints(self):
        """Should list available checkpoints."""
        from agent.state_persistence import StatePersistenceManager

        manager = StatePersistenceManager(
            checkpoint_dir=self.checkpoint_dir
        )

        # Create multiple checkpoints
        for i in range(3):
            manager.save_checkpoint(f"checkpoint_{i}", {"test": i})

        checkpoints = manager.list_checkpoints()
        self.assertGreater(len(checkpoints), 0)

    def test_conversation_history(self):
        """Should manage conversation history."""
        from agent.state_persistence import StatePersistenceManager

        manager = StatePersistenceManager(
            agent_memory_dir=self.agent_memory_dir
        )

        # Add conversation turns
        manager.add_conversation_turn(
            user_id="user_1",
            user_message="Hello",
            agent_message="Hi there!",
            context={"timestamp": "2024-01-01"}
        )

        manager.add_conversation_turn(
            user_id="user_1",
            user_message="How are you?",
            agent_message="I'm doing well, thank you!"
        )

        # Get history
        history = manager.get_conversation_history("user_1", n_turns=10)
        self.assertEqual(len(history), 2)

    def test_save_conversation_history(self):
        """Should save conversation history to disk."""
        from agent.state_persistence import StatePersistenceManager

        manager = StatePersistenceManager(
            agent_memory_dir=self.agent_memory_dir
        )

        manager.add_conversation_turn(
            user_id="user_1",
            user_message="Test message",
            agent_message="Test response"
        )

        # Save to disk
        result = manager.save_conversation_history("user_1")
        self.assertTrue(result)

        # Verify file exists
        history_file = self.agent_memory_dir / "user_1_conversation.json"
        self.assertTrue(history_file.exists())

    def test_save_and_recall_agent_memory(self):
        """Should save and recall agent memories in ChromaDB."""
        from agent.state_persistence import StatePersistenceManager

        manager = StatePersistenceManager(
            agent_memory_dir=self.agent_memory_dir
        )

        # Save memory
        memory_id = manager.save_agent_memory(
            agent_id="test_agent",
            memory_type="goal_tracking",
            content="User wants to search for news",
            metadata={"timestamp": "2024-01-01"}
        )

        self.assertTrue(len(memory_id) > 0)

        # Recall memory
        memories = manager.recall_agent_memories(
            agent_id="test_agent",
            memory_type="goal_tracking",
            query="news"
        )

        self.assertGreater(len(memories), 0)


class TestLangGraphCheckpointer(unittest.TestCase):
    """Test the LangGraphCheckpointer class."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.checkpoint_dir = self.test_dir / "checkpoints"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        from agent.state_persistence import StatePersistenceManager
        self.manager = StatePersistenceManager(
            checkpoint_dir=self.checkpoint_dir
        )

    def tearDown(self):
        """Clean up test directories."""
        try:
            shutil.rmtree(self.test_dir)
        except Exception:
            pass

    def test_checkpoint_id_generation(self):
        """Should generate unique checkpoint IDs."""
        from agent.state_persistence import LangGraphCheckpointer

        checkpointer = LangGraphCheckpointer(self.manager)
        checkpoint_id = checkpointer.get_checkpoint_id()

        self.assertTrue(len(checkpoint_id) > 0)

    def test_checkpoint_set_id(self):
        """Should allow setting checkpoint ID."""
        from agent.state_persistence import LangGraphCheckpointer

        checkpointer = LangGraphCheckpointer(self.manager)
        new_id = "custom_checkpoint_id"
        checkpointer.set_checkpoint_id(new_id)
        self.assertEqual(checkpointer.get_checkpoint_id(), new_id)


class TestEnhancedToolNodesArchitecture(unittest.TestCase):
    """Test the EnhancedToolNodesArchitecture class."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.checkpoint_dir = self.test_dir / "checkpoints"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Create mock config
        self.mock_config = MagicMock()
        self.mock_config.gemini_api_key = "test-key"
        self.mock_config.model_name = "gemini/gemini-2.5-flash"
        self.mock_config.max_rpm = 10
        self.mock_config.max_iter = 5

    def tearDown(self):
        """Clean up test directories."""
        try:
            shutil.rmtree(self.test_dir)
        except Exception:
            pass

    def test_creation_with_defaults(self):
        """Should create architecture with default configuration."""
        try:
            from agent.state_persistence import EnhancedToolNodesArchitecture

            architecture = EnhancedToolNodesArchitecture(
                config=self.mock_config,
                enable_persistence=True,
                checkpoint_id="test_arch"
            )

            self.assertIsNotNone(architecture)
            self.assertEqual(architecture.checkpoint_id, "test_arch")
        except ImportError as e:
            self.skipTest(f"Missing dependency: {e}")

    def test_execute_method(self):
        """Should execute a goal through the architecture."""
        try:
            from agent.state_persistence import EnhancedToolNodesArchitecture

            architecture = EnhancedToolNodesArchitecture(
                config=self.mock_config,
                enable_persistence=True,
                checkpoint_id="test_execute"
            )

            result = architecture.execute(
                goal="Test goal",
                context="Test context",
                max_steps=5
            )

            self.assertIn("success", result)
            self.assertIn("execution_time_seconds", result)
        except ImportError as e:
            self.skipTest(f"Missing dependency: {e}")


class TestConvenienceFactory(unittest.TestCase):
    """Test the convenience factory functions."""

    def test_load_state_persistence_architecture(self):
        """Should create architecture with factory function."""
        try:
            from agent.state_persistence import load_state_persistence_architecture

            # Mock the api_keys.json to avoid actual API key loading
            with patch.object(Path, 'exists', return_value=True):
                with patch('pathlib.Path.read_text') as mock_read:
                    mock_read.return_value = '{"gemini_api_key": "test-key"}'
                    architecture = load_state_persistence_architecture(
                        enable_persistence=True
                    )

            self.assertIsNotNone(architecture)
        except ImportError as e:
            self.skipTest(f"Missing dependency: {e}")


class TestIntegration(unittest.TestCase):
    """Integration tests for state persistence features."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = Path(tempfile.mkdtemp())
        mock_api_keys()

    def tearDown(self):
        """Clean up test directories."""
        try:
            shutil.rmtree(self.test_dir)
        except Exception:
            pass

    def test_full_workflow(self):
        """Test full state persistence workflow."""
        from agent.state_persistence import (
            StatePersistenceManager,
            LangGraphCheckpointer,
            EnhancedToolNodesArchitecture,
            CrewEngineConfig
        )

        manager = StatePersistenceManager(
            checkpoint_dir=self.test_dir / "checkpoints"
        )

        # Save state
        checkpoint_id = "full_workflow_test"
        state = {
            "goal": "Complete a task",
            "steps_executed": [],
            "tools_used": [],
            "success": False
        }

        manager.save_checkpoint(checkpoint_id, state)

        # Load state
        loaded = manager.load_checkpoint(checkpoint_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["state"]["goal"], "Complete a task")

    def test_memory_operations(self):
        """Test memory save and recall operations."""
        from agent.state_persistence import StatePersistenceManager

        manager = StatePersistenceManager(
            agent_memory_dir=self.test_dir / "agent_memories"
        )

        # Save memory
        memory_id = manager.save_agent_memory(
            agent_id="integration_test",
            memory_type="tool_usage",
            content="Used web_search to find information"
        )

        self.assertTrue(len(memory_id) > 0)

        # Recall memory
        memories = manager.recall_agent_memories(
            agent_id="integration_test",
            query="web search"
        )

        self.assertGreater(len(memories), 0)


# ════════════════════════════════════════════════════════════════════════════════
#  Test Suite Runner
# ════════════════════════════════════════════════════════════════════════════════

def run_tests():
    """Run all tests with verbose output."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestStatePersistenceManager))
    suite.addTests(loader.loadTestsFromTestCase(TestLangGraphCheckpointer))
    suite.addTests(loader.loadTestsFromTestCase(TestEnhancedToolNodesArchitecture))
    suite.addTests(loader.loadTestsFromTestCase(TestConvenienceFactory))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    print("=" * 80)
    print("  JARVIS State Persistence Architecture - Test Suite")
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
