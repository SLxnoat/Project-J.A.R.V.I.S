# memory/memory_manager.py
# Modernized with google-genai SDK (v1.0+) and .env configuration
# Uses unified config loader for API key management

import json
import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from threading import Lock
from uuid import uuid4

# Add project root to path for config imports when running directly
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

try:
    import chromadb
    from chromadb.config import Settings
except Exception:
    chromadb = None
    Settings = None

try:
    from google import genai
except Exception:
    genai = None

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Import unified config loader
from config.loader import get_base_dir, get_api_key

BASE_DIR = get_base_dir()
MEMORY_DIR = BASE_DIR / "jarvis_memory"
SHORT_TERM_DB_PATH = MEMORY_DIR / "short_term.db"
# ChromaDB 1.1.1 uses a Rust-backed SQLite engine.  Pointing it at a directory
# that already contains a legacy chroma.sqlite3 (written by an older Python-only
# backend) causes a Rust index-out-of-range panic.  Storing in its own clean
# subdirectory avoids this permanently without deleting existing data.
CHROMA_STORE_DIR = MEMORY_DIR / "chroma_store"
LONG_TERM_COLLECTION_NAME = "jarvis_long_term"
EMBEDDING_MODEL = "models/gemini-embedding-001"


def _get_env_api_key(key_name: str) -> str | None:
    """
    Load API key using unified config loader.
    Priority: .env -> os.environ -> config/api_keys.json
    """
    return get_api_key(key_name)


