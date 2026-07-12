import re


def remove_emojis(text: str) -> str:
    """Removes all standard emojis."""
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE
    )
    return emoji_pattern.sub('', text)

def preprocess_text(text: str) -> str:
    """
    Cleans raw LLM output for natural speech.
    - Removes emojis, asterisks, and markdown.
    - Replaces code blocks with a spoken summary.
    """
    # 1. Remove emojis
    text = remove_emojis(text)

    # 2. Remove asterisks (bold/italics) and underscores
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'_+', '', text)

    # 3. Remove code blocks and inline code
    text = re.sub(r'```[\s\S]*?```', ' [Code block displayed on screen] ', text)
    text = re.sub(r'`[^`]+`', '', text)

    # 4. Remove markdown headers and links
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

    # 5. Normalize whitespace and punctuation for natural pauses
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\.{2,}', '.', text) # Convert ellipses to periods for better TTS pacing

    return text
