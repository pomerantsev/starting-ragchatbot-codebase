"""
Shared fixtures and configuration for the RAG system tests.
"""
import pytest
import tempfile
import shutil
from unittest.mock import Mock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import sys
import os

# Add backend directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_system import RAGSystem
from vector_store import SearchResults
from models import Course, Lesson, CourseChunk


class MockConfig:
    """Mock configuration for RAG system testing"""
    CHUNK_SIZE = 800
    CHUNK_OVERLAP = 100
    CHROMA_PATH = "./test_chroma_db"
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    MAX_RESULTS = 5
    ANTHROPIC_API_KEY = "test_key"
    ANTHROPIC_MODEL = "claude-3-sonnet-20240229"
    MAX_HISTORY = 10


@pytest.fixture
def mock_config():
    """Provide a mock configuration for testing"""
    return MockConfig()


@pytest.fixture
def temp_chroma_dir():
    """Create a temporary directory for ChromaDB testing"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_rag_system():
    """Create a fully mocked RAG system for testing"""
    with patch('rag_system.DocumentProcessor'), \
         patch('rag_system.VectorStore'), \
         patch('rag_system.AIGenerator'), \
         patch('rag_system.SessionManager'):
        
        config = MockConfig()
        rag_system = RAGSystem(config)
        
        # Setup default mock behaviors
        rag_system.vector_store = Mock()
        rag_system.ai_generator = Mock()
        rag_system.session_manager = Mock()
        rag_system.tool_manager = Mock()
        
        # Default successful responses
        rag_system.ai_generator.generate_response.return_value = "Mock response"
        rag_system.tool_manager.get_last_sources.return_value = []
        rag_system.tool_manager.get_tool_definitions.return_value = [
            {"name": "search_course_content", "description": "Search course materials"}
        ]
        rag_system.session_manager.get_conversation_history.return_value = None
        
        yield rag_system


@pytest.fixture
def sample_course_data():
    """Provide sample course data for testing"""
    return {
        "course": Course(
            id="test_course",
            title="Test Course",
            description="A test course for testing",
            lessons=[]
        ),
        "lesson": Lesson(
            id="test_lesson",
            title="Test Lesson", 
            content="This is test lesson content about Python programming."
        ),
        "chunk": CourseChunk(
            id="test_chunk",
            course_id="test_course",
            lesson_id="test_lesson",
            content="Test chunk content",
            embedding=[0.1] * 384,
            metadata={"source": "test"}
        )
    }


@pytest.fixture
def sample_search_results():
    """Provide sample search results for testing"""
    return SearchResults(
        chunks=[
            CourseChunk(
                id="chunk1",
                course_id="course1",
                lesson_id="lesson1",
                content="Python is a programming language",
                embedding=[0.1] * 384,
                metadata={"course_title": "Python Basics", "lesson_title": "Introduction"}
            ),
            CourseChunk(
                id="chunk2", 
                course_id="course1",
                lesson_id="lesson2",
                content="Variables store data in Python",
                embedding=[0.2] * 384,
                metadata={"course_title": "Python Basics", "lesson_title": "Variables"}
            )
        ],
        similarities=[0.9, 0.8]
    )


# Pydantic models for API testing
class QueryRequest(BaseModel):
    """Request model for course queries"""
    query: str
    session_id: Optional[str] = None


class QueryResponse(BaseModel):
    """Response model for course queries"""
    answer: str
    sources: List[Dict[str, Any]]
    session_id: str


class CourseStats(BaseModel):
    """Response model for course statistics"""
    total_courses: int
    course_titles: List[str]


@pytest.fixture
def test_app():
    """Create a test FastAPI app without static file mounting"""
    app = FastAPI(title="Test Course Materials RAG System")
    
    # Add CORS middleware for testing
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Mock RAG system for the app
    mock_rag_system = Mock()
    mock_rag_system.session_manager.create_session.return_value = "test_session_123"
    mock_rag_system.query.return_value = ("Test response", [])
    mock_rag_system.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["Python Basics", "Web Development"]
    }
    
    # Define API endpoints inline to avoid static file issues
    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id
            if not session_id:
                session_id = mock_rag_system.session_manager.create_session()
            
            answer, sources = mock_rag_system.query(request.query, session_id)
            
            return QueryResponse(
                answer=answer,
                sources=sources,
                session_id=session_id
            )
        except Exception as e:
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = mock_rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"]
            )
        except Exception as e:
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/session/clear")
    async def clear_session(session_id: str):
        try:
            mock_rag_system.session_manager.clear_session(session_id)
            return {"status": "success", "message": "Session cleared successfully"}
        except Exception as e:
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/")
    async def read_root():
        return {"message": "RAG System API"}
    
    # Make mock_rag_system accessible for testing
    app.state.rag_system = mock_rag_system
    
    yield app


@pytest.fixture
def client(test_app):
    """Create a test client for the FastAPI app"""
    return TestClient(test_app)


@pytest.fixture
def mock_anthropic_response():
    """Mock response from Anthropic API"""
    return {
        "content": [
            {
                "type": "text",
                "text": "This is a mock response from Claude"
            }
        ],
        "stop_reason": "end_turn",
        "usage": {
            "input_tokens": 100,
            "output_tokens": 50
        }
    }


@pytest.fixture
def mock_search_sources():
    """Mock search sources for testing"""
    return [
        {
            "text": "Python Basics - Lesson 1: Introduction to Python programming",
            "link": "http://example.com/courses/python/lesson1"
        },
        {
            "text": "Python Basics - Lesson 2: Variables and data types",
            "link": "http://example.com/courses/python/lesson2" 
        }
    ]


@pytest.fixture(autouse=True)
def cleanup_mocks():
    """Automatically cleanup mocks after each test"""
    yield
    # Any cleanup code would go here if needed


@pytest.fixture
def mock_session_id():
    """Provide a consistent session ID for testing"""
    return "test_session_12345"


@pytest.fixture
def mock_conversation_history():
    """Provide mock conversation history"""
    return (
        "User: What is Python?\n"
        "Assistant: Python is a high-level programming language known for its simplicity.\n"
        "User: How do I install it?\n"
        "Assistant: You can install Python from python.org or use a package manager."
    )