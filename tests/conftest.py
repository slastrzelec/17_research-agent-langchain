import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.dirname(__file__))
# Tests must never trace to LangFuse or use a real key from a developer's .env:
# load_dotenv() does not override variables that are already set.
os.environ["LANGFUSE_PUBLIC_KEY"] = ""
os.environ["LANGFUSE_SECRET_KEY"] = ""
os.environ["LANGFUSE_TRACING_ENABLED"] = "false"
os.environ["OPENAI_API_KEY"] = "sk-test-not-a-real-key"
