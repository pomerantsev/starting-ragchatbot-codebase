import os
import sys
from unittest.mock import MagicMock, Mock

import pytest

# Add backend directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search_tools import CourseSearchTool
from vector_store import SearchResults


class TestCourseSearchToolExecute:
    """Test suite for CourseSearchTool.execute method"""

    def setup_method(self):
        """Set up test fixtures"""
        self.mock_vector_store = Mock()
        self.search_tool = CourseSearchTool(self.mock_vector_store)

    def test_successful_search_basic_query(self):
        """Test successful search with basic query"""
        # Arrange
        mock_results = SearchResults(
            documents=["Course content about Python programming"],
            metadata=[{"course_title": "Python Basics", "lesson_number": 1}],
            distances=[0.5],
        )
        self.mock_vector_store.search.return_value = mock_results
        self.mock_vector_store.get_lesson_link.return_value = (
            "https://example.com/lesson1"
        )

        # Act
        result = self.search_tool.execute("Python programming")

        # Assert
        assert result is not None
        assert "Python Basics" in result
        assert "Course content about Python programming" in result
        assert "[Python Basics - Lesson 1]" in result
        self.mock_vector_store.search.assert_called_once_with(
            query="Python programming", course_name=None, lesson_number=None
        )

    def test_successful_search_with_course_filter(self):
        """Test successful search with course name filter"""
        # Arrange
        mock_results = SearchResults(
            documents=["Advanced Python concepts"],
            metadata=[{"course_title": "Advanced Python", "lesson_number": 3}],
            distances=[0.3],
        )
        self.mock_vector_store.search.return_value = mock_results
        self.mock_vector_store.get_lesson_link.return_value = (
            "https://example.com/lesson3"
        )

        # Act
        result = self.search_tool.execute("concepts", course_name="Advanced Python")

        # Assert
        assert "Advanced Python" in result
        assert "Advanced Python concepts" in result
        self.mock_vector_store.search.assert_called_once_with(
            query="concepts", course_name="Advanced Python", lesson_number=None
        )

    def test_successful_search_with_lesson_filter(self):
        """Test successful search with lesson number filter"""
        # Arrange
        mock_results = SearchResults(
            documents=["Lesson 2 content about variables"],
            metadata=[{"course_title": "Python Basics", "lesson_number": 2}],
            distances=[0.4],
        )
        self.mock_vector_store.search.return_value = mock_results
        self.mock_vector_store.get_lesson_link.return_value = (
            "https://example.com/lesson2"
        )

        # Act
        result = self.search_tool.execute("variables", lesson_number=2)

        # Assert
        assert "Python Basics" in result
        assert "variables" in result
        assert "Lesson 2" in result
        self.mock_vector_store.search.assert_called_once_with(
            query="variables", course_name=None, lesson_number=2
        )

    def test_successful_search_with_both_filters(self):
        """Test successful search with both course name and lesson number filters"""
        # Arrange
        mock_results = SearchResults(
            documents=["Specific lesson content"],
            metadata=[{"course_title": "Python Advanced", "lesson_number": 5}],
            distances=[0.2],
        )
        self.mock_vector_store.search.return_value = mock_results
        self.mock_vector_store.get_lesson_link.return_value = (
            "https://example.com/lesson5"
        )

        # Act
        result = self.search_tool.execute(
            "specific", course_name="Python Advanced", lesson_number=5
        )

        # Assert
        assert "Python Advanced" in result
        assert "Specific lesson content" in result
        self.mock_vector_store.search.assert_called_once_with(
            query="specific", course_name="Python Advanced", lesson_number=5
        )

    def test_search_error_handling(self):
        """Test error handling when search returns error"""
        # Arrange
        mock_results = SearchResults(
            documents=[], metadata=[], distances=[], error="Database connection failed"
        )
        self.mock_vector_store.search.return_value = mock_results

        # Act
        result = self.search_tool.execute("test query")

        # Assert
        assert result == "Database connection failed"

    def test_empty_results_no_filters(self):
        """Test handling of empty results with no filters"""
        # Arrange
        mock_results = SearchResults(documents=[], metadata=[], distances=[])
        self.mock_vector_store.search.return_value = mock_results

        # Act
        result = self.search_tool.execute("nonexistent content")

        # Assert
        assert result == "No relevant content found."

    def test_empty_results_with_course_filter(self):
        """Test handling of empty results with course filter"""
        # Arrange
        mock_results = SearchResults(documents=[], metadata=[], distances=[])
        self.mock_vector_store.search.return_value = mock_results

        # Act
        result = self.search_tool.execute("content", course_name="Nonexistent Course")

        # Assert
        assert result == "No relevant content found in course 'Nonexistent Course'."

    def test_empty_results_with_lesson_filter(self):
        """Test handling of empty results with lesson filter"""
        # Arrange
        mock_results = SearchResults(documents=[], metadata=[], distances=[])
        self.mock_vector_store.search.return_value = mock_results

        # Act
        result = self.search_tool.execute("content", lesson_number=99)

        # Assert
        assert result == "No relevant content found in lesson 99."

    def test_empty_results_with_both_filters(self):
        """Test handling of empty results with both filters"""
        # Arrange
        mock_results = SearchResults(documents=[], metadata=[], distances=[])
        self.mock_vector_store.search.return_value = mock_results

        # Act
        result = self.search_tool.execute(
            "content", course_name="Test Course", lesson_number=5
        )

        # Assert
        assert (
            result == "No relevant content found in course 'Test Course' in lesson 5."
        )

    def test_multiple_results_formatting(self):
        """Test formatting of multiple search results"""
        # Arrange
        mock_results = SearchResults(
            documents=["First piece of content", "Second piece of content"],
            metadata=[
                {"course_title": "Course A", "lesson_number": 1},
                {"course_title": "Course B", "lesson_number": 2},
            ],
            distances=[0.3, 0.4],
        )
        self.mock_vector_store.search.return_value = mock_results
        self.mock_vector_store.get_lesson_link.side_effect = [
            "https://example.com/courseA/lesson1",
            "https://example.com/courseB/lesson2",
        ]

        # Act
        result = self.search_tool.execute("content")

        # Assert
        assert "[Course A - Lesson 1]" in result
        assert "[Course B - Lesson 2]" in result
        assert "First piece of content" in result
        assert "Second piece of content" in result
        # Check that results are separated by double newlines
        assert "\n\n" in result

    def test_sources_tracking(self):
        """Test that search tool tracks sources correctly"""
        # Arrange
        mock_results = SearchResults(
            documents=["Test content"],
            metadata=[{"course_title": "Test Course", "lesson_number": 3}],
            distances=[0.5],
        )
        self.mock_vector_store.search.return_value = mock_results
        self.mock_vector_store.get_lesson_link.return_value = "https://example.com/test"

        # Act
        result = self.search_tool.execute("test")

        # Assert
        assert len(self.search_tool.last_sources) == 1
        source = self.search_tool.last_sources[0]
        assert source["text"] == "Test Course - Lesson 3"
        assert source["link"] == "https://example.com/test"

    def test_missing_lesson_number_in_metadata(self):
        """Test handling when lesson_number is missing from metadata"""
        # Arrange
        mock_results = SearchResults(
            documents=["Course overview content"],
            metadata=[{"course_title": "Overview Course"}],  # No lesson_number
            distances=[0.4],
        )
        self.mock_vector_store.search.return_value = mock_results

        # Act
        result = self.search_tool.execute("overview")

        # Assert
        assert "[Overview Course]" in result  # No lesson number in header
        assert "Course overview content" in result
        # Should track source without lesson number
        assert len(self.search_tool.last_sources) == 1
        assert self.search_tool.last_sources[0]["text"] == "Overview Course"
        assert self.search_tool.last_sources[0]["link"] is None

    def test_course_title_unknown_fallback(self):
        """Test handling when course_title is missing from metadata"""
        # Arrange
        mock_results = SearchResults(
            documents=["Content with missing course title"],
            metadata=[{"lesson_number": 1}],  # No course_title
            distances=[0.6],
        )
        self.mock_vector_store.search.return_value = mock_results
        self.mock_vector_store.get_lesson_link.return_value = None

        # Act
        result = self.search_tool.execute("content")

        # Assert
        assert "[unknown - Lesson 1]" in result
        assert "Content with missing course title" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
