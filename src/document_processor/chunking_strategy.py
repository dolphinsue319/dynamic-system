"""Intelligent document chunking strategies"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ChunkType(Enum):
    """Types of document chunks"""
    CODE = "code"
    TEXT = "text"
    TABLE = "table"
    LIST = "list"
    HEADING = "heading"
    METADATA = "metadata"


@dataclass
class DocumentChunk:
    """A single document chunk"""
    content: str
    chunk_type: ChunkType
    start_pos: int
    end_pos: int
    token_count: int
    metadata: Dict[str, Any]
    parent_section: Optional[str] = None
    

class ChunkingStrategy:
    """
    Intelligent document chunking that preserves semantic boundaries
    and maintains context across chunks.
    """
    
    # Chunk size limits (in tokens)
    DEFAULT_CHUNK_SIZE = 10000
    MAX_CHUNK_SIZE = 50000
    MIN_CHUNK_SIZE = 500
    OVERLAP_SIZE = 200  # Token overlap between chunks
    
    def __init__(self, tokenizer=None):
        self.tokenizer = tokenizer
        if not tokenizer:
            import tiktoken
            try:
                self.tokenizer = tiktoken.get_encoding("cl100k_base")
            except Exception as e:
                logger.warning(f"Failed to load cl100k_base encoding: {e}, falling back to gpt2")
                try:
                    self.tokenizer = tiktoken.get_encoding("gpt2")
                except Exception as e:
                    logger.error(f"Failed to load tokenizer: {e}")
                    raise RuntimeError("Could not initialize tokenizer. Please install tiktoken.")
    
    def chunk_document(
        self,
        content: str,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        preserve_structure: bool = True,
        overlap: bool = True
    ) -> List[DocumentChunk]:
        """
        Chunk a document into semantic units
        
        Args:
            content: Document content to chunk
            chunk_size: Target size for each chunk in tokens
            preserve_structure: Whether to preserve document structure
            overlap: Whether to include overlap between chunks
            
        Returns:
            List of document chunks
        """
        if preserve_structure:
            # Detect document type and use appropriate strategy
            if self._is_code(content):
                return self._chunk_code(content, chunk_size)
            elif self._is_markdown(content):
                return self._chunk_markdown(content, chunk_size)
            elif self._is_structured_text(content):
                return self._chunk_structured_text(content, chunk_size)
        
        # Fallback to simple chunking
        return self._chunk_simple(content, chunk_size, overlap)
    
    def _is_code(self, content: str) -> bool:
        """Detect if content is primarily code"""
        code_indicators = [
            r'^\s*(def|class|function|import|from|const|let|var)\s',
            r'[{};]\s*$',
            r'^\s*#include',
            r'^\s*package\s',
        ]
        
        lines = content.split('\n')[:50]  # Check first 50 lines
        code_lines = 0
        
        for line in lines:
            if any(re.search(pattern, line, re.MULTILINE) for pattern in code_indicators):
                code_lines += 1
        
        return code_lines > len(lines) * 0.3
    
    def _is_markdown(self, content: str) -> bool:
        """Detect if content is markdown"""
        markdown_patterns = [
            r'^#{1,6}\s',  # Headers
            r'^\*\*.*\*\*',  # Bold
            r'^```',  # Code blocks
            r'^\|.*\|',  # Tables
            r'^\* |^- |^\d+\.',  # Lists
        ]
        
        lines = content.split('\n')[:30]
        markdown_lines = 0
        
        for line in lines:
            if any(re.search(pattern, line) for pattern in markdown_patterns):
                markdown_lines += 1
        
        return markdown_lines > 3
    
    def _is_structured_text(self, content: str) -> bool:
        """Detect if content has clear structure (sections, chapters, etc.)"""
        # Look for numbered sections or clear headers
        section_pattern = r'^(Chapter|Section|\d+\.|\d+\))\s'
        lines = content.split('\n')
        
        section_count = sum(1 for line in lines if re.match(section_pattern, line))
        return section_count > 3
    
    def _chunk_code(
        self,
        content: str,
        chunk_size: int
    ) -> List[DocumentChunk]:
        """Chunk code while preserving function/class boundaries"""
        chunks = []
        
        # Patterns for code structure
        patterns = {
            'python': r'^(class|def)\s+\w+',
            'javascript': r'^(function|class|const|let|var)\s+\w+',
            'java': r'^(public|private|protected)?\s*(class|interface|enum)\s+\w+',
        }
        
        # Try to detect language
        language = self._detect_language(content)
        pattern = patterns.get(language, patterns['python'])
        
        # Split by major code blocks
        lines = content.split('\n')
        current_chunk = []
        current_tokens = 0
        current_pos = 0
        
        for i, line in enumerate(lines):
            line_tokens = len(self.tokenizer.encode(line))
            
            # Check if this starts a new code block
            if re.match(pattern, line) and current_tokens > chunk_size * 0.5:
                # Save current chunk
                if current_chunk:
                    chunk_content = '\n'.join(current_chunk)
                    chunks.append(DocumentChunk(
                        content=chunk_content,
                        chunk_type=ChunkType.CODE,
                        start_pos=current_pos,
                        end_pos=current_pos + len(chunk_content),
                        token_count=current_tokens,
                        metadata={'language': language}
                    ))
                    current_pos += len(chunk_content) + 1
                    current_chunk = []
                    current_tokens = 0
            
            current_chunk.append(line)
            current_tokens += line_tokens
            
            # Force split if chunk is too large
            if current_tokens > chunk_size:
                chunk_content = '\n'.join(current_chunk)
                chunks.append(DocumentChunk(
                    content=chunk_content,
                    chunk_type=ChunkType.CODE,
                    start_pos=current_pos,
                    end_pos=current_pos + len(chunk_content),
                    token_count=current_tokens,
                    metadata={'language': language}
                ))
                current_pos += len(chunk_content) + 1
                current_chunk = []
                current_tokens = 0
        
        # Add remaining content
        if current_chunk:
            chunk_content = '\n'.join(current_chunk)
            chunks.append(DocumentChunk(
                content=chunk_content,
                chunk_type=ChunkType.CODE,
                start_pos=current_pos,
                end_pos=current_pos + len(chunk_content),
                token_count=current_tokens,
                metadata={'language': language}
            ))
        
        return chunks
    
    def _detect_language(self, content: str) -> str:
        """Simple language detection for code"""
        if 'import ' in content and 'def ' in content:
            return 'python'
        elif 'function ' in content or 'const ' in content:
            return 'javascript'
        elif 'public class' in content or 'private ' in content:
            return 'java'
        else:
            return 'unknown'
    
    def _chunk_markdown(
        self,
        content: str,
        chunk_size: int
    ) -> List[DocumentChunk]:
        """Chunk markdown while preserving section boundaries"""
        chunks = []
        
        # Split by headers
        header_pattern = r'^(#{1,6})\s+(.+)$'
        lines = content.split('\n')
        
        current_section = None
        current_chunk = []
        current_tokens = 0
        current_pos = 0
        
        for line in lines:
            header_match = re.match(header_pattern, line)
            
            if header_match:
                # Save current chunk if it exists
                if current_chunk and current_tokens > chunk_size * 0.3:
                    chunk_content = '\n'.join(current_chunk)
                    chunks.append(DocumentChunk(
                        content=chunk_content,
                        chunk_type=ChunkType.TEXT,
                        start_pos=current_pos,
                        end_pos=current_pos + len(chunk_content),
                        token_count=current_tokens,
                        metadata={'section': current_section},
                        parent_section=current_section
                    ))
                    current_pos += len(chunk_content) + 1
                    current_chunk = []
                    current_tokens = 0
                
                # Update section
                current_section = header_match.group(2)
            
            current_chunk.append(line)
            current_tokens += len(self.tokenizer.encode(line))
            
            # Force split if chunk is too large
            if current_tokens > chunk_size:
                chunk_content = '\n'.join(current_chunk)
                chunks.append(DocumentChunk(
                    content=chunk_content,
                    chunk_type=ChunkType.TEXT,
                    start_pos=current_pos,
                    end_pos=current_pos + len(chunk_content),
                    token_count=current_tokens,
                    metadata={'section': current_section},
                    parent_section=current_section
                ))
                current_pos += len(chunk_content) + 1
                
                # Keep last few lines for context
                if len(current_chunk) > 5:
                    current_chunk = current_chunk[-3:]
                    current_tokens = sum(len(self.tokenizer.encode(line)) for line in current_chunk)
                else:
                    current_chunk = []
                    current_tokens = 0
        
        # Add remaining content
        if current_chunk:
            chunk_content = '\n'.join(current_chunk)
            chunks.append(DocumentChunk(
                content=chunk_content,
                chunk_type=ChunkType.TEXT,
                start_pos=current_pos,
                end_pos=current_pos + len(chunk_content),
                token_count=current_tokens,
                metadata={'section': current_section},
                parent_section=current_section
            ))
        
        return chunks
    
    def _chunk_structured_text(
        self,
        content: str,
        chunk_size: int
    ) -> List[DocumentChunk]:
        """Chunk structured text (books, articles) by sections"""
        # Similar to markdown but with different patterns
        return self._chunk_by_paragraphs(content, chunk_size)
    
    def _chunk_by_paragraphs(
        self,
        content: str,
        chunk_size: int
    ) -> List[DocumentChunk]:
        """Chunk by paragraphs, respecting natural boundaries"""
        chunks = []
        
        # Split by double newlines (paragraphs)
        paragraphs = re.split(r'\n\n+', content)
        
        current_chunk = []
        current_tokens = 0
        current_pos = 0
        
        for para in paragraphs:
            para_tokens = len(self.tokenizer.encode(para))
            
            if current_tokens + para_tokens > chunk_size and current_chunk:
                # Save current chunk
                chunk_content = '\n\n'.join(current_chunk)
                chunks.append(DocumentChunk(
                    content=chunk_content,
                    chunk_type=ChunkType.TEXT,
                    start_pos=current_pos,
                    end_pos=current_pos + len(chunk_content),
                    token_count=current_tokens,
                    metadata={}
                ))
                current_pos += len(chunk_content) + 2
                current_chunk = []
                current_tokens = 0
            
            current_chunk.append(para)
            current_tokens += para_tokens
        
        # Add remaining content
        if current_chunk:
            chunk_content = '\n\n'.join(current_chunk)
            chunks.append(DocumentChunk(
                content=chunk_content,
                chunk_type=ChunkType.TEXT,
                start_pos=current_pos,
                end_pos=current_pos + len(chunk_content),
                token_count=current_tokens,
                metadata={}
            ))
        
        return chunks
    
    def _chunk_simple(
        self,
        content: str,
        chunk_size: int,
        overlap: bool
    ) -> List[DocumentChunk]:
        """Simple chunking with optional overlap"""
        chunks = []
        tokens = self.tokenizer.encode(content)
        
        step = chunk_size - (self.OVERLAP_SIZE if overlap else 0)
        
        for i in range(0, len(tokens), step):
            chunk_tokens = tokens[i:i + chunk_size]
            chunk_content = self.tokenizer.decode(chunk_tokens)
            
            chunks.append(DocumentChunk(
                content=chunk_content,
                chunk_type=ChunkType.TEXT,
                start_pos=i,
                end_pos=min(i + chunk_size, len(tokens)),
                token_count=len(chunk_tokens),
                metadata={'chunk_index': len(chunks)}
            ))
            
            if i + chunk_size >= len(tokens):
                break
        
        return chunks
    
    def merge_chunks(
        self,
        chunks: List[DocumentChunk],
        max_size: int
    ) -> List[DocumentChunk]:
        """Merge small chunks to optimize processing"""
        merged = []
        current_merge = []
        current_tokens = 0
        
        for chunk in chunks:
            if current_tokens + chunk.token_count > max_size and current_merge:
                # Create merged chunk
                merged_content = '\n'.join(c.content for c in current_merge)
                merged.append(DocumentChunk(
                    content=merged_content,
                    chunk_type=current_merge[0].chunk_type,
                    start_pos=current_merge[0].start_pos,
                    end_pos=current_merge[-1].end_pos,
                    token_count=current_tokens,
                    metadata={'merged_chunks': len(current_merge)}
                ))
                current_merge = []
                current_tokens = 0
            
            current_merge.append(chunk)
            current_tokens += chunk.token_count
        
        # Add remaining chunks
        if current_merge:
            merged_content = '\n'.join(c.content for c in current_merge)
            merged.append(DocumentChunk(
                content=merged_content,
                chunk_type=current_merge[0].chunk_type,
                start_pos=current_merge[0].start_pos,
                end_pos=current_merge[-1].end_pos,
                token_count=current_tokens,
                metadata={'merged_chunks': len(current_merge)}
            ))
        
        return merged