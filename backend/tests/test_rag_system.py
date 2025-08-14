import os
import sys
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add backend directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Course, CourseChunk, Lesson
from rag_system import RAGSystem
from vector_store import SearchResults


class MockConfig:
    """Mock configuration for RAG system"""

    CHUNK_SIZE = 800
    CHUNK_OVERLAP = 100
    CHROMA_PATH = "./test_chroma_db"
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    MAX_RESULTS = 5
    ANTHROPIC_API_KEY = "test_key"
    ANTHROPIC_MODEL = "claude-3-sonnet-20240229"
    MAX_HISTORY = 10


class TestRAGSystemContentQueries:
    """Integration tests for RAG system handling content queries"""

    def setup_method(self):
        """Set up test fixtures with mocked dependencies"""
        with (
            patch("rag_system.DocumentProcessor"),
            patch("rag_system.VectorStore"),
            patch("rag_system.AIGenerator"),
            patch("rag_system.SessionManager"),
        ):

            self.config = MockConfig()
            self.rag_system = RAGSystem(self.config)

        # Setup mocks
        self.mock_vector_store = self.rag_system.vector_store
        self.mock_ai_generator = self.rag_system.ai_generator
        self.mock_session_manager = self.rag_system.session_manager
        self.mock_tool_manager = Mock()
        self.rag_system.tool_manager = self.mock_tool_manager

    def test_successful_content_query_with_results(self):
        """Test successful content query that finds relevant results"""
        # Arrange
        query = "What is Python programming?"
        expected_response = "Python is a high-level programming language..."
        mock_sources = [
            {"text": "Python Basics - Lesson 1", "link": "http://example.com/lesson1"}
        ]

        # Mock AI generator to return successful response
        self.mock_ai_generator.generate_response.return_value = expected_response

        # Mock tool manager to return sources
        self.mock_tool_manager.get_last_sources.return_value = mock_sources

        # Mock session manager
        self.mock_session_manager.get_conversation_history.return_value = None

        # Act
        response, sources = self.rag_system.query(query)

        # Assert
        assert response == expected_response
        assert sources == mock_sources

        # Verify AI generator was called with correct parameters
        self.mock_ai_generator.generate_response.assert_called_once()
        call_args = self.mock_ai_generator.generate_response.call_args[1]
        assert (
            "Answer this question about course materials: What is Python programming?"
            in call_args["query"]
        )
        assert call_args["conversation_history"] is None
        assert call_args["tools"] is not None
        assert call_args["tool_manager"] == self.mock_tool_manager

        # Verify sources were retrieved and reset
        self.mock_tool_manager.get_last_sources.assert_called_once()
        self.mock_tool_manager.reset_sources.assert_called_once()

    def test_content_query_with_session_history(self):
        """Test content query with existing conversation history"""
        # Arrange
        query = "Tell me more about variables"
        session_id = "test_session_123"
        history = "User: What is Python?\nAssistant: Python is a programming language."
        expected_response = "Variables in Python are used to store data..."

        self.mock_session_manager.get_conversation_history.return_value = history
        self.mock_ai_generator.generate_response.return_value = expected_response
        self.mock_tool_manager.get_last_sources.return_value = []

        # Act
        response, sources = self.rag_system.query(query, session_id=session_id)

        # Assert
        assert response == expected_response

        # Verify session handling
        self.mock_session_manager.get_conversation_history.assert_called_once_with(
            session_id
        )
        self.mock_session_manager.add_exchange.assert_called_once_with(
            session_id, query, expected_response
        )

        # Verify AI generator received history
        call_args = self.mock_ai_generator.generate_response.call_args[1]
        assert call_args["conversation_history"] == history

    def test_content_query_ai_generator_failure(self):
        """Test handling when AI generator fails"""
        # Arrange
        query = "What is machine learning?"
        self.mock_ai_generator.generate_response.side_effect = Exception("API error")

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            self.rag_system.query(query)

        assert "API error" in str(exc_info.value)

    def test_content_query_no_sources_returned(self):
        """Test content query when no sources are found"""
        # Arrange
        query = "What is quantum computing?"
        expected_response = "I don't have specific information about quantum computing in the course materials."

        self.mock_ai_generator.generate_response.return_value = expected_response
        self.mock_tool_manager.get_last_sources.return_value = []  # No sources found

        # Act
        response, sources = self.rag_system.query(query)

        # Assert
        assert response == expected_response
        assert sources == []

    def test_content_query_with_search_tool_error(self):
        """Test content query when search tool returns an error"""
        # Arrange
        query = "Find course content"
        # Mock AI generator to simulate tool execution that returns an error
        expected_response = "I encountered an issue searching the course materials."

        self.mock_ai_generator.generate_response.return_value = expected_response
        self.mock_tool_manager.get_last_sources.return_value = []

        # Act
        response, sources = self.rag_system.query(query)

        # Assert
        assert response == expected_response
        assert sources == []

    def test_multiple_content_queries_same_session(self):
        """Test multiple queries in the same session"""
        # Arrange
        session_id = "persistent_session"
        queries = [
            "What is Python?",
            "How do I use variables?",
            "What about functions?",
        ]
        responses = [
            "Python is a programming language.",
            "Variables store data in Python.",
            "Functions are reusable code blocks.",
        ]

        self.mock_ai_generator.generate_response.side_effect = responses
        self.mock_tool_manager.get_last_sources.return_value = []
        self.mock_session_manager.get_conversation_history.return_value = None

        # Act & Assert
        for i, query in enumerate(queries):
            response, sources = self.rag_system.query(query, session_id=session_id)
            assert response == responses[i]

        # Verify session updates
        assert self.mock_session_manager.add_exchange.call_count == 3

    def test_tool_definitions_passed_to_ai_generator(self):
        """Test that tool definitions are properly passed to AI generator"""
        # Arrange
        query = "Search for Python content"
        expected_tools = [
            {"name": "search_course_content", "description": "Search course materials"},
            {"name": "get_course_outline", "description": "Get course outline"},
        ]

        self.mock_tool_manager.get_tool_definitions.return_value = expected_tools
        self.mock_ai_generator.generate_response.return_value = (
            "Found Python content..."
        )
        self.mock_tool_manager.get_last_sources.return_value = []

        # Act
        response, sources = self.rag_system.query(query)

        # Assert
        self.mock_tool_manager.get_tool_definitions.assert_called_once()
        call_args = self.mock_ai_generator.generate_response.call_args[1]
        assert call_args["tools"] == expected_tools
        assert call_args["tool_manager"] == self.mock_tool_manager

    def test_query_prompt_formatting(self):
        """Test that query prompts are formatted correctly"""
        # Arrange
        query = "How do I learn Python effectively?"
        self.mock_ai_generator.generate_response.return_value = "Here are some tips..."
        self.mock_tool_manager.get_last_sources.return_value = []

        # Act
        self.rag_system.query(query)

        # Assert
        call_args = self.mock_ai_generator.generate_response.call_args[1]
        formatted_query = call_args["query"]
        assert "Answer this question about course materials:" in formatted_query
        assert query in formatted_query

    def test_sources_reset_after_query(self):
        """Test that sources are properly reset after each query"""
        # Arrange
        query = "Test query"
        mock_sources = [{"text": "Test Source", "link": "http://test.com"}]

        self.mock_ai_generator.generate_response.return_value = "Test response"
        self.mock_tool_manager.get_last_sources.return_value = mock_sources

        # Act
        response, sources = self.rag_system.query(query)

        # Assert
        assert sources == mock_sources
        self.mock_tool_manager.reset_sources.assert_called_once()

    def test_empty_query_handling(self):
        """Test handling of empty or whitespace-only queries"""
        # Arrange
        empty_queries = ["", "   ", "\n\t"]

        for query in empty_queries:
            # Reset mocks
            self.mock_ai_generator.generate_response.reset_mock()
            self.mock_tool_manager.get_last_sources.return_value = []
            self.mock_ai_generator.generate_response.return_value = (
                "I need more information to help you."
            )

            # Act
            response, sources = self.rag_system.query(query)

            # Assert - System should still process empty queries
            self.mock_ai_generator.generate_response.assert_called_once()

    def test_very_long_query_handling(self):
        """Test handling of very long queries"""
        # Arrange
        long_query = "What is Python? " * 100  # Very long query
        self.mock_ai_generator.generate_response.return_value = (
            "Python is a programming language..."
        )
        self.mock_tool_manager.get_last_sources.return_value = []

        # Act
        response, sources = self.rag_system.query(long_query)

        # Assert - Should handle long queries without error
        self.mock_ai_generator.generate_response.assert_called_once()
        call_args = self.mock_ai_generator.generate_response.call_args[1]
        assert long_query in call_args["query"]

    def test_special_characters_in_query(self):
        """Test handling of queries with special characters"""
        # Arrange
        special_query = "What is @Python & how does it handle $variables?"
        self.mock_ai_generator.generate_response.return_value = (
            "Python handles variables..."
        )
        self.mock_tool_manager.get_last_sources.return_value = []

        # Act
        response, sources = self.rag_system.query(special_query)

        # Assert
        self.mock_ai_generator.generate_response.assert_called_once()
        call_args = self.mock_ai_generator.generate_response.call_args[1]
        assert special_query in call_args["query"]


