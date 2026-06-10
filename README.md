# J.A.R.V.I.S — MARK XXXIX

> **Just A Rather Very Intelligent System**  
> *The Last Monolithic Architecture Before the Agentic Evolution*

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Status](https://img.shields.io/badge/status-migration--ready-orange.svg)](#migration-roadmap)

---

## Executive Summary

JARVIS Mark XXXIX represents the culmination of a decade of evolution in personal AI assistant technology — a **monolithic-threaded architecture** engineered for reliability, performance, and direct system control. This final iteration before our strategic migration to LangGraph-based multi-agent orchestration delivers:

- **17+ specialized action modules** for complete Windows system automation
- **Hybrid memory system** combining SQLite for short-term context with ChromaDB for long-term semantic recall
- **Real-time audio streaming** with Playwright-powered web scraping
- **Screen and camera vision** with integrated Google Gen AI
- **Multi-step task planning** with autonomous error recovery

> **Note**: This is the last iteration of our monolithic architecture. JARVIS is currently in a **migration-readiness state**, with all components prepared for our transition to a LangGraph-driven Multi-Agent Agentic AI framework. See the [Migration Roadmap](#migration-roadmap) for details.

---

## System Architecture

### Overview

JARVIS Mark XXXIX operates on a **hybrid monolithic-threaded architecture** — a single-threaded event loop with asynchronous capabilities, thread-safe queue management, and synchronous tool execution.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         JARVIS ARCHITECTURE                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                         USER INTERFACE LAYER                            │ │
│  │  ┌──────────────────────┐  ┌──────────────────────┐  ┌────────────────┐ │ │
│  │  │   PyQt6 HUD Canvas   │  │  System Metrics      │  │  File Drop   │ │ │
│  │  │   (Visual Feedback)  │  │  (CPU/MEM/GPU/NET)   │  │  Zone        │ │ │
│  │  └──────────┬───────────┘  └──────────┬───────────┘  └───────┬────────┘ │ │
│  └─────────────┼──────────────────────────┼──────────────────────┼───────────┘  │
│                 │                          │                      │             │
│                 ▼                          ▼                      ▼             │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                         CORE ENGINE LAYER                               │ │
│  │  ┌──────────────────────┐  ┌──────────────────────┐  ┌────────────────┐ │ │
│  │  │   Audio Stream       │  │   Text Input Handler │  │  File Loader   │ │ │
│  │  │   Queue Management   │  │   on_text_command    │  │   Manager      │ │ │
│  │  └──────────┬───────────┘  └──────────┬───────────┘  └───────┬────────┘ │ │
│  └─────────────┼──────────────────────────┼──────────────────────┼───────────┘  │
│                 │                          │                      │             │
│                 ▼                          ▼                      ▼             │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                      AGENTIC PROCESSING LAYER                           │ │
│  │  ┌───────────────────────────────────────────────────────────────────┐  │ │
│  │  │   JarvisRAGProcessor (memory/rag_processor.py)                   │  │ │
│  │  │   - Short-term: SQLite conversation history                     │  │ │
│  │  │   - Long-term: ChromaDB semantic memory                         │  │ │
│  │  │   - Auto-memory extraction & consolidation                      │  │ │
│  │  └───────────────────────────────────────────────────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│                 ┌───────────────────────┐                                    │
│                 │       ROUTER          │                                    │
│                 └──────────┬────────────┘                                    │
│                            ▼                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                        ACTION MODULES (17+)                             │ │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────────────────┐   │ │
│  │  │ open_app│ │web_search│ │ browser │ │ file_con│ │  screen_process│   │ │
│  │  │         │ │         │ │ control │ │ troller │ │  (camera+screen) │   │ │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └──────────────────┘   │ │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────────────────┐   │ │
│  │  │computer │ │computer │ │ game_up │ │ flight_ │ │  code_helper     │   │ │
│  │  │ control │ │ settings│ │ dated   │ │ finder  │ │  dev_agent       │   │ │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └──────────────────┘   │ │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────────────────┐   │ │
│  │  │ send_msg│ │ reminder│ │youtube  │ │ desktop │ │  file_processor  │   │ │
│  │  │         │ │         │ │ video   │ │ control │ │                │   │ │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └──────────────────┘   │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Architecture Components

| Layer | Components | Responsibility |
|-------|------------|----------------|
| **UI Layer** | `ui.py` (1,530 lines) | PyQt6 HUD, metrics display, file drop zones |
| **Core Engine** | `main.py` (942 lines) | Event loop, audio queues, tool routing |
| **Processing** | `memory/rag_processor.py` | RAG pipeline, conversation history, auto-memory |
| **Planning** | `agent/planner.py` | Goal decomposition into tool steps |
| **Execution** | `agent/executor.py` | Plan execution, retry logic, error recovery |
| **Task Queue** | `agent/task_queue.py` | Priority scheduling, concurrent execution |
| **Error Handling** | `agent/error_handler.py` | Recovery decisions, replanning suggestions |
| **Action Modules** | 17 modules in `actions/` | System control, web automation, file ops |

### Technical Stack

| Component | Technology | Version |
|-----------|------------|---------|
| Core Language | Python | 3.10+ |
| UI Framework | PyQt6 | 6.5+ |
| LLM SDK | Google Gen AI | v1.0+ |
| Vector DB | ChromaDB | 0.4+ |
| Short-term Memory | SQLite | Built-in |
| Audio Processing | SoundDevice | 0.4+ |
| Web Automation | Playwright | 1.40+ |
| Screen Capture | mss | 6.1+ |
| Computer Control | pyautogui | 0.9+ |

---

## Key Capabilities

### 1. Web & Information Access

| Module | Lines | Capabilities |
|--------|-------|--------------|
| `web_search.py` | 385 | Serper API + Playwright stealth deep scraping, ChromaDB storage |
| `browser_control.py` | 519 | Full Playwright automation (navigation, form filling, scraping) |
| `file_processor.py` | 832 | Document analysis (PDF, DOCX, XLSX, images) |
| `screen_processor.py` | 367 | Screenshot capture + camera feed + Gemini Live analysis |

**Use Cases:**
- Real-time web research with deep content scraping
- Automated form submission and data extraction
- Multi-format document processing
- Visual understanding of screen content

### 2. System & Application Control

| Module | Lines | Capabilities |
|--------|-------|--------------|
| `open_app.py` | 207 | Windows app launching with path detection |
| `computer_control.py` | 477 | Mouse/keyboard automation, screenshot, screen finding |
| `computer_settings.py` | 671 | OS configuration (brightness, volume, network) |
| `desktop.py` | 456 | Desktop wallpaper, organization, cleanup |

**Use Cases:**
- Context-aware application launching
- Automated system configuration
- Windows automation for repetitive tasks
- Desktop environment management

### 3. Communication & Media

| Module | Lines | Capabilities |
|--------|-------|--------------|
| `send_message.py` | 214 | WhatsApp, Telegram messaging |
| `youtube_video.py` | 417 | YouTube video control, summarization |
| `weather_report.py` | 61 | Current weather and forecast |
| `flight_finder.py` | 338 | Flight search with price tracking |

**Use Cases:**
- Instant messaging automation
- Media playback control and content discovery
- Travel planning and flight monitoring
- Weather-based decision support

### 4. Task Automation & Productivity

| Module | Lines | Capabilities |
|--------|-------|--------------|
| `reminder.py` | 155 | Windows Task Scheduler integration |
| `file_controller.py` | 481 | File I/O operations, search, disk usage |
| `game_updater.py` | 816 | Steam/Epic game management |
| `code_helper.py` | 582 | Code generation, editing, execution |

**Use Cases:**
- Scheduled task automation
- File system management
- Gaming ecosystem management
- Developer productivity助手

### 5. Advanced AI Operations

| Module | Lines | Capabilities |
|--------|-------|--------------|
| `dev_agent.py` | 596 | Agent task delegation and orchestration |
| `code_helper.py` | 582 | Code generation, explanation, debugging |
| `agent/planner.py` | 240 | Goal decomposition, step planning |
| `agent/executor.py` | 400 | Plan execution, retries, error recovery |
| `agent/error_handler.py` | 196 | Error analysis, recovery suggestions |

**Use Cases:**
- Multi-step task orchestration
- Autonomous error recovery
- Code analysis and generation
- Goal-oriented task execution

---

## Installation & Setup

### Prerequisites

- **Python**: 3.10 or higher
- **Operating System**: Windows 10/11 (primary), Linux (partial support), macOS (limited)
- **Hardware**: Minimum 4GB RAM, modern CPU

### Quick Start

```bash
# Clone the repository
git clone https://github.com/your-org/jarvis.git
cd jarvis

# Create and activate virtual environment
python -m venv jarvis-env
source jarvis-env/bin/activate  # Windows: jarvis-env\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Initialize configuration
# Edit config/api_keys.json with your Gemini and OpenRouter API keys
# Edit config/config.json with system preferences

# Launch JARVIS
python main.py
```

### Dependencies

| Package | Purpose | Version |
|---------|---------|---------|
| `google-genai` | Gemini LLM integration | 1.0+ |
| `chromadb` | Vector database | 0.4+ |
| `playwright` | Web automation | 1.40+ |
| `playwright-stealth` | Anti-bot bypass | 1.0+ |
| `PyQt6` | UI framework | 6.5+ |
| `sounddevice` | Audio processing | 0.4+ |
| `psutil` | System monitoring | 5.9+ |
| `python-dotenv` | Environment config | 1.0+ |
| `opencv-python` | Image processing | 4.8+ |
| `mss` | Screen capture | 6.1+ |

### Docker Support (Beta)

```bash
docker build -t jarvis:latest .
docker run -it --rm \
  -v $PWD/config:/app/config \
  -v $PWD/jarvis_memory:/app/jarvis_memory \
  jarvis:latest
```

---

## Configuration

### API Keys (`config/api_keys.json`)

```json
{
  "gemini_api_key": "AIza...",
  "openrouter_api_key": "sk-or-v1-...",
  "os_system": "windows"
}
```

### Environment Variables (Optional)

```bash
# .env file in project root
GEMINI_API_KEY=AIza...
OPENROUTER_API_KEY=sk-or-v1-...
SERPER_API_KEY=your-serper-key-if-available
```

### Configuration Options (`config/config.json`)

| Option | Default | Description |
|--------|---------|-------------|
| `audio_sample_rate` | 16000 | Microphone sample rate |
| `output_sample_rate` | 24000 | Speaker sample rate |
| `max_memory_facts` | 10 | Maximum facts to load |
| `tool_timeout` | 30 | Tool execution timeout (seconds) |
| `retry_attempts` | 3 | Maximum tool retry attempts |
| `debug_mode` | false | Enable verbose logging |

---

## Migration Roadmap

### Current State: Monolithic Architecture

JARVIS Mark XXXIX operates as a **single-threaded event loop** with synchronous tool execution. While robust and reliable, this architecture has limitations:

| Limitation | Impact |
|------------|--------|
| Sequential tool execution | 7.5s for 3-tool queries |
| No autonomous replanning | User intervention required |
| Tightly coupled modules | Difficult testing and maintenance |
| No persistent agent state | Context lost on restart |

### Strategic Migration to LangGraph

We are migrating to a **LangGraph-driven Multi-Agent Agentic AI** architecture. This represents our largest architectural evolution since JARVIS's inception.

#### Migration Timeline

| Phase | Duration | Status |
|-------|----------|--------|
| Phase 0: Foundation | Week 1 | ✅ Complete |
| Phase 1: RAG Migration | Week 2 | In Progress |
| Phase 2: Tool Nodes | Week 3 | Pending |
| Phase 3: State Persistence | Week 4 | Pending |
| Phase 4: Autonomous Features | Week 5 | Pending |
| Phase 5: Audio Integration | Week 6 | Pending |
| Phase 6: Final Integration | Week 7 | Pending |

#### Benefits of Migration

| Feature | Before | After Migration |
|---------|--------|-----------------|
| Parallel Tool Execution | Sequential | 4-7x faster |
| Error Recovery | Manual | Autonomous |
| State Persistence | SQLite only | MemorySaver + ChromaDB |
| Testability | Integration tests | 80%+ node coverage |
| Code Organization | 942-line main.py | 200-line modular nodes |

#### New Capabilities Enabled

1. **Parallel Tool Execution**: Execute multiple tools concurrently
2. **Autonomous Self-Correction**: Agent detects and recovers from errors
3. **Multi-Turn Goal Tracking**: Agent remembers and continues user goals
4. **Context-Aware Interrupts**: Natural conversation turn-taking
5. **Declarative State Machine**: Explicit state transitions

### Running Both Architectures (Transition Period)

During migration, both architectures run in parallel:

```python
# main.py - HybridExecutor
from agent.executor import AgentExecutor as OldExecutor
from langgraph.adapters import LangGraphExecutor

class HybridExecutor:
    def __init__(self):
        self.old_executor = OldExecutor()
        self.new_executor = LangGraphExecutor()
        self.migration_percentage = 0.5  # 50% to new
    
    async def execute(self, goal: str, **kwargs):
        if random.random() < self.migration_percentage:
            return await self.new_executor.execute({"user_input": goal})
        else:
            return await self.old_executor.execute(goal, **kwargs)
```

### Completion Criteria

| Criterion | Target |
|-----------|--------|
| System uptime during migration | 99.9% |
| Response time improvement | >40% faster |
| Error rate reduction | >50% fewer interruptions |
| User satisfaction score | >4.5/5 |

---

## Project Structure

```
Project-J.A.R.V.I.S/
├── actions/                    # 17+ action modules
│   ├── web_search.py          # Serper API + Playwright
│   ├── browser_control.py     # Playwright automation
│   ├── screen_processor.py    # Camera + screenshot
│   ├── computer_control.py    # Mouse/keyboard
│   ├── file_controller.py     # File operations
│   └── [12 more modules]...
├── agent/
│   ├── planner.py             # Goal decomposition
│   ├── executor.py            # Plan execution
│   ├── task_queue.py          # Priority scheduling
│   └── error_handler.py       # Recovery analysis
├── config/
│   ├── api_keys.json          # API credentials
│   └── config.json            # System settings
├── core/
│   └── prompt.txt             # System instructions
├── memory/
│   ├── memory_manager.py      # Short-term + long-term
│   ├── rag_processor.py       # RAG pipeline
│   └── config_manager.py      # Config helpers
├── future_enhancement/        # Migration documentation
│   ├── plan.md               # Migration plan
│   ├── tasks.md              # Implementation tasks
│   ├── blueprint.md          # Architecture design
│   └── verify.md             # Validation suite
├── jarvis_memory/             # Persistent data
│   ├── short_term.db          # SQLite history
│   └── chroma/                # Vector store
├── ui.py                      # PyQt6 interface
├── main.py                    # Core engine (942 lines)
└── requirements.txt           # Dependencies
```

---

## Development

### Running Tests

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# Linting
ruff check .

# Type checking
mypy --config-file=pyproject.toml .
```

### Adding New Action Modules

1. Create `actions/new_module.py`
2. Implement `new_module_action(parameters: dict, player=None) -> str`
3. Register in `main.py` TOOL_DECLARATIONS
4. Add import in `main.py` action imports
5. Add import in `agent/executor.py` _call_tool

### Debugging

```bash
# Enable debug mode
export JARVIS_DEBUG=true

# View logs
tail -f logs/jarvis.log

# Debug with pdb
python -m pdb main.py
```

---

## Troubleshooting

### Common Issues

| Error | Solution |
|-------|----------|
| `GEMINI_API_KEY not found` | Set in `config/api_keys.json` |
| `Playwright not installed` | `playwright install-deps` |
| `ChromaDB initialization failed` | Clear `jarvis_memory/chroma/` |
| `Audio queue full` | Increase `CHUNK_SIZE` in config |
| `Tool timeout` | Increase `tool_timeout` in config |

### Logging

| Level | Environment Variable | Output |
|-------|---------------------|--------|
| DEBUG | `JARVIS_DEBUG=true` | Full logging |
| INFO | (default) | Standard output |
| ERROR | `JARVIS_ERROR_LOG=true` | Error file |

---

## Contributing

We welcome contributions! Please read our [Contributing Guidelines](CONTRIBUTING.md) first.

### Development Workflow

1. Create a feature branch: `git checkout -b feature/amazing-feature`
2. Commit your changes: `git commit -m 'feat: add amazing feature'`
3. Push to the branch: `git push origin feature/amazing-feature`
4. Open a Pull Request

### Pull Request Process

1. Update documentation to match changes
2. Add tests for new functionality
3. Ensure all checks pass
4. Request review from maintainers

---

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- Google Gen AI team for the Gemini LLM
- ChromaDB team for the vector database
- Playwright team for browser automation
- PyQt6 team for the UI framework
- The open-source community for inspiration and support

---

## Contact & Support

- **GitHub Issues**: [Report bugs, request features](https://github.com/your-org/jarvis/issues)
- **Documentation**: [Full documentation](https://jarvis.ai/docs)
- **Email**: support@jarvis.ai
- **Twitter**: [@jarvis_ai](https://twitter.com/jarvis_ai)

---

## Acknowledgement

> **JARVIS Mark XXXIX** - The Final Monolithic Architecture  
> *This version represents the culmination of our monolithic architecture before our strategic migration to LangGraph. All components are prepared for the agentic evolution while maintaining full backward compatibility.*

---

<p align="center">
  <b>J.A.R.V.I.S. — Just A Rather Very Intelligent System</b><br>
  <i>Building the future of personal AI assistance, one command at a time</i>
</p>
