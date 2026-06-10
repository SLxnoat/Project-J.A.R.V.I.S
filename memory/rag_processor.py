import json
from pathlib import Path
from typing import Any

try:
    import google.generativeai as genai
except ImportError:
    try:
        from google import genai
    except Exception:
        genai = None

try:
    import memory.memory_manager as memory_module
except Exception:
    memory_module = None


class JarvisRAGProcessor:
    DEFAULT_MODEL = "gemini-2.5-flash"
    SYSTEM_INSTRUCTION = (
        "You are JARVIS, AI assistant. "
        "Use short-term conversation context, long-term memory facts, and tool results to answer. "
        "Keep responses concise, accurate, and grounded in available information. "
        "If you do not know something, say so instead of inventing details."
    )

    def __init__(self, model_name: str | None = None) -> None:
        self.root_dir = Path(__file__).resolve().parent.parent
        self.model_name = model_name or self.DEFAULT_MODEL
        self.api_key = self._load_api_key()
        self.memory = self._init_memory()
        self.model = self._init_llm()

    def _load_api_key(self) -> str | None:
        config_path = self.root_dir / "config" / "api_keys.json"
        try:
            with open(config_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
                return data.get("gemini_api_key")
        except Exception as exc:
            print(f"[Jarvis RAG] ⚠️ Could not load API key: {exc}")  # Sir, I failed to locate the Gemini API key
            return None

    def _init_memory(self) -> Any:
        if memory_module is None:
            print("[Jarvis RAG] ⚠️ Memory module unavailable.")  # Sir, I could not initialize memory
            return None

        try:
            return memory_module.JarvisMemory()
        except Exception as exc:
            print(f"[Jarvis RAG] ⚠️ Failed to initialize JarvisMemory: {exc}")  # Sir, I failed to initialize the memory system
            return None

    def _init_llm(self) -> Any:
        if genai is None:
            print("[Jarvis RAG] ⚠️ Google GenAI SDK is not installed.")  # Sir, I cannot access the language model
            return None

        if not self.api_key:
            print("[Jarvis RAG] ⚠️ Gemini API key is missing.")  # Sir, I cannot configure the model without credentials
            return None

        try:
            genai.configure(api_key=self.api_key)
            return genai.GenerativeModel(model_name=self.model_name)
        except Exception as exc:
            print(f"[Jarvis RAG] ⚠️ Failed to initialize LLM: {exc}")  # Sir, I failed to create the Gemini model client
            return None

    def process_user_input(self, user_input_text: str) -> str:
        user_text = (user_input_text or "").strip()
        if not user_text:
            return "Sir, I require user input to continue."

        recent_context = self._retrieve_recent_context()
        long_term_facts = self._retrieve_long_term_facts(user_text)
        prompt = self._build_augmented_prompt(user_text, recent_context, long_term_facts)

        jarvis_response = self._generate_response(prompt)
        if not jarvis_response:
            return "Sir, I failed to process the RAG pipeline."

        self._persist_short_term_interaction("user", user_text)
        self._persist_short_term_interaction("jarvis", jarvis_response)
        self._auto_memory_consolidation(user_text, jarvis_response)

        return jarvis_response

    def _retrieve_recent_context(self) -> list[dict]:
        if self.memory is None:
            return []

        try:
            return self.memory.get_recent_context(limit=5)
        except Exception as exc:
            print(f"[Jarvis RAG] ⚠️ Failed to retrieve short-term context: {exc}")  # Sir, I could not read the recent conversation
            return []

    def _retrieve_long_term_facts(self, query_text: str) -> list[dict]:
        if self.memory is None:
            return []

        try:
            return self.memory.recall_relevant_facts(query_text, n_results=3)
        except Exception as exc:
            print(f"[Jarvis RAG] ⚠️ Failed to retrieve long-term facts: {exc}")  # Sir, I could not recall long-term memory
            return []

    def _build_augmented_prompt(
        self,
        user_text: str,
        recent_context: list[dict],
        long_term_facts: list[dict],
    ) -> str:
        prompt_parts = [self.SYSTEM_INSTRUCTION]

        if long_term_facts:
            prompt_parts.append("[LONG-TERM FACTS]")
            for index, fact in enumerate(long_term_facts, start=1):
                content = str(fact.get("content", "")).strip()
                if not content:
                    continue
                metadata = fact.get("metadata") or {}
                metadata_str = ""
                if metadata:
                    metadata_pairs = [f"{k}={v}" for k, v in metadata.items() if v is not None]
                    if metadata_pairs:
                        metadata_str = f" ({', '.join(metadata_pairs)})"
                prompt_parts.append(f"Fact {index}: {content}{metadata_str}")
        else:
            prompt_parts.append("[LONG-TERM FACTS] No relevant long-term facts were found.")

        if recent_context:
            prompt_parts.append("[RECENT CONVERSATION HISTORY]")
            for record in recent_context:
                timestamp = record.get("timestamp") or "unknown time"
                role = record.get("role", "user").title()
                content = record.get("content", "").strip()
                if not content:
                    continue
                prompt_parts.append(f"{timestamp} | {role}: {content}")
        else:
            prompt_parts.append("[RECENT CONVERSATION HISTORY] No recent conversation history available.")

        prompt_parts.append("[USER INPUT]")
        prompt_parts.append(user_text)
        prompt_parts.append("[RESPONSE]")
        prompt_parts.append(
            "Answer as JARVIS using the facts and recent history when relevant. "
            "Do not invent unsupported information."
        )

        return "\n".join(prompt_parts)

    def _generate_response(self, prompt: str) -> str | None:
        if self.model is None:
            print("[Jarvis RAG] ⚠️ LLM client is unavailable.")  # Sir, I cannot generate a response without a model
            return None

        try:
            response = self.model.generate_content(prompt)
            if not response or not getattr(response, "text", None):
                return None
            return str(response.text).strip()
        except Exception as exc:
            print(f"[Jarvis RAG] ⚠️ LLM generation failed: {exc}")  # Sir, the language model failed to respond
            return None

    def _persist_short_term_interaction(self, role: str, content: str) -> None:
        if self.memory is None:
            return

        try:
            self.memory.save_interaction(role, content)
        except Exception as exc:
            print(f"[Jarvis RAG] ⚠️ Failed to persist short-term interaction: {exc}")  # Sir, I could not save the conversation turn

    def _auto_memory_consolidation(self, user_text: str, jarvis_text: str) -> None:
        if memory_module is None or self.memory is None:
            return

        try:
            should_save = memory_module.should_extract_memory(user_text, jarvis_text, self.api_key or "")
            if should_save:
                self.memory.store_permanent_fact(
                    user_text,
                    metadata={"source": "auto_memory_consolidation"},
                )
        except Exception as exc:
            print(f"[Jarvis RAG] ⚠️ Auto-memory consolidation failed: {exc}")  # Sir, I could not store the new fact
