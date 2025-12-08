"""
AI provider interface and OpenAI implementation for quiz generation.
"""

import json
import time
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from openai import OpenAI
from app.config import config


class AIProvider(ABC):
    """Abstract base class for AI providers."""
    
    @abstractmethod
    def generate_quiz(self, text: str, n_questions: int, difficulty: str) -> List[Dict[str, Any]]:
        """
        Generate quiz questions from text.
        
        Args:
            text: Source text to generate questions from
            n_questions: Number of questions to generate
            difficulty: Difficulty level (easy, medium, hard)
            
        Returns:
            List of question dictionaries
        """
        pass


class OpenAIProvider(AIProvider):
    """OpenAI implementation of AI provider."""
    
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        """Initialize OpenAI client."""
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.max_retries = 2
    
    def generate_quiz(self, text: str, n_questions: int, difficulty: str) -> List[Dict[str, Any]]:
        """Generate quiz using OpenAI."""
        
        # Build prompt
        prompt = self._build_prompt(text, n_questions, difficulty)
        
        # Try with retries
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert educational content creator. Generate quiz questions in valid JSON format only. Do not include any explanatory text outside the JSON."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.7,
                    max_tokens=2000
                )
                
                content = response.choices[0].message.content.strip()
                
                # Parse JSON
                questions = self._parse_response(content)
                
                if questions and len(questions) > 0:
                    return questions
                else:
                    raise ValueError("No valid questions generated")
                
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {e}")
                
                if attempt < self.max_retries:
                    # Exponential backoff
                    sleep_time = 2 ** attempt
                    time.sleep(sleep_time)
                else:
                    # Final attempt failed
                    raise Exception(f"Failed to generate quiz after {self.max_retries + 1} attempts: {e}")
        
        return []
    
    def _build_prompt(self, text: str, n_questions: int, difficulty: str) -> str:
        """Build prompt for quiz generation."""
        
        difficulty_instructions = {
            "easy": "Focus on basic recall and understanding. Questions should test fundamental concepts and definitions.",
            "medium": "Include application and analysis questions. Test understanding and ability to apply concepts.",
            "hard": "Require critical thinking and problem-solving. Include complex scenarios and multi-step reasoning."
        }
        
        instruction = difficulty_instructions.get(difficulty, difficulty_instructions["medium"])
        
        prompt = f"""Based on the following educational content, generate {n_questions} quiz questions at {difficulty} difficulty level.

{instruction}

Content:
{text[:8000]}

Generate questions in the following JSON format ONLY. Do not include any text outside the JSON array:

[
  {{
    "type": "mcq",
    "question": "Question text here?",
    "choices": ["Choice A", "Choice B", "Choice C", "Choice D"],
    "answer": 0,
    "explanation": "Detailed explanation of why this answer is correct"
  }},
  {{
    "type": "short",
    "question": "Question text here?",
    "answer": "Expected short answer",
    "explanation": "Explanation"
  }}
]

Requirements:
- Generate exactly {n_questions} questions
- Mix of MCQ and short answer questions (at least 60% MCQ)
- Each MCQ must have exactly 4 choices
- Answer index for MCQ is 0-based (0, 1, 2, or 3)
- Include clear, educational explanations
- Questions must be based on the provided content
- Ensure questions are appropriate for {difficulty} level

Return ONLY the JSON array, no other text.
"""
        return prompt
    
    def _parse_response(self, content: str) -> List[Dict[str, Any]]:
        """Parse and validate response from AI."""
        
        # Try to extract JSON if wrapped in markdown code blocks
        content = content.strip()
        if content.startswith('```'):
            # Remove markdown code blocks
            lines = content.split('\n')
            if lines[0].startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].startswith('```'):
                lines = lines[:-1]
            content = '\n'.join(lines)
        
        # Remove 'json' language identifier if present
        content = content.replace('```json', '').replace('```', '').strip()
        
        # Parse JSON
        try:
            questions = json.loads(content)
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            print(f"Content: {content[:500]}")
            
            # Try to find JSON array in content
            start_idx = content.find('[')
            end_idx = content.rfind(']')
            if start_idx != -1 and end_idx != -1:
                try:
                    questions = json.loads(content[start_idx:end_idx+1])
                except:
                    raise ValueError("Could not parse JSON from response")
            else:
                raise ValueError("No JSON array found in response")
        
        # Validate questions
        validated = []
        for q in questions:
            if self._validate_question(q):
                validated.append(q)
        
        return validated
    
    def _validate_question(self, question: Dict[str, Any]) -> bool:
        """Validate a single question."""
        
        required_fields = ["type", "question", "answer", "explanation"]
        
        # Check required fields
        for field in required_fields:
            if field not in question:
                print(f"Missing required field: {field}")
                return False
        
        # Validate by type
        if question["type"] == "mcq":
            if "choices" not in question:
                print("MCQ missing choices")
                return False
            if not isinstance(question["choices"], list) or len(question["choices"]) != 4:
                print("MCQ must have exactly 4 choices")
                return False
            if not isinstance(question["answer"], int) or question["answer"] not in [0, 1, 2, 3]:
                print("MCQ answer must be integer 0-3")
                return False
        
        elif question["type"] == "short":
            if not isinstance(question["answer"], str):
                print("Short answer must be string")
                return False
        
        else:
            print(f"Unknown question type: {question['type']}")
            return False
        
        return True


def get_ai_provider() -> AIProvider:
    """Get configured AI provider instance."""
    if not config.OPENAI_API_KEY or config.OPENAI_API_KEY == "REPLACE_OPENAI_KEY":
        raise ValueError("OPENAI_API_KEY not configured")
    
    return OpenAIProvider(api_key=config.OPENAI_API_KEY, model=config.AI_MODEL)