# Integration test that tests the actual query flow without mocking everything
class TestRAGSystemQueryFlow:
    """Test the actual query flow with minimal mocking"""

    @patch("rag_system.DocumentProcessor")
    @patch("rag_system.VectorStore")
    @patch("rag_system.AIGenerator")
    @patch("rag_system.SessionManager")
    def test_query_flow_integration(
        self,
        mock_session_mgr_class,
        mock_ai_gen_class,
        mock_vector_store_class,
        mock_doc_processor_class,
    ):
        """Test the integration of all components in a query"""
        # Arrange
        config = MockConfig()

        # Mock the classes to return mock instances
        mock_vector_store = Mock()
        mock_ai_generator = Mock()
        mock_session_manager = Mock()

        mock_vector_store_class.return_value = mock_vector_store
        mock_ai_gen_class.return_value = mock_ai_generator
        mock_session_mgr_class.return_value = mock_session_manager

        # Set up the RAG system
        rag_system = RAGSystem(config)

        # Mock AI generator response
        mock_ai_generator.generate_response.return_value = (
            "Python is a versatile programming language."
        )

        # Mock tool manager behavior
        mock_tool_manager = rag_system.tool_manager
        mock_tool_manager.get_last_sources = Mock(
            return_value=[
                {"text": "Python Course - Lesson 1", "link": "http://example.com"}
            ]
        )
        mock_tool_manager.reset_sources = Mock()
        mock_tool_manager.get_tool_definitions = Mock(
            return_value=[
                {"name": "search_course_content", "description": "Search courses"}
            ]
        )

        # Act
        response, sources = rag_system.query("What is Python programming?")

        # Assert
        assert response == "Python is a versatile programming language."
        assert len(sources) == 1
        assert sources[0]["text"] == "Python Course - Lesson 1"

        # Verify the flow
        mock_ai_generator.generate_response.assert_called_once()
        mock_tool_manager.get_last_sources.assert_called_once()
        mock_tool_manager.reset_sources.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
