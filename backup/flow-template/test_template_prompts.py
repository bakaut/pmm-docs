#!/usr/bin/env python3
"""
Test script to verify that all prompts are loaded correctly through templates.
"""

import os
import sys

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_template_prompts():
    """Test that all prompts are loaded correctly through templates."""
    print("Testing template-based prompt loading...")
    
    # Set required environment variables
    os.environ['operouter_key'] = 'test_key'
    os.environ['bot_token'] = 'test_token'
    os.environ['database_url'] = 'postgresql://test:test@test:5432/test'
    
    from mindset.config import Config
    config = Config.from_env()
    
    # Test all prompts
    prompts = {
        'system_prompt': config.system_prompt,
        'intent_detection_prompt': config.system_prompt_intent,
        'emotion_detection_prompt': config.system_prompt_detect_emotion,
        'state_detection_prompt': config.system_prompt_detect_state,
        'suno_preparation_prompt': config.system_prompt_prepare_suno
    }
    
    # Check that all prompts are loaded and have reasonable lengths
    for name, prompt in prompts.items():
        print(f"{name}: {len(prompt)} characters")
        assert len(prompt) > 0, f"{name} should not be empty"
        assert "error" not in prompt.lower(), f"{name} should not contain error messages"
    
    print("All template-based prompts loaded successfully!")

if __name__ == "__main__":
    test_template_prompts()
    print("Template prompt tests completed!")