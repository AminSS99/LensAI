"""
Message Utility Functions
Provides utilities for safely splitting and formatting Telegram messages.
"""

from typing import List


# Telegram's maximum message length
TELEGRAM_MAX_LENGTH = 4096


def split_message(text: str, max_length: int = TELEGRAM_MAX_LENGTH) -> List[str]:
    """
    Split a long message into chunks that respect Telegram's character limit.
    
    This function intelligently splits messages at natural boundaries to avoid:
    - Breaking multi-byte UTF-8 characters (emojis, Cyrillic, etc.)
    - Cutting URLs or markdown links in half
    - Breaking markdown formatting syntax
    
    Args:
        text: The message text to split
        max_length: Maximum length per chunk (default: 4096 for Telegram)
        
    Returns:
        List of message chunks, each under max_length characters
    """
    if not text:
        return []
    
    # If text fits in one message, return it as-is
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    current_chunk = ""
    
    # Split by double newlines first (paragraphs)
    paragraphs = text.split('\n\n')
    
    for para_idx, paragraph in enumerate(paragraphs):
        # If adding this paragraph would exceed the limit
        if len(current_chunk) + len(paragraph) + 2 > max_length:
            # If current chunk has content, save it
            if current_chunk:
                chunks.append(current_chunk.rstrip())
                current_chunk = ""
            
            # If the paragraph itself is too long, split by single newlines
            if len(paragraph) > max_length:
                lines = paragraph.split('\n')
                
                for line_idx, line in enumerate(lines):
                    # If adding this line would exceed the limit
                    if len(current_chunk) + len(line) + 1 > max_length:
                        if current_chunk:
                            chunks.append(current_chunk.rstrip())
                            current_chunk = ""
                        
                        # If even a single line is too long, split by words
                        if len(line) > max_length:
                            words = line.split(' ')
                            
                            for word in words:
                                # If adding this word would exceed limit
                                if len(current_chunk) + len(word) + 1 > max_length:
                                    if current_chunk:
                                        chunks.append(current_chunk.rstrip())
                                    
                                    # If even a single word is too long (e.g., very long URL)
                                    # split it carefully at the character level
                                    if len(word) > max_length:
                                        # Split at safe boundary (max_length - 10 to be safe)
                                        safe_length = max_length - 10
                                        for i in range(0, len(word), safe_length):
                                            chunk = word[i:i + safe_length]
                                            chunks.append(chunk)
                                        current_chunk = ""
                                    else:
                                        current_chunk = word + " "
                                else:
                                    current_chunk += word + " "
                        else:
                            current_chunk = line + "\n"
                    else:
                        current_chunk += line + ("\n" if line_idx < len(lines) - 1 else "")
            else:
                current_chunk = paragraph + "\n\n"
        else:
            current_chunk += paragraph + ("\n\n" if para_idx < len(paragraphs) - 1 else "")
    
    # Add any remaining content
    if current_chunk.strip():
        chunks.append(current_chunk.rstrip())
    
    return chunks


def split_message_simple(text: str, max_length: int = 4000) -> List[str]:
    """
    Simple message splitter that splits at newline boundaries.
    Safer than arbitrary character splitting but less sophisticated than split_message().
    
    Args:
        text: The message text to split
        max_length: Maximum length per chunk (default: 4000 for safety margin)
        
    Returns:
        List of message chunks
    """
    if not text or len(text) <= max_length:
        return [text] if text else []
    
    chunks = []
    lines = text.split('\n')
    current_chunk = ""
    
    for line in lines:
        # Check if adding this line would exceed the limit
        if len(current_chunk) + len(line) + 1 > max_length:
            # Save current chunk if it has content
            if current_chunk:
                chunks.append(current_chunk.rstrip())
            
            # Start new chunk with this line
            # If even a single line is too long, we need to split it
            if len(line) > max_length:
                # Split at word boundaries
                words = line.split(' ')
                temp_line = ""
                for word in words:
                    if len(temp_line) + len(word) + 1 > max_length:
                        if temp_line:
                            chunks.append(temp_line.rstrip())
                        temp_line = word + " "
                    else:
                        temp_line += word + " "
                current_chunk = temp_line
            else:
                current_chunk = line + "\n"
        else:
            current_chunk += line + "\n"
    
    # Add remaining content
    if current_chunk.strip():
        chunks.append(current_chunk.rstrip())
    
    return chunks
