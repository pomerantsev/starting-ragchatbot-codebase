"""
API endpoint tests for the RAG system FastAPI application.
Tests all endpoints for proper request/response handling.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import json


@pytest.mark.api
class TestQueryEndpoint:
    """Tests for /api/query endpoint"""
    
    def test_query_endpoint_success(self, client):
        """Test successful query with response and sources"""
        # Arrange
        request_data = {
            "query": "What is Python programming?",
            "session_id": "test_session"
        }
        
        # Mock the RAG system response
        client.app.state.rag_system.query.return_value = (
            "Python is a high-level programming language.",
            [{"text": "Python Basics", "link": "http://example.com/python"}]
        )
        
        # Act
        response = client.post("/api/query", json=request_data)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Python is a high-level programming language."
        assert len(data["sources"]) == 1
        assert data["sources"][0]["text"] == "Python Basics"
        assert data["session_id"] == "test_session"
        
        # Verify RAG system was called correctly
        client.app.state.rag_system.query.assert_called_once_with(
            "What is Python programming?", "test_session"
        )
    
    def test_query_endpoint_without_session_id(self, client):
        """Test query without providing session_id (should create new one)"""
        # Arrange
        request_data = {"query": "How do I learn Python?"}
        
        client.app.state.rag_system.query.return_value = (
            "Start with the basics and practice regularly.",
            []
        )
        
        # Act
        response = client.post("/api/query", json=request_data)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test_session_123"  # From fixture
        
        # Verify session creation was called
        client.app.state.rag_system.session_manager.create_session.assert_called_once()
    
    def test_query_endpoint_empty_query(self, client):
        """Test query endpoint with empty query string"""
        # Arrange
        request_data = {"query": ""}
        
        client.app.state.rag_system.query.return_value = (
            "I need more information to help you.",
            []
        )
        
        # Act
        response = client.post("/api/query", json=request_data)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "need more information" in data["answer"].lower()
    
    def test_query_endpoint_missing_query(self, client):
        """Test query endpoint with missing query field"""
        # Arrange
        request_data = {"session_id": "test"}
        
        # Act
        response = client.post("/api/query", json=request_data)
        
        # Assert
        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "detail" in data
        assert any("query" in str(error) for error in data["detail"])
    
    def test_query_endpoint_invalid_json(self, client):
        """Test query endpoint with invalid JSON"""
        # Act
        response = client.post(
            "/api/query",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        # Assert
        assert response.status_code == 422
    
    def test_query_endpoint_rag_system_error(self, client):
        """Test query endpoint when RAG system raises exception"""
        # Arrange
        request_data = {"query": "Test query"}
        
        client.app.state.rag_system.query.side_effect = Exception("RAG system error")
        
        # Act
        response = client.post("/api/query", json=request_data)
        
        # Assert
        assert response.status_code == 500
        data = response.json()
        assert "RAG system error" in data["detail"]
    
    def test_query_endpoint_with_sources(self, client):
        """Test query endpoint returns properly structured sources"""
        # Arrange
        request_data = {"query": "Python functions"}
        
        mock_sources = [
            {
                "text": "Python Functions - Chapter 3: Defining and calling functions",
                "link": "http://example.com/courses/python/functions"
            },
            {
                "text": "Advanced Python - Chapter 1: Lambda functions and closures", 
                "link": "http://example.com/courses/advanced-python/lambdas"
            }
        ]
        
        client.app.state.rag_system.query.return_value = (
            "Functions in Python are defined using the def keyword.",
            mock_sources
        )
        
        # Act
        response = client.post("/api/query", json=request_data)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["sources"]) == 2
        assert data["sources"][0]["text"] == "Python Functions - Chapter 3: Defining and calling functions"
        assert data["sources"][1]["link"] == "http://example.com/courses/advanced-python/lambdas"
    
    def test_query_endpoint_long_query(self, client):
        """Test query endpoint with very long query"""
        # Arrange
        long_query = "What is Python programming? " * 100
        request_data = {"query": long_query}
        
        client.app.state.rag_system.query.return_value = (
            "Python is a programming language.",
            []
        )
        
        # Act
        response = client.post("/api/query", json=request_data)
        
        # Assert
        assert response.status_code == 200
        client.app.state.rag_system.query.assert_called_once_with(long_query, "test_session_123")


@pytest.mark.api
class TestCoursesEndpoint:
    """Tests for /api/courses endpoint"""
    
    def test_courses_endpoint_success(self, client):
        """Test successful course statistics retrieval"""
        # Arrange
        mock_analytics = {
            "total_courses": 3,
            "course_titles": ["Python Basics", "Web Development", "Data Science"]
        }
        client.app.state.rag_system.get_course_analytics.return_value = mock_analytics
        
        # Act
        response = client.get("/api/courses")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total_courses"] == 3
        assert len(data["course_titles"]) == 3
        assert "Python Basics" in data["course_titles"]
        assert "Data Science" in data["course_titles"]
        
        # Verify RAG system method was called
        client.app.state.rag_system.get_course_analytics.assert_called_once()
    
    def test_courses_endpoint_empty_courses(self, client):
        """Test courses endpoint when no courses are available"""
        # Arrange
        client.app.state.rag_system.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": []
        }
        
        # Act
        response = client.get("/api/courses")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total_courses"] == 0
        assert data["course_titles"] == []
    
    def test_courses_endpoint_rag_system_error(self, client):
        """Test courses endpoint when RAG system raises exception"""
        # Arrange
        client.app.state.rag_system.get_course_analytics.side_effect = Exception("Analytics error")
        
        # Act
        response = client.get("/api/courses")
        
        # Assert
        assert response.status_code == 500
        data = response.json()
        assert "Analytics error" in data["detail"]


@pytest.mark.api
class TestSessionClearEndpoint:
    """Tests for /api/session/clear endpoint"""
    
    def test_session_clear_success(self, client):
        """Test successful session clearing"""
        # Arrange
        session_id = "test_session_123"
        
        # Act
        response = client.post(f"/api/session/clear?session_id={session_id}")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "cleared successfully" in data["message"]
        
        # Verify session manager was called
        client.app.state.rag_system.session_manager.clear_session.assert_called_once_with(session_id)
    
    def test_session_clear_missing_session_id(self, client):
        """Test session clear without session_id parameter"""
        # Act
        response = client.post("/api/session/clear")
        
        # Assert
        assert response.status_code == 422  # Missing required parameter
    
    def test_session_clear_error(self, client):
        """Test session clear when session manager raises exception"""
        # Arrange
        session_id = "invalid_session"
        client.app.state.rag_system.session_manager.clear_session.side_effect = Exception("Session not found")
        
        # Act
        response = client.post(f"/api/session/clear?session_id={session_id}")
        
        # Assert
        assert response.status_code == 500
        data = response.json()
        assert "Session not found" in data["detail"]


@pytest.mark.api
class TestRootEndpoint:
    """Tests for / (root) endpoint"""
    
    def test_root_endpoint(self, client):
        """Test root endpoint returns basic API info"""
        # Act
        response = client.get("/")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "RAG System API" in data["message"]


@pytest.mark.api
class TestAPIIntegration:
    """Integration tests for API endpoints"""
    
    def test_query_and_courses_endpoints_together(self, client):
        """Test using query and courses endpoints in sequence"""
        # First, get course statistics
        client.app.state.rag_system.get_course_analytics.return_value = {
            "total_courses": 2,
            "course_titles": ["Python Basics", "Web Development"]
        }
        
        courses_response = client.get("/api/courses")
        assert courses_response.status_code == 200
        
        # Then, make a query
        client.app.state.rag_system.query.return_value = (
            "Python is covered in the Python Basics course.",
            [{"text": "Python Basics - Lesson 1", "link": "http://example.com"}]
        )
        
        query_response = client.post("/api/query", json={"query": "Tell me about Python"})
        assert query_response.status_code == 200
        
        # Verify both responses are correct
        courses_data = courses_response.json()
        query_data = query_response.json()
        
        assert courses_data["total_courses"] == 2
        assert "Python" in query_data["answer"]
    
    def test_session_lifecycle(self, client):
        """Test creating, using, and clearing a session"""
        session_id = "lifecycle_test_session"
        
        # Make a query with specific session
        client.app.state.rag_system.query.return_value = ("First response", [])
        query1_response = client.post("/api/query", json={
            "query": "First question",
            "session_id": session_id
        })
        assert query1_response.status_code == 200
        
        # Make another query with same session
        client.app.state.rag_system.query.return_value = ("Second response", [])
        query2_response = client.post("/api/query", json={
            "query": "Second question", 
            "session_id": session_id
        })
        assert query2_response.status_code == 200
        
        # Clear the session
        clear_response = client.post(f"/api/session/clear?session_id={session_id}")
        assert clear_response.status_code == 200
        
        # Verify all calls were made with correct session
        assert client.app.state.rag_system.query.call_count == 2
        client.app.state.rag_system.session_manager.clear_session.assert_called_once_with(session_id)
    
    def test_error_handling_consistency(self, client):
        """Test that all endpoints handle errors consistently"""
        # Test query endpoint error
        client.app.state.rag_system.query.side_effect = Exception("Query error")
        query_response = client.post("/api/query", json={"query": "test"})
        assert query_response.status_code == 500
        
        # Test courses endpoint error
        client.app.state.rag_system.get_course_analytics.side_effect = Exception("Analytics error")
        courses_response = client.get("/api/courses")
        assert courses_response.status_code == 500
        
        # Test session clear error
        client.app.state.rag_system.session_manager.clear_session.side_effect = Exception("Clear error")
        clear_response = client.post("/api/session/clear?session_id=test")
        assert clear_response.status_code == 500
        
        # All should have consistent error structure
        for response in [query_response, courses_response, clear_response]:
            data = response.json()
            assert "detail" in data
            assert "error" in data["detail"].lower()


@pytest.mark.api
class TestAPIValidation:
    """Tests for API request validation"""
    
    def test_query_request_validation(self, client):
        """Test query request model validation"""
        # Test with invalid data types
        invalid_requests = [
            {"query": 123},  # query should be string
            {"query": "valid", "session_id": 123},  # session_id should be string
            {"query": None},  # query cannot be null
        ]
        
        for invalid_request in invalid_requests:
            response = client.post("/api/query", json=invalid_request)
            assert response.status_code == 422
            
    def test_query_response_structure(self, client):
        """Test that query responses have correct structure"""
        # Arrange
        client.app.state.rag_system.query.return_value = (
            "Test answer",
            [{"text": "source", "link": "http://example.com"}]
        )
        
        # Act
        response = client.post("/api/query", json={"query": "test"})
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields exist
        required_fields = ["answer", "sources", "session_id"]
        for field in required_fields:
            assert field in data
            
        # Check data types
        assert isinstance(data["answer"], str)
        assert isinstance(data["sources"], list)
        assert isinstance(data["session_id"], str)
    
    def test_courses_response_structure(self, client):
        """Test that courses responses have correct structure"""
        # Act
        response = client.get("/api/courses")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields
        assert "total_courses" in data
        assert "course_titles" in data
        
        # Check data types
        assert isinstance(data["total_courses"], int)
        assert isinstance(data["course_titles"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])