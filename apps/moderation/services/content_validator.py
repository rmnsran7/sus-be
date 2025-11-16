# speakUPsurrey/ssb/apps/moderation/services/content_validator.py

import os
import json
import requests
from dataclasses import dataclass, asdict
from django.core.cache import cache
from apps.core.models import BlockedWord
from decouple import config

# Cerebras API Configuration
CEREBRAS_API_URL = "https://api.cerebras.ai/v1/chat/completions"
CEREBRAS_API_KEY = config("CEREBRAS_API_KEY", default="")

# --- STEP 1: MODIFY THE LLMAnalysisResult CLASS ---
@dataclass
class LLMAnalysisResult:
    """A structured class to hold results from the LLM analysis."""
    is_spam: bool = False
    is_harmful: bool = False
    is_promotional: bool = False
    summary: str = ""
    raw_data: dict | None = None  # raw API response for auditing

    def to_dict(self):
        return asdict(self)


def check_for_blocked_words(text: str) -> bool:
    """
    Checks if the given text contains any blocked words from the database.
    Uses caching for performance.
    """
    cache_key = 'blocked_words_set'
    blocked_words = cache.get(cache_key)
    if blocked_words is None:
        blocked_words = set(BlockedWord.objects.values_list('word', flat=True))
        cache.set(cache_key, blocked_words, timeout=3600)

    text_lower = text.lower()
    for word in blocked_words:
        if word in text_lower:
            return True
    return False


# --- STEP 2: UPDATED analyze_with_llm FUNCTION ---
def analyze_with_llm(text: str) -> LLMAnalysisResult:
    """
    Sends text to the Cerebras LLM for analysis and returns a structured result.
    This version disables model reasoning and captures the raw API response.
    """
    if not CEREBRAS_API_KEY:
        print("Error: CEREBRAS_API_KEY not set. Skipping LLM analysis.")
        error_data = {"error": "API key not configured."}
        return LLMAnalysisResult(summary="LLM analysis skipped.", raw_data=error_data)

    # Strong system message forbidding chain-of-thought and requiring strict JSON only.
    system_prompt = (
        "You are a content quality reviewer. Do NOT produce any internal chain-of-thought or reasoning text. "
        "Input can be in english, punjabi or hindi language"
        "Remeber that selling anything is not spam. People can sell their own items. dont mark selling as spam. it should be marked as promotional only."
        "Do NOT include intermediate steps, deliberation, or any <think> / <reason> tags. "
        "Return ONLY a single valid JSON object (no surrounding text, no markdown code fences). "
        "The JSON object must contain these keys: "
        "'is_spam' (boolean), 'is_harmful' (boolean), 'is_promotional' (boolean), "
        "'summary' (string, max 20 words)."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text}
    ]

    # JSON Schema to enforce structured output (optional but helps enforce machine-parseable output).
    # If your account or model tier does not support structured outputs, you may remove response_format.
    json_schema = {
        "type": "object",
        "properties": {
            "is_spam": {"type": "boolean"},
            "is_harmful": {"type": "boolean"},
            "is_promotional": {"type": "boolean"},
            "summary": {"type": "string"}
        },
        "required": ["is_spam", "is_harmful", "is_promotional", "summary"],
        "additionalProperties": False
    }

    payload = {
        "model": "llama-3.3-70b",          # use OpenAI-OSS model on Cerebras
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": 150
    }

    headers = {"Authorization": f"Bearer {CEREBRAS_API_KEY}", "Content-Type": "application/json"}

    try:
        response = requests.post(CEREBRAS_API_URL, headers=headers, json=payload, timeout=5.0)
        response.raise_for_status()

        # Capture the raw full response immediately for auditing/storage.
        api_response_json = response.json()

        # Extract model message content in a robust way.
        message_content = None
        try:
            message_content = api_response_json["choices"][0]["message"]["content"]
        except Exception:
            # Some variants of the API may put the text in choices[0]["text"]
            message_content = api_response_json["choices"][0].get("text") if "choices" in api_response_json and api_response_json["choices"] else None

        if not message_content:
            raise ValueError("No message content returned by LLM.")

        # Clean and parse JSON. Find the JSON object even if it's surrounded by text.
        cleaned_text = message_content.strip()

        # Find the first '{'
        json_start = cleaned_text.find('{')
        # Find the last '}'
        json_end = cleaned_text.rfind('}')

        if json_start == -1 or json_end == -1 or json_end < json_start:
            raise ValueError(f"Could not find valid JSON object in LLM response: {cleaned_text}")

        # Extract the JSON string
        json_string = cleaned_text[json_start:json_end+1]

        # Parse the extracted string
        result_json = json.loads(json_string)

        # Validate types explicitly
        if not all(isinstance(result_json.get(key), bool) for key in ['is_spam', 'is_harmful', 'is_promotional']):
            raise ValueError("LLM response JSON missing required boolean keys or wrong types.")
        if not isinstance(result_json.get('summary'), str):
            raise ValueError("LLM response JSON 'summary' is not a string.")

        return LLMAnalysisResult(
            is_spam=result_json.get('is_spam', False),
            is_harmful=result_json.get('is_harmful', False),
            is_promotional=result_json.get('is_promotional', False),
            summary=result_json.get('summary', "Summary not provided."),
            raw_data=api_response_json
        )

    except requests.exceptions.Timeout:
        print("LLM analysis failed: API request timed out.")
        error_data = {"error": "API request timed out."}
        return LLMAnalysisResult(summary="LLM check timed out.", raw_data=error_data)

    except requests.exceptions.RequestException as e:
        print(f"LLM analysis failed: API error: {e}")
        error_data = {"error": str(e), "status_code": e.response.status_code if e.response else None}
        return LLMAnalysisResult(summary="LLM check failed due to API error.", raw_data=error_data)

    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        print(f"LLM analysis failed: Could not parse or validate LLM response: {e}")
        error_data = {"error": "Could not parse or validate LLM response.", "response_text": ""}
        if 'response' in locals() and response.text:
            error_data["response_text"] = response.text
        return LLMAnalysisResult(summary="LLM check failed due to response format.", raw_data=error_data)

    except Exception as e:
        print(f"LLM analysis failed: An unexpected error occurred: {e}")
        error_data = {"error": "An unexpected error occurred.", "detail": str(e)}
        return LLMAnalysisResult(summary="LLM check failed due to unexpected error.", raw_data=error_data)