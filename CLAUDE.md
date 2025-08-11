# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

**Setup and Installation:**
```bash
# Install dependencies (requires uv package manager)
uv sync

# Create environment file (required)
echo "ANTHROPIC_API_KEY=your_key_here" > .env
```

**Running the Application:**
```bash
# Quick start (recommended)
./run.sh

# Manual start with hot reload
cd backend && uv run uvicorn app:app --reload --port 8000
```

**Access Points:**
- Web Interface: http://localhost:8000
- API Documentation: http://localhost:8000/docs

## Architecture Overview

This is a RAG (Retrieval-Augmented Generation) chatbot system that answers questions about course materials using semantic search and AI generation.

### Core Architecture Pattern

The system uses a **two-phase Claude interaction model**:
1. **Tool Decision Phase**: Claude API call with search tools available - Claude decides whether to search
2. **Response Generation Phase**: Second Claude API call with search results - Claude synthesizes final answer

### Component Integration Flow

```
User Query → FastAPI → RAGSystem → AIGenerator → Claude API (with tools)
                                       ↓
                                   ToolManager → VectorStore → ChromaDB
                                       ↓
                               Claude API (with results) → Final Response
```

### Key Components

- **RAGSystem** (`rag_system.py`): Central orchestrator managing all components
- **VectorStore** (`vector_store.py`): ChromaDB integration with SentenceTransformer embeddings
- **AIGenerator** (`ai_generator.py`): Handles Claude API interaction with tool calling
- **DocumentProcessor** (`document_processor.py`): Processes course documents into searchable chunks
- **SessionManager** (`session_manager.py`): In-memory conversation history (lost on restart)
- **SearchTools** (`search_tools.py`): Claude function calling interface for semantic search

### Configuration Details

**Models and Embeddings:**
- AI Model: `claude-sonnet-4-20250514` 
- Embedding Model: `all-MiniLM-L6-v2` (384 dimensions)
- Chunking: 800 characters with 100 character overlap
- Search Results: Maximum 5 results per query

**Storage:**
- Vector Database: ChromaDB (persists at `./chroma_db`)
- Session Storage: In-memory only (ephemeral)
- Document Source: `/docs` folder loaded at startup

### Document Processing Pipeline

1. **Startup Process**: Automatically loads and processes all files in `/docs` folder
2. **Document Structure**: Expects structured format with course metadata headers
3. **Chunking Strategy**: Sentence-aware splitting with configurable overlap
4. **Context Enhancement**: Prepends course/lesson context to chunks for better retrieval

### Development Workflow

- **Hot Reload**: Backend automatically reloads on file changes when using `--reload` flag
- **Environment**: Requires `.env` file with `ANTHROPIC_API_KEY`
- **Dependencies**: Python 3.13+ and uv package manager required
- **Frontend**: Vanilla HTML/CSS/JavaScript served by FastAPI as static files

### Key Integration Points

**Embedding Generation**: Happens twice in the flow
- Document processing (startup): Text chunks → embeddings → ChromaDB storage  
- Query processing (runtime): User query → embedding → semantic search

**Claude Function Calling**: AI decides autonomously whether to search based on query context
- System prompt constrains to "one search per query maximum"
- Tool results fed back to Claude for final response synthesis

**Session Context**: Conversation history maintained in memory and passed to Claude for contextual responses
- always use uv to run the server, do not use pip directly
- make sure to use uv for all dependency management