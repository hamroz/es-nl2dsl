#!/usr/bin/env python3
"""
External LLM Manager for integrating OpenAI, Google, DeepSeek, and Qwen AI.
- Supports latest OpenAI models including GPT-4o and mini variants.
- Backwards compatible with legacy openai 0.x SDKs.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class ExternalLLM:
    """Configuration for an external LLM"""
    name: str
    provider: str  # "openai", "google", "deepseek", "qwen", etc.
    model_id: str  # e.g., "gpt-4o", "gemini-2.5-pro", "qwen-max"
    api_key: str
    endpoint: Optional[str] = None  # Optional custom endpoint / base_url (OpenAI-compatible)
    max_tokens: int = 2000
    temperature: float = 0.7
    enabled: bool = True
    added_date: str = ""

    def __post_init__(self):
        if not self.added_date:
            self.added_date = datetime.now().isoformat()


def _make_openai_client(api_key: str, base_url: Optional[str] = None):
    """
    Returns (client, is_new_sdk).
    - New SDK (>=1.x): `from openai import OpenAI`; client = OpenAI(api_key=..., base_url=...)
    - Legacy SDK (0.x): `import openai`; set globals; return module; is_new_sdk=False
    """
    try:
        # Try new SDK
        from openai import OpenAI  # type: ignore
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        return OpenAI(**kwargs), True
    except Exception:
        # Fallback to legacy SDK
        import openai as openai_legacy  # type: ignore
        openai_legacy.api_key = api_key
        if base_url:
            # legacy uses api_base instead of base_url
            setattr(openai_legacy, "api_base", base_url)
        return openai_legacy, False


def _extract_responses_text(resp: Any) -> str:
    """
    Best-effort extraction of text from OpenAI Responses API payloads.
    Prefers `resp.output_text` (new SDK), with a few safe fallbacks.
    """
    text = getattr(resp, "output_text", None)
    if isinstance(text, str) and text.strip():
        return text

    # Fallbacks for odd shapes (should rarely be needed)
    for attr in ("text",):
        t = getattr(resp, attr, None)
        if isinstance(t, str) and t.strip():
            return t

    # Last-ditch: try to read from dict-like outputs
    try:
        if hasattr(resp, "output") and resp.output:
            # new SDK usually has segments with .content[0].text
            seg = resp.output[0]
            content = getattr(seg, "content", None)
            if content and isinstance(content, list):
                t = getattr(content[0], "text", None)
                if isinstance(t, str) and t.strip():
                    return t
    except Exception:
        pass

    return ""


def _chat_tokens_kwargs(is_new_sdk: bool, model_id: str, n: int) -> dict:
    """
    Decide which token limit kwarg to use for Chat Completions.
    Some newer models (e.g., GPT-5 family via chat API) require 'max_completion_tokens'.
    Legacy/older models still use 'max_tokens'.
    """
    if is_new_sdk and (model_id.startswith(("gpt-5", "o4", "o3", "o1"))):
        return {"max_completion_tokens": n}
    return {"max_tokens": n}


def _try_responses_with_tokens(client, model_id: str, payload: dict, primary_key: str, fallback_key: str):
    """
    Call client.responses.create with primary token key first,
    then retry once swapping to the fallback key if the server says the param is unsupported.
    Does not mutate the original payload and ensures only one token key is sent per attempt.
    """
    base_payload = dict(payload)
    primary_value = base_payload.pop(primary_key, None)
    fallback_value = base_payload.pop(fallback_key, None)

    # 1st try with primary
    try:
        kwargs = dict(base_payload)
        if primary_value is not None:
            kwargs[primary_key] = primary_value
        return client.responses.create(model=model_id, **kwargs)
    except Exception as e:
        msg = str(e)
        if f"Unsupported parameter: '{primary_key}'" not in msg:
            raise

    # 2nd try with fallback
    kwargs = dict(base_payload)
    if fallback_value is not None:
        kwargs[fallback_key] = fallback_value
    return client.responses.create(model=model_id, **kwargs)


class ExternalLLMManager:
    """Manage external LLM configurations"""

    def __init__(self, config_file: str = "artifacts/external_llms.json"):
        self.config_file = Path(config_file)
        self.llms: Dict[str, ExternalLLM] = {}
        self.last_error: Optional[str] = None  # surface the last exception to the UI
        self.load_config()

    def load_config(self):
        """Load LLM configurations from file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    for name, config in data.items():
                        self.llms[name] = ExternalLLM(**config)
            except Exception as e:
                print(f"Error loading LLM config: {e}")
                self.last_error = str(e)
                self.llms = {}
        else:
            # Create default config
            self.llms = {}
            self.save_config()

    def save_config(self):
        """Save LLM configurations to file"""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        data = {name: asdict(llm) for name, llm in self.llms.items()}
        with open(self.config_file, 'w') as f:
            json.dump(data, f, indent=2)

    def add_llm(self, llm: ExternalLLM) -> bool:
        """Add or update an LLM configuration"""
        self.last_error = None
        try:
            if self.validate_llm(llm):
                self.llms[llm.name] = llm
                self.save_config()
                return True
            return False
        except Exception as e:
            self.last_error = str(e)
            print(f"Error adding LLM: {e}")
            return False

    def remove_llm(self, name: str) -> bool:
        """Remove an LLM configuration"""
        if name in self.llms:
            del self.llms[name]
            self.save_config()
            return True
        return False

    def get_llm(self, name: str) -> Optional[ExternalLLM]:
        """Get an LLM configuration by name"""
        return self.llms.get(name)

    def list_llms(self, enabled_only: bool = False) -> List[ExternalLLM]:
        """List all LLM configurations"""
        llms = list(self.llms.values())
        if enabled_only:
            llms = [llm for llm in llms if llm.enabled]
        return llms

    def validate_llm(self, llm: ExternalLLM) -> bool:
        """Validate LLM configuration by making a test call"""
        self.last_error = None
        try:
            if llm.provider == "openai":
                client, is_new = _make_openai_client(llm.api_key, llm.endpoint)
                test_text = None

                if is_new:
                    # Prefer Responses API (GPT-5 path). Try max_output_tokens, retry with max_completion_tokens if needed.
                    try:
                        payload = {
                            "input": "Say 'test'",
                            "max_output_tokens": 64,
                            "max_completion_tokens": 64,  # present for fallback
                        }
                        resp = _try_responses_with_tokens(
                            client,
                            llm.model_id,
                            payload,
                            primary_key="max_output_tokens",
                            fallback_key="max_completion_tokens",
                        )
                        test_text = _extract_responses_text(resp)
                        # Treat successful call with no text (e.g., status=incomplete due to token cap) as valid
                        if not test_text:
                            return True
                    except Exception:
                        # Fallback to Chat Completions (new SDK)
                        kwargs = _chat_tokens_kwargs(True, llm.model_id, 16)
                        resp = client.chat.completions.create(
                            model=llm.model_id,
                            messages=[{"role": "user", "content": "Say 'test'"}],
                            **kwargs,
                        )
                        test_text = resp.choices[0].message.content or ""
                else:
                    # Legacy SDK (0.x) – ChatCompletion with classic max_tokens
                    resp = client.ChatCompletion.create(
                        model=llm.model_id,
                        messages=[{"role": "user", "content": "Say 'test'"}],
                        max_tokens=8,
                    )
                    test_text = resp["choices"][0]["message"]["content"] or ""

                return bool(test_text and test_text.strip())

            elif llm.provider == "google":
                try:
                    import google.generativeai as genai
                except Exception as e:
                    self.last_error = f"google-generativeai not installed: {e}"
                    return False
                genai.configure(api_key=llm.api_key)
                model = genai.GenerativeModel(model_name=llm.model_id)
                response = model.generate_content("Say test")
                txt = getattr(response, "text", "") or ""
                return bool(txt.strip() or getattr(response, "candidates", []))

            elif llm.provider == "deepseek":
                # OpenAI-compatible; use Chat Completions against base_url
                base = llm.endpoint or "https://api.deepseek.com/v1"
                client, is_new = _make_openai_client(llm.api_key, base_url=base)
                if is_new:
                    resp = client.chat.completions.create(
                        model=llm.model_id,
                        messages=[{"role": "user", "content": "Say 'test'"}],
                        max_tokens=8,
                    )
                    return bool(resp.choices)
                else:
                    resp = client.ChatCompletion.create(
                        model=llm.model_id,
                        messages=[{"role": "user", "content": "Say 'test'"}],
                        max_tokens=8,
                    )
                    return bool(resp["choices"])

            elif llm.provider == "qwen":
                # Qwen uses OpenAI-compatible API
                base = llm.endpoint or "https://dashscope.aliyuncs.com/compatible-mode/v1"
                client, is_new = _make_openai_client(llm.api_key, base_url=base)
                if is_new:
                    resp = client.chat.completions.create(
                        model=llm.model_id,
                        messages=[{"role": "user", "content": "Say 'test'"}],
                        max_tokens=8,
                    )
                    return bool(resp.choices)
                else:
                    resp = client.ChatCompletion.create(
                        model=llm.model_id,
                        messages=[{"role": "user", "content": "Say 'test'"}],
                        max_tokens=8,
                    )
                    return bool(resp["choices"])

            else:
                # Unknown provider: basic sanity check
                return bool(llm.api_key)

        except Exception as e:
            self.last_error = str(e)
            print(f"Validation failed for {llm.name}: {e}")
            return False

    def call_llm(self, name: str, prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
        """Call an external LLM with a prompt"""
        llm = self.get_llm(name)
        if not llm or not llm.enabled:
            return None

        try:
            if llm.provider == "openai":
                client, is_new = _make_openai_client(llm.api_key, llm.endpoint)

                if is_new:
                    # Prefer Responses API (GPT-5 best path)
                    try:
                        msgs = []
                        if system_prompt:
                            msgs.append({"role": "system", "content": system_prompt})
                        msgs.append({"role": "user", "content": prompt})

                        payload = {
                            "input": msgs,
                            "temperature": llm.temperature,
                            "max_output_tokens": llm.max_tokens,
                            "max_completion_tokens": llm.max_tokens,  # present for fallback
                        }
                        resp = _try_responses_with_tokens(
                            client,
                            llm.model_id,
                            payload,
                            primary_key="max_output_tokens",
                            fallback_key="max_completion_tokens",
                        )
                        out = _extract_responses_text(resp)
                        if out:
                            return out
                    except Exception:
                        # Fallback to Chat Completions (new SDK) – choose token kwarg adaptively
                        messages = []
                        if system_prompt:
                            messages.append({"role": "system", "content": system_prompt})
                        messages.append({"role": "user", "content": prompt})

                        kwargs = _chat_tokens_kwargs(True, llm.model_id, llm.max_tokens)
                        resp = client.chat.completions.create(
                            model=llm.model_id,
                            messages=messages,
                            temperature=llm.temperature,
                            **kwargs,
                        )
                        return resp.choices[0].message.content
                else:
                    # Legacy SDK (0.x) – ChatCompletion with classic max_tokens
                    messages = []
                    if system_prompt:
                        messages.append({"role": "system", "content": system_prompt})
                    messages.append({"role": "user", "content": prompt})

                    resp = client.ChatCompletion.create(
                        model=llm.model_id,
                        messages=messages,
                        max_tokens=llm.max_tokens,
                        temperature=llm.temperature,
                    )
                    return resp["choices"][0]["message"]["content"]

            elif llm.provider == "google":
                import google.generativeai as genai
                genai.configure(api_key=llm.api_key)
                model = genai.GenerativeModel(
                    model_name=llm.model_id,
                    system_instruction=system_prompt if system_prompt else None,
                )
                response = model.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(
                        max_output_tokens=llm.max_tokens,
                        temperature=llm.temperature,
                    ),
                )
                return getattr(response, "text", None)

            elif llm.provider == "deepseek":
                base = llm.endpoint or "https://api.deepseek.com/v1"
                client, is_new = _make_openai_client(llm.api_key, base_url=base)
                messages: List[Dict[str, str]] = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                if is_new:
                    resp = client.chat.completions.create(
                        model=llm.model_id,
                        messages=messages,
                        max_tokens=llm.max_tokens,
                        temperature=llm.temperature,
                    )
                    return resp.choices[0].message.content
                else:
                    resp = client.ChatCompletion.create(
                        model=llm.model_id,
                        messages=messages,
                        max_tokens=llm.max_tokens,
                        temperature=llm.temperature,
                    )
                    return resp["choices"][0]["message"]["content"]

            elif llm.provider == "qwen":
                base = llm.endpoint or "https://dashscope.aliyuncs.com/compatible-mode/v1"
                client, is_new = _make_openai_client(llm.api_key, base_url=base)
                messages: List[Dict[str, str]] = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                if is_new:
                    resp = client.chat.completions.create(
                        model=llm.model_id,
                        messages=messages,
                        max_tokens=llm.max_tokens,
                        temperature=llm.temperature,
                    )
                    return resp.choices[0].message.content
                else:
                    resp = client.ChatCompletion.create(
                        model=llm.model_id,
                        messages=messages,
                        max_tokens=llm.max_tokens,
                        temperature=llm.temperature,
                    )
                    return resp["choices"][0]["message"]["content"]

            else:
                print(f"Unknown provider: {llm.provider}")
                return None

        except Exception as e:
            self.last_error = str(e)
            print(f"Error calling {name}: {e}")
            return None

    def get_available_models(self) -> Dict[str, List[str]]:
        """Get list of available models for each provider"""
        return {
            "openai": [
                "gpt-4o",          # Latest GPT-4o model
                "gpt-4o-mini",     # Smaller, faster GPT-4o variant
                "gpt-4-turbo",     # GPT-4 Turbo
                "o1",              # OpenAI o1 reasoning model
                "o1-mini",         # Smaller o1 variant
                "o3-mini",         # Latest o3 mini model
            ],
            "google": [
                "gemini-2.5-pro",
                "gemini-2.5-flash",
                "gemini-2.0-flash-thinking-exp",
                "gemini-1.5-pro",
                "gemini-1.5-flash",
            ],
            "deepseek": [
                "deepseek-reasoner",  # R1-style reasoner
                "deepseek-chat",      # Standard chat model
                "deepseek-coder",     # Code-focused model
            ],
            "qwen": [
                "qwen-max",          # Largest Qwen model
                "qwen-plus",         # Medium Qwen model
                "qwen-turbo",        # Fast Qwen model
                "qwen-long",         # Long context Qwen model
                "qwen2.5-coder-32b-instruct",  # Coding model
            ],
        }

    def update_llm_status(self, name: str, enabled: bool) -> bool:
        """Enable or disable an LLM"""
        if name in self.llms:
            self.llms[name].enabled = enabled
            self.save_config()
            return True
        return False


# Singleton instance
_manager_instance = None

def get_external_llm_manager() -> ExternalLLMManager:
    """Get singleton instance of ExternalLLMManager"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = ExternalLLMManager()
    return _manager_instance