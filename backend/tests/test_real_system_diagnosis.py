"""
Diagnostic tests for the real RAG system to identify the root cause of 'query failed' issues.
These tests run against the actual system components without mocking.
"""

import os
import sys
from unittest.mock import patch

import pytest

# Add backend directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_generator import AIGenerator
from config import config
from rag_system import RAGSystem
from search_tools import CourseSearchTool, ToolManager
from vector_store import VectorStore


class TestRealSystemDiagnosis:
    """Diagnostic tests against the real system components"""

    def setup_method(self):
        """Set up real system components for testing"""
        # Use the real config but override API key to avoid actual API calls
        self.config = config

        # Create real vector store
        self.vector_store = VectorStore(
            chroma_path=self.config.CHROMA_PATH,
            embedding_model=self.config.EMBEDDING_MODEL,
            max_results=self.config.MAX_RESULTS,
        )

        # Create real search tool
        self.search_tool = CourseSearchTool(self.vector_store)

        # Create real tool manager
        self.tool_manager = ToolManager()
        self.tool_manager.register_tool(self.search_tool)

    def test_vector_store_connection(self):
        """Test if vector store can connect and has data"""
        try:
            # Check if vector store can connect
            course_count = self.vector_store.get_course_count()
            print(f"Vector store course count: {course_count}")

            # Check if we have any course titles
            course_titles = self.vector_store.get_existing_course_titles()
            print(f"Existing course titles: {course_titles}")

            assert (
                course_count >= 0
            ), "Vector store should return non-negative course count"

            if course_count == 0:
                pytest.fail(
                    "No courses found in vector store - this explains 'query failed'"
                )

        except Exception as e:
            pytest.fail(f"Vector store connection failed: {e}")

    def test_vector_store_search_functionality(self):
        """Test if vector store search works with real data"""
        try:
            # Test basic search
            results = self.vector_store.search("Python")
            print(
                f"Search results for 'Python': {len(results.documents) if not results.error else 'ERROR: ' + results.error}"
            )

            if results.error:
                pytest.fail(f"Vector store search returned error: {results.error}")

            # Test search with specific course (if any exist)
            course_titles = self.vector_store.get_existing_course_titles()
            if course_titles:
                first_course = course_titles[0]
                results = self.vector_store.search(
                    "introduction", course_name=first_course
                )
                print(
                    f"Search results for 'introduction' in '{first_course}': {len(results.documents) if not results.error else 'ERROR: ' + results.error}"
                )

                if results.error:
                    pytest.fail(
                        f"Vector store search with course filter failed: {results.error}"
                    )

        except Exception as e:
            pytest.fail(f"Vector store search functionality failed: {e}")

    def test_course_search_tool_with_real_data(self):
        """Test CourseSearchTool with real vector store data"""
        try:
            # Test basic search
            result = self.search_tool.execute("Python programming")
            print(
                f"CourseSearchTool result for 'Python programming': {result[:200]}..."
            )

            # Check for error conditions
            if "No relevant content found" in result:
                course_count = self.vector_store.get_course_count()
                if course_count == 0:
                    pytest.fail(
                        "CourseSearchTool returns 'No relevant content found' because vector store is empty"
                    )
                else:
                    print(
                        f"CourseSearchTool found no content despite {course_count} courses in vector store"
                    )

            # Test with existing course if available
            course_titles = self.vector_store.get_existing_course_titles()
            if course_titles:
                first_course = course_titles[0]
                result = self.search_tool.execute("basics", course_name=first_course)
                print(
                    f"CourseSearchTool result with course filter '{first_course}': {result[:200]}..."
                )

        except Exception as e:
            pytest.fail(f"CourseSearchTool execution failed: {e}")

    def test_embedding_model_loading(self):
        """Test if the embedding model can be loaded"""
        try:
            # Try to use the embedding function
            test_text = "This is a test sentence"
            # The embedding function is used internally by ChromaDB
            # We'll test it indirectly by doing a search
            results = self.vector_store.search(test_text)

            if results.error and "embedding" in results.error.lower():
                pytest.fail(f"Embedding model loading failed: {results.error}")

        except Exception as e:
            if "embedding" in str(e).lower() or "model" in str(e).lower():
                pytest.fail(f"Embedding model loading failed: {e}")
            else:
                # Re-raise if it's not related to embedding
                raise

    def test_chroma_db_persistence(self):
        """Test if ChromaDB data is persisted correctly"""
        try:
            # Check if the chroma_db directory exists
            chroma_path = self.config.CHROMA_PATH
            if not os.path.exists(chroma_path):
                pytest.fail(f"ChromaDB directory does not exist at: {chroma_path}")

            # Check if there are actual database files
            db_files = os.listdir(chroma_path)
            print(f"ChromaDB files: {db_files}")

            if not db_files:
                pytest.fail(
                    "ChromaDB directory exists but is empty - no data persisted"
                )

        except Exception as e:
            pytest.fail(f"ChromaDB persistence check failed: {e}")

    def test_course_name_resolution(self):
        """Test course name resolution functionality"""
        try:
            course_titles = self.vector_store.get_existing_course_titles()
            if not course_titles:
                pytest.skip("No courses available to test name resolution")

            # Test exact match
            first_course = course_titles[0]
            resolved = self.vector_store._resolve_course_name(first_course)
            print(f"Exact match resolution: '{first_course}' -> '{resolved}'")
            assert (
                resolved == first_course
            ), f"Exact match should return same course name"

            # Test partial match if course name is long enough
            if len(first_course.split()) > 1:
                partial_name = first_course.split()[0]  # First word
                resolved = self.vector_store._resolve_course_name(partial_name)
                print(f"Partial match resolution: '{partial_name}' -> '{resolved}'")
                # Should resolve to something (might not be exact match due to fuzzy search)
                assert (
                    resolved is not None
                ), f"Partial match should resolve to some course"

        except Exception as e:
            pytest.fail(f"Course name resolution failed: {e}")

    def test_tool_manager_functionality(self):
        """Test ToolManager with real tools"""
        try:
            # Test tool registration
            tool_definitions = self.tool_manager.get_tool_definitions()
            print(f"Registered tools: {[tool['name'] for tool in tool_definitions]}")

            assert len(tool_definitions) > 0, "No tools registered in ToolManager"

            # Test tool execution
            search_result = self.tool_manager.execute_tool(
                "search_course_content", query="Python"
            )
            print(f"Tool execution result: {search_result[:200]}...")

            if "not found" in search_result.lower():
                pytest.fail(f"Tool execution indicates tool not found: {search_result}")

        except Exception as e:
            pytest.fail(f"ToolManager functionality failed: {e}")

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake_key"})
    def test_ai_generator_initialization(self):
        """Test AIGenerator initialization (without making API calls)"""
        try:
            # Test that AIGenerator can be initialized
            ai_gen = AIGenerator("fake_api_key", self.config.ANTHROPIC_MODEL)

            # Test that system prompt is accessible
            assert hasattr(
                ai_gen, "SYSTEM_PROMPT"
            ), "AIGenerator should have SYSTEM_PROMPT"
            assert len(ai_gen.SYSTEM_PROMPT) > 0, "System prompt should not be empty"

            # Test that base parameters are set
            assert hasattr(ai_gen, "base_params"), "AIGenerator should have base_params"
            assert ai_gen.base_params["model"] == self.config.ANTHROPIC_MODEL

        except Exception as e:
            pytest.fail(f"AIGenerator initialization failed: {e}")

    def test_docs_folder_existence(self):
        """Test if docs folder exists and has content"""
        try:
            docs_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "docs"
            )
            print(f"Checking docs folder at: {docs_path}")

            if not os.path.exists(docs_path):
                pytest.fail(f"Docs folder does not exist at: {docs_path}")

            doc_files = [
                f
                for f in os.listdir(docs_path)
                if f.lower().endswith((".pdf", ".txt", ".docx"))
            ]
            print(f"Document files found: {doc_files}")

            if not doc_files:
                pytest.fail(
                    "Docs folder exists but contains no document files - this explains why vector store is empty"
                )

        except Exception as e:
            pytest.fail(f"Docs folder check failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])  # -s to see print statements