class JarvisMemory:
    def __init__(self) -> None:
        self.memory_dir = MEMORY_DIR
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self._db_lock = Lock()
        self._short_term_conn = None
        self._chroma_client = None
        self._chroma_collection = None
        self._genai_client = None
        self._api_key = None

        self._init_short_term_db()
        self._init_genai_client()
        self._init_long_term_store()

    def _init_short_term_db(self) -> None:
        try:
            self._short_term_conn = sqlite3.connect(
                SHORT_TERM_DB_PATH,
                check_same_thread=False,
                isolation_level=None,
            )
            cursor = self._short_term_conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS short_term_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    role TEXT CHECK(role IN ('user','jarvis')) NOT NULL,
                    content TEXT NOT NULL
                )
                """
            )
            self._short_term_conn.commit()
        except Exception as exc:
            print(f"[Jarvis Memory] [WARN] Failed to initialize short-term SQLite: {exc}")  # Jarvis: fallback to no short-term store
            self._short_term_conn = None

    def _init_genai_client(self) -> None:
        """
        Initialize the modern google-genai SDK client.
        Replaces deprecated google.generativeai.Client initialization.
        """
        if genai is None:
            self._genai_client = None
            return

        # Get API key from environment (prioritizing .env file)
        self._api_key = _get_env_api_key("GEMINI_API_KEY")
        if not self._api_key:
            self._genai_client = None
            print("[Jarvis Memory] [WARN] GEMINI_API_KEY not found")  # Jarvis: no API key available
            return

        try:
            # Modern 2026 SDK Client initialization
            self._genai_client = genai.Client(api_key=self._api_key)
            print("[Jarvis Memory] [OK] Google GenAI SDK client initialized")  # Jarvis: Gemini SDK ready
        except Exception as exc:
            print(f"[Jarvis Memory] [WARN] Failed to initialize Gemini client: {exc}")  # Jarvis: embedding service unavailable
            self._genai_client = None

    def _embed_text(self, text: str) -> list[float] | None:
        """
        Generate embeddings using the modern google-genai SDK.
        Uses text-embedding-004 model with updated API format.
        """
        if self._genai_client is None:
            return None

        cleaned_text = (text or "").strip()
        if not cleaned_text:
            return None

        try:
            # Modern 2026 API format for text embeddings
            # Pass text directly as string
            response = self._genai_client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=cleaned_text,
            )

            # Handle response — normalised access avoids Pylance stub mismatches.
            # google-genai SDK may return ContentEmbedding objects (which have a
            # .values attribute) or plain lists, depending on the version.

            # Path A: response.embeddings  → list[ContentEmbedding]
            raw_embeddings: list | None = getattr(response, "embeddings", None)
            if raw_embeddings and isinstance(raw_embeddings, list) and len(raw_embeddings) > 0:
                first = raw_embeddings[0]
                vals = getattr(first, "values", None)
                if vals is not None:
                    return list(vals)
                # Older SDK versions may nest a further .embedding attribute
                # Type stubs may not include this attribute, so use getattr with fallback
                nested = getattr(first, "embedding", None)
                if nested is not None:
                    return list(nested) if not isinstance(nested, list) else nested
                if isinstance(first, (list, tuple)):
                    return list(first)

            # Path B: response.embedding  → ContentEmbedding (single)
            raw_single: list | None = getattr(response, "embedding", None)
            if raw_single is not None:
                vals = getattr(raw_single, "values", None)
                if vals is not None:
                    return list(vals)
                # Type stubs may not include this attribute
                nested = getattr(raw_single, "embedding", None)
                if nested is not None:
                    return list(nested) if not isinstance(nested, list) else nested
                if isinstance(raw_single, (list, tuple)):
                    return list(raw_single)

            # Handle dict-like response
            if hasattr(response, "__dict__"):
                for attr_name in ["embeddings", "embedding"]:
                    attr = getattr(response, attr_name, None)
                    if attr is not None:
                        if isinstance(attr, list) and len(attr) > 0:
                            item = attr[0]
                            if hasattr(item, "values"):
                                return list(item.values)
                            if hasattr(item, "embedding"):
                                return list(item.embedding)
                            if isinstance(item, (list, tuple)):
                                return list(item)

            print("[Jarvis Memory] [WARN] Failed to extract embedding from response")  # Jarvis: embedding extraction failed
            return None

        except Exception as exc:
            print(f"[Jarvis Memory] [WARN] Failed to create embedding: {exc}")  # Jarvis: embedding service unavailable
            return None

    def _create_chroma_client(self):
        if chromadb is None:
            raise ImportError("chromadb is not installed")

        # Use the dedicated chroma_store/ subdirectory so chromadb 1.1.1's Rust
        # SQLite engine never encounters the legacy schema written by older versions.
        CHROMA_STORE_DIR.mkdir(parents=True, exist_ok=True)

        if hasattr(chromadb, "PersistentClient"):
            return chromadb.PersistentClient(path=str(CHROMA_STORE_DIR))

        if hasattr(chromadb, "Client") and Settings is not None:
            return chromadb.Client(
                Settings(persist_directory=str(CHROMA_STORE_DIR), chroma_db_impl="duckdb+parquet")
            )

        raise RuntimeError("Unsupported chromadb client API")

    def _init_long_term_store(self) -> None:
        try:
            if chromadb is None:
                raise ImportError("chromadb is not installed")

            self._chroma_client = self._create_chroma_client()
            self._chroma_collection = self._chroma_client.get_or_create_collection(
                name=LONG_TERM_COLLECTION_NAME,
            )
        except Exception as exc:
            print(f"[Jarvis Memory] [WARN] Failed to initialize long-term ChromaDB: {exc}")  # Jarvis: long-term recall is disabled
            self._chroma_client = None
            self._chroma_collection = None

    def save_interaction(self, role: str, content: str) -> bool:
        if self._short_term_conn is None:
            return False

        role = role if role in {"user", "jarvis"} else "user"
        text = (content or "").strip()
        if not text:
            return False

        try:
            with self._db_lock:
                cursor = self._short_term_conn.cursor()
                cursor.execute(
                    "INSERT INTO short_term_memory (role, content) VALUES (?, ?)",
                    (role, text),
                )
                self._short_term_conn.commit()
            return True
        except Exception as exc:
            print(f"[Jarvis Memory] [WARN] Failed to save short-term interaction: {exc}")  # Jarvis: short-term memory write failed
            return False

    def get_recent_context(self, limit: int = 5) -> list[dict]:
        if self._short_term_conn is None:
            return []

        try:
            cursor = self._short_term_conn.cursor()
            cursor.execute(
                "SELECT id, timestamp, role, content FROM short_term_memory ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            rows = cursor.fetchall()
            context = [
                {
                    "id": row[0],
                    "timestamp": row[1],
                    "role": row[2],
                    "content": row[3],
                }
                for row in rows
            ]
            return list(reversed(context))
        except Exception as exc:
            print(f"[Jarvis Memory] [WARN] Failed to read short-term context: {exc}")  # Jarvis: read failed, but I can continue
            return []

    def clear_short_term(self) -> None:
        if self._short_term_conn is None:
            return

        try:
            with self._db_lock:
                cursor = self._short_term_conn.cursor()
                cursor.execute("DELETE FROM short_term_memory")
                self._short_term_conn.commit()
        except Exception as exc:
            print(f"[Jarvis Memory] [WARN] Failed to clear short-term memory: {exc}")  # Jarvis: cleanup failed

    def store_permanent_fact(self, fact_text: str, metadata: dict | None = None) -> list[str]:
        if self._chroma_collection is None or self._genai_client is None:
            return []

        text = (fact_text or "").strip()
        if not text:
            return []

        try:
            embedding = self._embed_text(text)
            if not embedding:
                print("[Jarvis Memory] [WARN] Failed to get embedding for permanent fact.")  # Jarvis: long-term store failed
                return []

            item_id = str(uuid4())
            actual_metadata = dict(metadata) if metadata else {}
            if not actual_metadata:
                actual_metadata = {"source": "user_input"}

            self._chroma_collection.add(
                documents=[text],
                metadatas=[actual_metadata],
                ids=[item_id],
                embeddings=[embedding],
            )
            return [item_id]
        except Exception as exc:
            print(f"[Jarvis Memory] [WARN] Failed to store permanent fact: {exc}")  # Jarvis: long-term store failed
            return []

    def recall_relevant_facts(self, query_text: str, n_results: int = 3) -> list[dict]:
        if self._chroma_collection is None or self._genai_client is None:
            return []

        query = (query_text or "").strip()
        if not query:
            return []

        try:
            embedding = self._embed_text(query)
            if not embedding:
                print("[Jarvis Memory] [WARN] Failed to get embedding for query.")  # Jarvis: semantic recall failed
                return []

            results = self._chroma_collection.query(
                query_embeddings=[embedding],
                n_results=n_results,
                include=["documents", "metadatas", "distances"],
            )
            # ChromaDB QueryResult values are TypedDict entries that may be None
            # when the collection is empty or no results match.
            # Guard against None before subscripting to avoid Pylance reportOptionalSubscript
            _docs_raw: list[list[str]] | None = results.get("documents")
            _meta_raw: list | None = results.get("metadatas")
            _dist_raw: list[list[float]] | None = results.get("distances")
            _docs_outer = _docs_raw if _docs_raw is not None else [[]]
            _meta_outer = _meta_raw if _meta_raw is not None else [[]]
            _dist_outer = _dist_raw if _dist_raw is not None else [[]]
            documents = _docs_outer[0] if _docs_outer else []
            metadatas = _meta_outer[0] if _meta_outer else []
            distances = _dist_outer[0] if _dist_outer else []

            facts = []
            # Guard: ensure lists are not None before zip (Pylance reportArgumentType fix)
            safe_docs = list(documents) if documents is not None else []
            safe_metas = list(metadatas) if metadatas is not None else []
            safe_dists = list(distances) if distances is not None else []
            # Truncate to shortest list to avoid zip issues
            min_len = min(len(safe_docs), len(safe_metas), len(safe_dists)) if safe_docs and safe_metas and safe_dists else 0
            for i in range(min_len):
                facts.append(
                    {
                        "content": safe_docs[i],
                        "metadata": safe_metas[i] or {},
                        "distance": safe_dists[i],
                    }
                )
            return facts
        except Exception as exc:
            print(f"[Jarvis Memory] [WARN] Failed to recall long-term facts: {exc}")  # Jarvis: semantic recall failed
            return []

    def load_memory(self) -> dict:
        if self._chroma_collection is None:
            return {"facts": []}

        try:
            data = self._chroma_collection.get(include=["documents", "metadatas"])
            # GetResult values are TypedDict fields; guard against None before use.
            # Pylance: data.get() returns TypedDict entry that may be None
            documents_raw = data.get("documents")
            metadatas_raw = data.get("metadatas")
            documents: list = documents_raw if documents_raw is not None else []
            metadatas: list = metadatas_raw if metadatas_raw is not None else []

            # Flatten nested lists produced by some chromadb versions
            if documents and isinstance(documents[0], list):
                documents = documents[0]
            if metadatas and isinstance(metadatas[0], list):
                metadatas = metadatas[0]

            # Guard: ensure lists are not None before zip (Pylance reportArgumentType fix)
            safe_docs = list(documents) if documents is not None else []
            safe_metas = list(metadatas) if metadatas is not None else []
            facts = [
                {"content": doc, "metadata": metadata or {}}
                for doc, metadata in zip(safe_docs, safe_metas)
                if isinstance(doc, str) and doc.strip()
            ]
            return {"facts": facts}
        except Exception as exc:
            print(f"[Jarvis Memory] [WARN] Failed to load memory facts: {exc}")  # Jarvis: loading memories failed
            return {"facts": []}

    def update_memory(self, memory_update: dict) -> dict:
        if not isinstance(memory_update, dict) or not memory_update:
            return self.load_memory()

        facts = self._serialize_memory_update(memory_update)
        for fact_text, metadata in facts:
            self.store_permanent_fact(fact_text, metadata)

        return self.load_memory()

    @staticmethod
    def _serialize_memory_update(memory_update: dict) -> list[tuple[str, dict]]:
        facts: list[tuple[str, dict]] = []
        for category, entries in memory_update.items():
            if not isinstance(entries, dict):
                continue
            for key, entry in entries.items():
                if isinstance(entry, dict) and "value" in entry:
                    value = entry["value"]
                else:
                    value = entry

                if value is None:
                    continue
                value_text = str(value).strip()
                if not value_text:
                    continue

                key_text = str(key).strip()
                category_text = str(category).strip()
                fact_text = (
                    f"{category_text}.{key_text}: {value_text}"
                    if category_text and key_text
                    else f"{key_text}: {value_text}"
                )

                facts.append(
                    (
                        fact_text,
                        {
                            "category": category_text,
                            "key": key_text,
                        },
                    )
                )
        return facts


jarvis_memory = JarvisMemory()


def save_interaction(role: str, content: str) -> bool:
    return jarvis_memory.save_interaction(role, content)


def get_recent_context(limit: int = 5) -> list[dict]:
    return jarvis_memory.get_recent_context(limit)


def clear_short_term() -> None:
    jarvis_memory.clear_short_term()


def store_permanent_fact(fact_text: str, metadata: dict | None = None) -> list[str]:
    return jarvis_memory.store_permanent_fact(fact_text, metadata)


def recall_relevant_facts(query_text: str, n_results: int = 3) -> list[dict]:
    return jarvis_memory.recall_relevant_facts(query_text, n_results)


def load_memory() -> dict:
    return jarvis_memory.load_memory()


def update_memory(memory_update: dict) -> dict:
    return jarvis_memory.update_memory(memory_update)


def format_memory_for_prompt(memory: dict | None) -> str:
    if not memory:
        return ""

    if "facts" in memory:
        facts = memory.get("facts", [])
        if not facts:
            return ""

        lines = ["[LONG-TERM MEMORY — use naturally, never recite like a list]"]
        for fact in facts[:10]:
            content = str(fact.get("content", "")).strip()
            if not content:
                continue
            metadata = fact.get("metadata") or {}
            metadata_text = ""
            if metadata:
                metadata_pairs = [f"{k}={v}" for k, v in metadata.items() if v is not None]
                if metadata_pairs:
                    metadata_text = f" ({', '.join(metadata_pairs)})"
            lines.append(f"- {content}{metadata_text}")

        return "\n".join(lines) + "\n"

    # Legacy fallback for older category-based memory shape
    legacy_fields = ["identity", "preferences", "projects", "relationships", "wishes", "notes"]
    if any(isinstance(memory.get(field), dict) for field in legacy_fields):
        lines = []

        identity = memory.get("identity", {})
        if isinstance(identity, dict):
            id_fields = ["name", "age", "birthday", "city", "job", "language", "school", "nationality"]
            for field in id_fields:
                entry = identity.get(field)
                if entry:
                    val = entry.get("value") if isinstance(entry, dict) else entry
                    if val:
                        lines.append(f"{field.title()}: {val}")
            for key, entry in identity.items():
                if key in id_fields:
                    continue
                val = entry.get("value") if isinstance(entry, dict) else entry
                if val:
                    lines.append(f"{key.replace('_', ' ').title()}: {val}")

        prefs = memory.get("preferences", {})
        if isinstance(prefs, dict) and prefs:
            lines.append("")
            lines.append("Preferences:")
            for key, entry in list(prefs.items())[:15]:
                val = entry.get("value") if isinstance(entry, dict) else entry
                if val:
                    lines.append(f"  - {key.replace('_', ' ').title()}: {val}")

        projects = memory.get("projects", {})
        if isinstance(projects, dict) and projects:
            lines.append("")
            lines.append("Active Projects / Goals:")
            for key, entry in list(projects.items())[:8]:
                val = entry.get("value") if isinstance(entry, dict) else entry
                if val:
                    lines.append(f"  - {key.replace('_', ' ').title()}: {val}")

        rels = memory.get("relationships", {})
        if isinstance(rels, dict) and rels:
            lines.append("")
            lines.append("People in their life:")
            for key, entry in list(rels.items())[:10]:
                val = entry.get("value") if isinstance(entry, dict) else entry
                if val:
                    lines.append(f"  - {key.replace('_', ' ').title()}: {val}")

        wishes = memory.get("wishes", {})
        if isinstance(wishes, dict) and wishes:
            lines.append("")
            lines.append("Wishes / Plans / Wants:")
            for key, entry in list(wishes.items())[:8]:
                val = entry.get("value") if isinstance(entry, dict) else entry
                if val:
                    lines.append(f"  - {key.replace('_', ' ').title()}: {val}")

        notes = memory.get("notes", {})
        if isinstance(notes, dict) and notes:
            lines.append("")
            lines.append("Other notes:")
            for key, entry in list(notes.items())[:8]:
                val = entry.get("value") if isinstance(entry, dict) else entry
                if val:
                    lines.append(f"  - {key}: {val}")

        if not lines:
            return ""

        header = "[WHAT YOU KNOW ABOUT THIS PERSON — use naturally, never recite like a list]\n"
        result = header + "\n".join(lines)
        if len(result) > 2000:
            result = result[:1997] + "…"
        return result + "\n"

    return ""


def should_extract_memory(user_text: str, jarvis_text: str, api_key: str = "") -> bool:
    try:
        from or_client import client

        combined = f"User: {user_text[:300]}\nJarvis: {jarvis_text[:1000]}"

        result = client.chat(
            f"Does the following dialogue contain any long-term memorable facts about the user?\n"
            f"Memorable facts include: personal descriptors (identity, occupation, location), preferences/favorites, "
            f"active projects/tasks, relationships, future plans/wishes, or habits.\n\n"
            f"Dialogue:\n{combined}\n\n"
            f"Reply ONLY with 'YES' if memorable facts are present, or 'NO' if the conversation is purely transactional or transient.",
            system="You are a binary classification filter. Respond ONLY with YES or NO.",
            max_tokens=5,
            temperature=0.0,
        )
        result_upper = result.upper().strip()
        # Handle various LLM response formats
        if "YES" in result_upper:
            return True
        if result_upper.startswith("NO") or "NO," in result_upper or result_upper == "NO":
            return False
        # If response is ambiguous, fall back to heuristic
        print(f"[Jarvis Memory] [INFO] LLM response ambiguous ({result[:50]}), using heuristic fallback")
        return _should_extract_memory_heuristic(user_text, jarvis_text)

    except ImportError:
        # or_client not available - fallback to simple heuristic
        print("[Jarvis Memory] [INFO] or_client not available - using heuristic fallback")  # Jarvis: using simplified memory check
        return _should_extract_memory_heuristic(user_text, jarvis_text)
    except Exception as exc:
        print(f"[Jarvis Memory] [WARN] Stage1 check failed: {exc}")  # Jarvis: memory relevance detection failed
        return _should_extract_memory_heuristic(user_text, jarvis_text)


def _should_extract_memory_heuristic(user_text: str, jarvis_text: str) -> bool:
    """
    Fallback heuristic for memory extraction when or_client is not available.
    Uses simple keyword matching to determine if a conversation contains
    long-term memorable facts.
    """
    # Keywords indicating personal information that should be remembered
    identity_keywords = ["name", "i'm", "i am", "call me", "my name", "i'm called"]
    preference_keywords = ["like", "love", "prefer", "favorite", "hate", "enjoy", "don't like"]
    project_keywords = ["working on", "building", "creating", "developing", "project", "code"]
    relationship_keywords = ["friend", "family", "mother", "father", "sister", "brother", "wife", "husband", "girlfriend", "boyfriend"]
    wish_keywords = ["want", "wish", "hope", "dream", "plan", "visit", "travel to", "buy"]

    combined_lower = (user_text + " " + jarvis_text).lower()

    # Check for identity indicators
    if any(kw in combined_lower for kw in identity_keywords):
        return True

    # Check for preference indicators
    if any(kw in combined_lower for kw in preference_keywords):
        return True

    # Check for project/work indicators
    if any(kw in combined_lower for kw in project_keywords):
        return True

    # Check for relationship indicators
    if any(kw in combined_lower for kw in relationship_keywords):
        return True

    # Check for wish/planning indicators
    if any(kw in combined_lower for kw in wish_keywords):
        return True

    # Default: don't extract if no clear signals
    return False


def extract_memory(user_text: str, jarvis_text: str, api_key: str = "") -> dict:
    try:
        from or_client import client

        combined = f"User: {user_text[:600]}\nJarvis: {jarvis_text[:300]}"

        raw = client.chat(
            f"Extract all long-term memorable facts from this dialogue. Supports any language inputs, but output values in English.\n"
            f"Return ONLY a valid JSON object. Return {{}} if no relevant information is present.\n\n"
            f"## CATEGORY GUIDE:\n"
            f"  - identity: personal descriptors (e.g., name, age, city, occupation, nationality)\n"
            f"  - preferences: preferred/disliked items (e.g., favorite_food, favorite_music, hobbies)\n"
            f"  - projects: active work, software engineering, tasks, ideas in progress (e.g., mark_xxv: 'Building JARVIS AI')\n"
            f"  - relationships: named or described acquaintances, family, friends, colleagues (e.g., colleague_bob: 'Lead dev')\n"
            f"  - wishes: future plans, destinations to travel, items to buy, dreams\n"
            f"  - notes: habits, daily schedule, general observations worth saving\n\n"
            f"## EXTRACTION PROTOCOL:\n"
            f"- Be comprehensive and liberal: capture any detail that builds personalization.\n"
            f"- Analyze both user statements and assistant declarations.\n"
            f"- Ignore transient tasks (weather requests, search results, immediate shell commands, etc.).\n"
            f"- Output concise, descriptive values in English.\n\n"
            f"## JSON CONTRACT FORMAT:\n"
            f'{{"identity":{{"name":{{"value":"Ali"}}}},\n'
            f' "preferences":{{"favorite_color":{{"value":"blue"}}}},\n'
            f' "projects":{{"mark_xxv":{{"value":"JARVIS-like AI assistant"}}}},\n'
            f' "relationships":{{"friend_yusuf":{{"value":"close friend"}}}},\n'
            f' "wishes":{{"buy_guitar":{{"value":"wants an acoustic guitar"}}}},\n'
            f' "notes":{{"works_at_night":{{"value":"usually active late at night"}}}}}}\n\n'
            f"Dialogue Content:\n{combined}\n\nJSON:",
            system="Return ONLY a valid JSON object. Do not include markdown code fences, do not use backticks, and provide no explanations.",
            max_tokens=1024,
            temperature=0.2,
        )

        clean = raw.strip()
        clean = re.sub(r"```(?:json)?", "", clean).strip().rstrip("`").strip()

        if not clean or clean == "{}":
            return {}

        return json.loads(clean)

    except ImportError:
        # or_client not available - or heuristic already rejected, return empty
        return {}
    except json.JSONDecodeError:
        return {}
    except Exception as exc:
        if "429" not in str(exc):
            print(f"[Jarvis Memory] [WARN] Extract failed: {exc}")  # Jarvis: extraction failed
        return {}
