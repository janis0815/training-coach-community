import logging
from groq import Groq, RateLimitError, APIError
from database import load_conversation_history, save_conversation_messages, clear_conversation_history

logger = logging.getLogger(__name__)

MODEL_FULL = "llama-3.3-70b-versatile"
MODEL_LIGHT = "llama-3.1-8b-instant"


class CoachAI:
    def __init__(self, api_key: str):
        self.client = Groq(api_key=api_key)
        self.conversations: dict[int, list[dict]] = {}

    def _get_history(self, chat_id: int) -> list[dict]:
        if chat_id not in self.conversations:
            # Aus DB laden beim ersten Zugriff
            self.conversations[chat_id] = load_conversation_history(chat_id)
        return self.conversations[chat_id]

    def _trim_history(self, history: list[dict], limit: int):
        while len(history) > limit:
            history.pop(0)

    def _persist(self, chat_id: int):
        """Speichert die aktuelle History in die DB."""
        if chat_id in self.conversations:
            save_conversation_messages(chat_id, self.conversations[chat_id])

    def chat(self, chat_id: int, user_message: str, system_prompt: str, use_full_model: bool = False) -> str:
        history = self._get_history(chat_id)

        if use_full_model:
            self._trim_history(history, 20)
            model = MODEL_FULL
            max_tokens = 4000
        else:
            self._trim_history(history, 10)
            model = MODEL_LIGHT
            max_tokens = 800

        messages = [
            {"role": "system", "content": system_prompt},
            *[{"role": msg["role"], "content": msg["content"]} for msg in history],
            {"role": "user", "content": user_message},
        ]

        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=max_tokens,
            )
            reply = response.choices[0].message.content

        except RateLimitError:
            logger.warning(f"Rate Limit für chat_id {chat_id}")
            return "⏳ Rate Limit erreicht. Versuch es in 1-2 Minuten nochmal!"
        except APIError as e:
            logger.error(f"Groq API Fehler: {e}")
            return "❌ Da ist etwas schiefgelaufen. Versuch es nochmal!"

        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": reply})
        self._persist(chat_id)
        return reply

    def reset(self, chat_id: int):
        self.conversations.pop(chat_id, None)
        clear_conversation_history(chat_id)
