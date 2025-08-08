"""Document preprocessor using Gemini's 1M token context window"""

import logging
import tiktoken
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum

from ..utils.llm_client import LLMClient

logger = logging.getLogger(__name__)


class ProcessingStrategy(Enum):
    """Document processing strategies"""
    HIERARCHICAL = "hierarchical"  # Multi-level summarization
    SEMANTIC = "semantic"          # Semantic chunking and extraction
    EXTRACTIVE = "extractive"      # Key content extraction
    HYBRID = "hybrid"              # Combination of strategies


@dataclass
class DocumentSummary:
    """Preprocessed document summary"""
    original_tokens: int
    summary_tokens: int
    strategy_used: ProcessingStrategy
    sections: List[Dict[str, Any]]
    key_points: List[str]
    metadata: Dict[str, Any]
    full_summary: str
    cached: bool = False


class DocumentPreprocessor:
    """
    Preprocesses large documents using Gemini's 1M token context.
    Enables other LLMs with smaller context windows to work with the summary.
    """
    
    # Token limits for different models
    MODEL_CONTEXT_LIMITS = {
        "gemini-2.0-flash": 1_000_000,
        "gemini-2.5-pro": 1_000_000,
        "gpt-4o": 128_000,
        "gpt-4o-mini": 128_000,
        "claude-3-5-sonnet": 200_000,
        "claude-3-opus": 200_000,
    }
    
    # Threshold for triggering preprocessing
    PREPROCESSING_THRESHOLD = 100_000  # tokens
    
    def __init__(self, config: Dict[str, Any], mcp_session=None):
        self.config = config
        self.llm_client = LLMClient(config.get("models", {}), mcp_session=mcp_session)
        self.preprocessor_model = config.get("document_processing", {}).get(
            "preprocessor_model", "gemini-2.0-flash"
        )
        self.enable_preprocessing = config.get("document_processing", {}).get(
            "enable_preprocessing", True
        )
        self.max_direct_tokens = config.get("document_processing", {}).get(
            "max_direct_tokens", 100_000
        )
        
        # Initialize tokenizer for accurate token counting
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            logger.warning(f"Failed to load cl100k_base encoding: {e}, falling back to gpt2")
            try:
                self.tokenizer = tiktoken.get_encoding("gpt2")
            except Exception as e:
                logger.error(f"Failed to load tokenizer: {e}")
                raise RuntimeError("Could not initialize tokenizer. Please install tiktoken.")
            
        from .summary_cache import SummaryCache
        self.cache = SummaryCache()
    
    async def initialize(self):
        """Initialize the preprocessor"""
        await self.llm_client.initialize()
        await self.cache.initialize()
        logger.info(f"Document preprocessor initialized with model: {self.preprocessor_model}")
    
    async def should_preprocess(
        self, 
        content: str,
        target_model: str
    ) -> Tuple[bool, int]:
        """
        Determine if document should be preprocessed
        
        Returns:
            Tuple of (should_preprocess, token_count)
        """
        if not self.enable_preprocessing:
            return False, 0
        
        # Count tokens
        token_count = len(self.tokenizer.encode(content))
        
        # Get target model's context limit
        target_limit = self.MODEL_CONTEXT_LIMITS.get(target_model, 128_000)
        
        # Preprocess if:
        # 1. Document exceeds target model's limit
        # 2. Document exceeds preprocessing threshold
        should_preprocess = (
            token_count > target_limit * 0.8 or  # 80% of target limit
            token_count > self.max_direct_tokens
        )
        
        if should_preprocess:
            logger.info(
                f"Document with {token_count:,} tokens exceeds limit for {target_model} "
                f"({target_limit:,} tokens). Will preprocess with {self.preprocessor_model}."
            )
        
        return should_preprocess, token_count
    
    async def preprocess(
        self,
        content: str,
        request_context: str,
        strategy: ProcessingStrategy = ProcessingStrategy.HYBRID
    ) -> DocumentSummary:
        """
        Preprocess a large document using Gemini
        
        Args:
            content: The document content
            request_context: The user's request/question about the document
            strategy: Processing strategy to use
            
        Returns:
            DocumentSummary with preprocessed content
        """
        # Check cache first
        cache_key = self.cache.generate_key(content, request_context)
        cached_summary = await self.cache.get(cache_key)
        if cached_summary:
            logger.info("Using cached document summary")
            cached_summary.cached = True
            return cached_summary
        
        # Count tokens
        original_tokens = len(self.tokenizer.encode(content))
        logger.info(f"Preprocessing document with {original_tokens:,} tokens using {strategy.value} strategy")
        
        # Build preprocessing prompt based on strategy
        prompt = self._build_preprocessing_prompt(content, request_context, strategy)
        
        try:
            # Use Gemini with its 1M context window
            response = await self.llm_client.complete(
                prompt=prompt,
                model=self.preprocessor_model,
                temperature=0.1,  # Low temperature for consistent summaries
                max_tokens=50000  # Allow substantial summary
            )
            
            # Parse response into structured summary
            summary = self._parse_summary_response(response, strategy, original_tokens)
            
            # Cache the result
            await self.cache.set(cache_key, summary)
            
            logger.info(
                f"Document preprocessed: {original_tokens:,} → {summary.summary_tokens:,} tokens "
                f"({(1 - summary.summary_tokens/original_tokens)*100:.1f}% reduction)"
            )
            
            return summary
            
        except Exception as e:
            logger.error(f"Preprocessing failed: {e}")
            # Return a basic summary on failure
            return DocumentSummary(
                original_tokens=original_tokens,
                summary_tokens=1000,
                strategy_used=strategy,
                sections=[],
                key_points=["Preprocessing failed - using original content"],
                metadata={"error": str(e)},
                full_summary=content[:10000],  # First 10k chars as fallback
                cached=False
            )
    
    def _build_preprocessing_prompt(
        self,
        content: str,
        request_context: str,
        strategy: ProcessingStrategy
    ) -> str:
        """Build the preprocessing prompt based on strategy"""
        
        base_prompt = f"""You are a document preprocessor. Your task is to analyze and summarize this large document 
to enable effective processing by other AI models with smaller context windows.

User's Request/Question: {request_context}

Document Content:
{content}

"""
        
        if strategy == ProcessingStrategy.HIERARCHICAL:
            return base_prompt + """
Create a hierarchical summary with the following structure:
1. Executive Summary (500 words max)
2. Main Sections (identify and summarize each major section)
3. Key Details relevant to the user's request
4. Important Code/Data Snippets (if applicable)
5. Relationships and Dependencies

Format your response as a structured JSON-like output."""
        
        elif strategy == ProcessingStrategy.SEMANTIC:
            return base_prompt + """
Perform semantic analysis and extraction:
1. Identify main themes and concepts
2. Extract semantically relevant sections for the user's request
3. Preserve important context and relationships
4. Highlight key entities, definitions, and facts
5. Maintain logical flow and coherence

Focus on content most relevant to the user's request."""
        
        elif strategy == ProcessingStrategy.EXTRACTIVE:
            return base_prompt + """
Extract the most important content:
1. Key sentences and paragraphs directly relevant to the user's request
2. Critical code blocks or data structures
3. Important definitions and explanations
4. Actionable insights and conclusions
5. References and dependencies

Preserve exact quotes where important."""
        
        else:  # HYBRID
            return base_prompt + """
Provide a comprehensive preprocessing using multiple strategies:

PART 1 - Hierarchical Overview:
- Executive summary (300 words)
- Section-by-section breakdown
- Document structure and organization

PART 2 - Semantic Extraction:
- Key concepts and themes relevant to: {request_context}
- Important relationships and dependencies
- Critical insights and patterns

PART 3 - Detailed Content:
- Exact quotes and snippets most relevant to the request
- Code blocks, formulas, or data structures (if applicable)
- Specific answers to implicit questions in the request

PART 4 - Metadata:
- Document type and format
- Key statistics (word count, sections, etc.)
- Relevance score to user's request (1-10)
- Suggested follow-up questions

Format as structured sections for easy parsing.""".format(request_context=request_context)
    
    def _parse_summary_response(
        self,
        response: str,
        strategy: ProcessingStrategy,
        original_tokens: int
    ) -> DocumentSummary:
        """Parse the LLM response into a structured summary"""
        
        # Count summary tokens
        summary_tokens = len(self.tokenizer.encode(response))
        
        # Extract sections and key points (simplified parsing)
        lines = response.split('\n')
        sections = []
        key_points = []
        
        current_section = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Detect section headers (lines starting with numbers or PART)
            if line.startswith(('1.', '2.', '3.', '4.', '5.', 'PART')):
                if current_section:
                    sections.append(current_section)
                current_section = {
                    "title": line,
                    "content": []
                }
            elif current_section:
                current_section["content"].append(line)
            
            # Extract key points (lines with bullets or dashes)
            if line.startswith(('- ', '• ', '* ')):
                key_points.append(line[2:])
        
        if current_section:
            sections.append(current_section)
        
        # Format sections
        for section in sections:
            section["content"] = "\n".join(section["content"])
        
        return DocumentSummary(
            original_tokens=original_tokens,
            summary_tokens=summary_tokens,
            strategy_used=strategy,
            sections=sections,
            key_points=key_points[:10],  # Top 10 key points
            metadata={
                "preprocessor_model": self.preprocessor_model,
                "reduction_ratio": f"{(1 - summary_tokens/original_tokens)*100:.1f}%"
            },
            full_summary=response,
            cached=False
        )
    
    async def extract_from_summary(
        self,
        summary: DocumentSummary,
        query: str,
        target_model: str
    ) -> str:
        """
        Extract specific information from a preprocessed summary
        
        Args:
            summary: The preprocessed document summary
            query: Specific extraction query
            target_model: The model that will process the extraction
            
        Returns:
            Extracted content optimized for target model
        """
        # Build extraction prompt
        prompt = f"""Based on this document summary, extract information relevant to: {query}

Summary Overview:
- Original document: {summary.original_tokens:,} tokens
- Processing strategy: {summary.strategy_used.value}
- Key sections: {len(summary.sections)}

Key Points:
{chr(10).join(f'- {point}' for point in summary.key_points)}

Detailed Summary:
{summary.full_summary[:30000]}  # Limit to fit in target model

Extract and format the most relevant information for the query."""
        
        # Use target model for extraction
        response = await self.llm_client.complete(
            prompt=prompt,
            model=target_model,
            temperature=0.3,
            max_tokens=5000
        )
        
        return response