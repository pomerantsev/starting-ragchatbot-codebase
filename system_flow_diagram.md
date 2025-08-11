# RAG Chatbot System Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                FRONTEND (Browser)                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│  User Interface (index.html + script.js + style.css)                            │
│                                                                                 │
│  1. User types: "How do I learn Python?"                                       │
│  2. sendMessage() triggered                                                     │
│  3. POST /api/query { query: "...", session_id: "..." }                       │
│                                    │                                           │
└────────────────────────────────────┼───────────────────────────────────────────┘
                                     │ HTTP Request
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            FASTAPI SERVER (app.py)                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│  @app.post("/api/query")                                                        │
│  async def query_documents(request: QueryRequest):                             │
│    4. Extract query + session_id from request                                  │
│    5. Call rag_system.query(request.query, session_id)                        │
│                                    │                                           │
└────────────────────────────────────┼───────────────────────────────────────────┘
                                     │ Function Call
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         RAG SYSTEM ORCHESTRATOR (rag_system.py)                │
├─────────────────────────────────────────────────────────────────────────────────┤
│  def query(self, query: str, session_id: str):                                 │
│    6. Get conversation history from session_manager                            │
│    7. Build prompt: "Answer this question about course materials: {query}"    │
│    8. Call ai_generator.generate_response(...)                                 │
│                                    │                                           │
└────────────────────────────────────┼───────────────────────────────────────────┘
                                     │ Function Call
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        AI GENERATOR (ai_generator.py)                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│  def generate_response(self, query, tools, tool_manager):                      │
│    9. Call Anthropic Claude API with:                                          │
│       - System prompt (course materials assistant)                             │
│       - User query                                                             │
│       - Available search tools                                                 │
│       - Conversation history                                                   │
│                                    │                                           │
└────────────────────────────────────┼───────────────────────────────────────────┘
                                     │ API Call
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          ANTHROPIC CLAUDE API                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│  10. Claude analyzes query: "This looks like a course content question"        │
│  11. Claude decides: "I should search for Python learning materials"          │
│  12. Claude responds with tool_use: search_course_content(query="Python")     │
│                                    │                                           │
└────────────────────────────────────┼───────────────────────────────────────────┘
                                     │ Tool Use Response
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        TOOL MANAGER (search_tools.py)                          │
├─────────────────────────────────────────────────────────────────────────────────┤
│  def execute_tool(self, tool_name, **kwargs):                                  │
│    13. Route to CourseSearchTool.search_course_content(query="Python")        │
│    14. Call vector_store.search(query="Python")                               │
│                                    │                                           │
└────────────────────────────────────┼───────────────────────────────────────────┘
                                     │ Function Call
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         VECTOR STORE (vector_store.py)                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│  def search(self, query: str):                                                 │
│    15. Query gets embedded by SentenceTransformer                             │
│        "Python" → [0.1, -0.3, 0.7, ..., 0.2] (384-dim vector)               │
│    16. Call chromadb.query(query_embeddings=[...])                            │
│                                    │                                           │
└────────────────────────────────────┼───────────────────────────────────────────┘
                                     │ Vector Search
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            CHROMADB DATABASE                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│  Stored Data:                                                                  │
│  • Course chunks as 384-dim vectors                                            │
│  • Original text content                                                       │
│  • Metadata (course_title, lesson_number, etc.)                              │
│                                                                                 │
│  17. Compute cosine similarity between query vector and all stored vectors     │
│  18. Return top 5 most similar chunks:                                         │
│      - "Course Building Towards Computer Use Lesson 2: Python basics..."      │
│      - "Course Python Fundamentals Lesson 1: Getting started with..."        │
│                                    │                                           │
└────────────────────────────────────┼───────────────────────────────────────────┘
                                     │ Search Results
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    RETURN PATH: Results Flow Back                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│  19. ChromaDB → VectorStore: Relevant text chunks + metadata                   │
│  20. VectorStore → ToolManager: Formatted search results                       │
│  21. ToolManager → AIGenerator: Tool execution results                         │
│  22. AIGenerator → Claude API: Send search results as tool_result              │
│                                    │                                           │
└────────────────────────────────────┼───────────────────────────────────────────┘
                                     │ Second API Call
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     CLAUDE FINAL RESPONSE GENERATION                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│  23. Claude receives search results about Python learning                      │
│  24. Claude synthesizes information:                                           │
│      "Based on the course materials, here's how to learn Python:              │
│       1. Start with variables and data types                                   │
│       2. Practice with loops and conditionals..."                              │
│  25. Returns final natural language response                                   │
│                                    │                                           │
└────────────────────────────────────┼───────────────────────────────────────────┘
                                     │ Final Response
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         RESPONSE JOURNEY BACK                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│  26. AIGenerator → RAGSystem: Final response + sources                         │
│  27. RAGSystem → SessionManager: Store conversation history                    │
│  28. RAGSystem → FastAPI: Return (answer, sources, session_id)                │
│  29. FastAPI → Frontend: JSON response                                         │
│  30. Frontend → User: Display answer with collapsible sources                  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

CONCURRENT PROCESSES:
┌─────────────────────┐  ┌──────────────────────┐  ┌─────────────────────────┐
│   SESSION MANAGER   │  │  DOCUMENT PROCESSOR  │  │    STARTUP PROCESS      │
│   (session_manager  │  │  (document_processor │  │                         │
│        .py)         │  │        .py)          │  │  On server startup:     │
│                     │  │                      │  │  1. Load docs/ folder   │
│ • In-memory storage │  │ • Parse course files │  │  2. Process documents   │
│ • Track conversation│  │ • Extract metadata   │  │  3. Create embeddings   │
│ • Limit history     │  │ • Chunk text         │  │  4. Populate ChromaDB   │
│ • session_1, 2, 3..│  │ • Structure lessons  │  │                         │
└─────────────────────┘  └──────────────────────┘  └─────────────────────────┘

KEY DATA STRUCTURES:
• Frontend: sessionId (string), query (string)
• FastAPI: QueryRequest/Response (Pydantic models)  
• RAG System: Course, Lesson, CourseChunk objects
• Vector Store: 384-dim embeddings + metadata
• AI Generator: Messages list for Claude API
• Session Manager: Dict[session_id, List[Message]]
```

## Key Insights from the Flow:

1. **Claude is the Orchestrator**: AI decides whether/when to search autonomously
2. **Embeddings Happen Twice**: 
   - Documents → vectors (at startup)
   - User query → vector (at search time)
3. **Two Claude API Calls**: 
   - First: "Should I search?" → Tool use decision
   - Second: "Generate final answer" → Natural language response
4. **Memory-Only Sessions**: Lost on server restart
5. **Semantic Search**: Similarity in 384-dimensional space, not keyword matching