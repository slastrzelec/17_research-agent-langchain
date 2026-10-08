"""Scripted chat model: lets tests drive the real agent graph without any API."""
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class ScriptedChatModel(BaseChatModel):
    script: list  # list of AIMessage, consumed in order (the last one repeats)
    calls: int = 0

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        msg = self.script[min(self.calls, len(self.script) - 1)]
        msg = msg.model_copy(update={"id": None})  # fresh message each turn (repeats must not share ids)
        self.calls += 1
        return ChatResult(generations=[ChatGeneration(message=msg)])


def tool_call_msg(name, args, tokens=100, call_id="c1"):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}],
                     usage_metadata={"input_tokens": tokens - 10, "output_tokens": 10,
                                     "total_tokens": tokens})


def answer_msg(text, tokens=50):
    return AIMessage(content=text, usage_metadata={"input_tokens": tokens - 5,
                                                    "output_tokens": 5, "total_tokens": tokens})
