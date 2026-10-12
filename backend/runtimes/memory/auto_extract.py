"""Auto fact extraction from conversation using local LLM."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from runtimes.memory.contracts import MemoryType, Origin


@dataclass
class ExtractedFact:
    """A fact extracted from text."""
    content: str
    memory_type: MemoryType = MemoryType.SEMANTIC
    importance: float = 0.5
    entities: List[str] = None
    confidence: float = 0.8
    origin: Origin = Origin.CONVERSATION
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.entities is None:
            self.entities = []
        if self.metadata is None:
            self.metadata = {}


EXTRACTION_PROMPT = """Extract key facts from the following conversation. Return a JSON array of facts, where each fact has:
- content: The fact as a single sentence
- memory_type: One of "conversation", "episodic", "semantic", "working"
- importance: Float 0.0-1.0
- entities: List of named entities mentioned
- confidence: Float 0.0-1.0
- origin: One of "user_document", "conversation", "generated"

Only extract facts that are:
1. Specific and verifiable (not opinions)
2. Useful for future recall (rates, names, decisions, preferences)
3. Not already obvious from context

Conversation:
{text}

Return ONLY the JSON array, no other text."""


async def extract_facts(
    text: str,
    context: Dict[str, Any],
    model: str = "qwen2.5:14b",
    max_facts: int = 10,
    models_runtime: Any = None,
) -> List[ExtractedFact]:
    """Extract facts from text using local LLM."""
    # Try LLM-based extraction first
    if models_runtime is not None:
        try:
            return await _llm_extract(text, context, model, max_facts, models_runtime)
        except Exception as e:
            # Fall through to heuristic
            pass
    
    # Fallback to heuristic extraction
    return _heuristic_extract(text, context, max_facts)


async def _llm_extract(
    text: str,
    context: Dict[str, Any],
    model: str,
    max_facts: int,
    models_runtime: Any,
) -> List[ExtractedFact]:
    """Extract facts using local LLM via ModelsRuntime."""
    # Get model completion for extraction
    prompt = EXTRACTION_PROMPT.format(text=text)
    
    try:
        # Use the models runtime to generate completion
        # ModelsRuntime should have a complete/generate method
        if hasattr(models_runtime, 'complete'):
            response = await models_runtime.complete(
                prompt=prompt,
                model=model,
                temperature=0.1,
                max_tokens=2048,
            )
        elif hasattr(models_runtime, 'generate'):
            response = await models_runtime.generate(
                prompt=prompt,
                model=model,
                temperature=0.1,
                max_tokens=2048,
            )
        else:
            raise AttributeError("ModelsRuntime has no complete/generate method")
        
        # Parse JSON response
        content = response if isinstance(response, str) else response.get("text", "")
        facts_data = json.loads(content)
        
        if not isinstance(facts_data, list):
            return []
        
        facts = []
        for fact_data in facts_data[:max_facts]:
            try:
                facts.append(ExtractedFact(
                    content=fact_data.get("content", ""),
                    memory_type=MemoryType(fact_data.get("memory_type", "semantic")),
                    importance=float(fact_data.get("importance", 0.5)),
                    entities=fact_data.get("entities", []),
                    confidence=float(fact_data.get("confidence", 0.8)),
                    origin=Origin(fact_data.get("origin", "conversation")),
                    metadata={"extracted_by": "llm", "model": model},
                ))
            except Exception:
                continue
        
        return facts
        
    except json.JSONDecodeError:
        # LLM returned invalid JSON
        return []
    except Exception:
        return []


def _heuristic_extract(
    text: str,
    context: Dict[str, Any],
    max_facts: int,
) -> List[ExtractedFact]:
    """Heuristic fact extraction without LLM."""
    facts = []
    
    # Each pattern tuple: (regex, content_template)
    # content_template: "is" for "X is Y", "costs" for "X costs Y", etc.
    # Or a callable(match) -> content
    patterns = [
        # "my X is Y" -> "X is Y"
        (r'(?:my|the|our)\s+(\w+(?:\s+\w+)*)\s+(?:is|equals?|:)\s+([^.!?]+)', "is"),
        # "X costs Y" -> "X costs Y"
        (r'(\w+(?:\s+\w+)*)\s+(?:cost|charge)s?\s+([^.!?]+)', "costs"),
        # "X rate Y" (singular verb, not followed by "is") -> "X rates Y"
        (r'(\w+(?:\s+\w+)*)\s+rate\b(?!\s+is)\s+([^.!?]+)', "rates"),
        # "X rates Y" (plural verb) -> "X rates Y"
        (r'(\w+(?:\s+\w+)*)\s+rates\s+([^.!?]+)', "rates"),
        # "remember that Y" -> "Y"
        (r'(?:remember|note|save)\s+(?:that\s+)?([^.!?]+)', None),
        # "decided that Y" -> "decided Y"
        (r'(decided|agreed|confirmed)\s+(?:that\s+)?([^.!?]+)', "decided"),
        # "deadline is Y" -> "deadline is Y"
        (r'(deadline|due|by)\s+(?:is\s+)?([^.!?]+)', "is"),
    ]
    
    for pattern, template in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            if len(facts) >= max_facts:
                break
            
            if template is None:
                # Single group pattern: content = group(1)
                if match.lastindex >= 1:
                    content = match.group(1).strip()
                else:
                    continue
            elif match.lastindex >= 2:
                # Two group pattern: content = "group1 template group2"
                content = f"{match.group(1).strip()} {template} {match.group(2).strip()}"
            elif match.lastindex == 1:
                content = match.group(1).strip()
            else:
                continue
            
            if len(content) >= 10 and len(content) < 500:
                facts.append(ExtractedFact(
                    content=content,
                    memory_type=MemoryType.SEMANTIC,
                    importance=0.6,
                    entities=_extract_entities(content),
                    confidence=0.7,
                    origin=Origin.CONVERSATION,
                    metadata={"extracted_by": "heuristic"},
                ))
            
            if len(facts) >= max_facts:
                break
    
    return facts[:max_facts]


def _extract_entities(text: str) -> List[str]:
    """Simple entity extraction."""
    entities = []
    
    # Capitalized words (potential proper nouns)
    words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
    entities.extend(words[:5])
    
    # Dollar amounts
    amounts = re.findall(r'\$[\d,]+(?:\.\d{2})?', text)
    entities.extend(amounts)
    
    # Dates
    dates = re.findall(r'\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\w+\s+\d{1,2},?\s+\d{4})\b', text)
    entities.extend(dates)
    
    return list(set(entities))[:10]


async def extract_and_store(
    text: str,
    context: Dict[str, Any],
    memory_runtime: Any,
    project_id: Optional[str] = None,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    models_runtime: Any = None,
) -> List[str]:
    """Extract facts and store them in the Spine."""
    facts = await extract_facts(text, context, models_runtime=models_runtime)
    stored_ids = []
    
    for fact in facts:
        try:
            fact_id = await memory_runtime.store(
                content=fact.content,
                memory_type=fact.memory_type,
                metadata=fact.metadata,
                session_id=session_id,
                user_id=user_id,
                importance=fact.importance,
                scope=project_id,
                origin=fact.origin,
            )
            stored_ids.append(fact_id)
        except Exception:
            continue
    
    return stored_ids