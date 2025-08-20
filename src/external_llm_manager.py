#!/usr/bin/env python3
"""
External LLM Manager for integrating Claude, OpenAI, and other AI models
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import openai
import anthropic
from datetime import datetime

@dataclass
class ExternalLLM:
    """Configuration for an external LLM"""
    name: str
    provider: str  # openai, anthropic, cohere, etc.
    model_id: str  # gpt-4, claude-3-opus, etc.
    api_key: str
    endpoint: Optional[str] = None  # Optional custom endpoint
    max_tokens: int = 2000
    temperature: float = 0.7
    enabled: bool = True
    added_date: str = ""
    
    def __post_init__(self):
        if not self.added_date:
            self.added_date = datetime.now().isoformat()

class ExternalLLMManager:
    """Manage external LLM configurations"""
    
    def __init__(self, config_file: str = "artifacts/external_llms.json"):
        self.config_file = Path(config_file)
        self.llms: Dict[str, ExternalLLM] = {}
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
        try:
            # Validate API key by making a test call
            if self.validate_llm(llm):
                self.llms[llm.name] = llm
                self.save_config()
                return True
            return False
        except Exception as e:
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
        try:
            if llm.provider == "openai":
                client = openai.OpenAI(api_key=llm.api_key)
                # Test with a simple completion
                response = client.chat.completions.create(
                    model=llm.model_id,
                    messages=[{"role": "user", "content": "Say 'test'"}],
                    max_tokens=5
                )
                return bool(response.choices)
            
            elif llm.provider == "anthropic":
                client = anthropic.Anthropic(api_key=llm.api_key)
                # Test with a simple message
                response = client.messages.create(
                    model=llm.model_id,
                    max_tokens=5,
                    messages=[{"role": "user", "content": "Say 'test'"}]
                )
                return bool(response.content)
            
            elif llm.provider == "google":
                try:
                    import google.generativeai as genai
                    genai.configure(api_key=llm.api_key)
                    model = genai.GenerativeModel(llm.model_id)
                    response = model.generate_content("Say test")
                    return bool(response.text)
                except:
                    return False
            
            elif llm.provider == "deepseek":
                # DeepSeek uses OpenAI-compatible API
                client = openai.OpenAI(
                    api_key=llm.api_key,
                    base_url="https://api.deepseek.com/v1"
                )
                response = client.chat.completions.create(
                    model=llm.model_id,
                    messages=[{"role": "user", "content": "Say 'test'"}],
                    max_tokens=5
                )
                return bool(response.choices)
            
            elif llm.provider == "cohere":
                import cohere
                client = cohere.Client(llm.api_key)
                response = client.generate(
                    model=llm.model_id if llm.model_id else 'command',
                    prompt="Say test",
                    max_tokens=5
                )
                return bool(response.generations)
            
            else:
                # For unknown providers, assume valid if API key is provided
                return bool(llm.api_key)
                
        except Exception as e:
            print(f"Validation failed for {llm.name}: {e}")
            return False
    
    def call_llm(self, name: str, prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
        """Call an external LLM with a prompt"""
        llm = self.get_llm(name)
        if not llm or not llm.enabled:
            return None
        
        try:
            if llm.provider == "openai":
                client = openai.OpenAI(api_key=llm.api_key)
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})
                
                response = client.chat.completions.create(
                    model=llm.model_id,
                    messages=messages,
                    max_tokens=llm.max_tokens,
                    temperature=llm.temperature
                )
                return response.choices[0].message.content
            
            elif llm.provider == "anthropic":
                client = anthropic.Anthropic(api_key=llm.api_key)
                
                # Prepare messages
                messages = [{"role": "user", "content": prompt}]
                
                # Add system prompt if provided
                system = system_prompt if system_prompt else None
                
                response = client.messages.create(
                    model=llm.model_id,
                    max_tokens=llm.max_tokens,
                    temperature=llm.temperature,
                    system=system,
                    messages=messages
                )
                
                # Extract text from response
                if response.content:
                    return response.content[0].text
                return None
            
            elif llm.provider == "google":
                try:
                    import google.generativeai as genai
                    genai.configure(api_key=llm.api_key)
                    
                    # Create model
                    model = genai.GenerativeModel(
                        llm.model_id,
                        system_instruction=system_prompt if system_prompt else None
                    )
                    
                    # Generate response
                    response = model.generate_content(
                        prompt,
                        generation_config=genai.GenerationConfig(
                            max_output_tokens=llm.max_tokens,
                            temperature=llm.temperature
                        )
                    )
                    
                    return response.text if response else None
                except Exception as e:
                    print(f"Error calling Google Gemini: {e}")
                    return None
            
            elif llm.provider == "deepseek":
                # DeepSeek uses OpenAI-compatible API
                client = openai.OpenAI(
                    api_key=llm.api_key,
                    base_url="https://api.deepseek.com/v1"
                )
                
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})
                
                response = client.chat.completions.create(
                    model=llm.model_id,
                    messages=messages,
                    max_tokens=llm.max_tokens,
                    temperature=llm.temperature
                )
                return response.choices[0].message.content
            
            elif llm.provider == "cohere":
                import cohere
                client = cohere.Client(llm.api_key)
                
                # Combine system prompt with user prompt if provided
                full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
                
                response = client.generate(
                    model=llm.model_id if llm.model_id else 'command',
                    prompt=full_prompt,
                    max_tokens=llm.max_tokens,
                    temperature=llm.temperature
                )
                
                if response.generations:
                    return response.generations[0].text
                return None
            
            else:
                print(f"Unknown provider: {llm.provider}")
                return None
                
        except Exception as e:
            print(f"Error calling {name}: {e}")
            return None
    
    def get_available_models(self) -> Dict[str, List[str]]:
        """Get list of available models for each provider"""
        return {
            "openai": [
                "gpt-5",  # GPT-5 flagship reasoning model
                "gpt-5-mini",  # Lightweight GPT-5 for cost-sensitive apps
                "gpt-5-nano"  # Smallest, fastest GPT-5 for low latency
            ],
            "google": [
                "gemini-2.5-pro",  # Gemini 2.5 Pro with adaptive thinking
                "gemini-2.5-flash"  # Gemini 2.5 Flash for high throughput
            ],
            "deepseek": [
                "deepseek-reasoner"  # DeepSeek R1 reasoning model (R1-0528)
            ]
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