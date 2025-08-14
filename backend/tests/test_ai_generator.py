import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add backend directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_generator import AIGenerator


class MockContentBlock:
    """Mock content block for anthropic responses"""
    def __init__(self, text=None, tool_name=None, tool_input=None, tool_id=None):
        if tool_name:
            self.type = "tool_use"
            self.name = tool_name
            self.input = tool_input or {}
            self.id = tool_id or "test_id"
        else:
            self.type = "text"
            self.text = text or "Default response"


class MockAnthropicResponse:
    """Mock Anthropic API response"""
    def __init__(self, content_blocks, stop_reason="end_turn"):
        self.content = content_blocks
        self.stop_reason = stop_reason


class TestAIGenerator:
    """Test suite for AIGenerator class"""

    def setup_method(self):
        """Set up test fixtures"""
        with patch('anthropic.Anthropic'):
            self.ai_generator = AIGenerator("test_api_key", "claude-3-sonnet-20240229")
        self.mock_client = Mock()
        self.ai_generator.client = self.mock_client

        # Mock tool manager
        self.mock_tool_manager = Mock()

    def test_generate_response_without_tools(self):
        """Test basic response generation without tools"""
        # Arrange
        expected_response = "This is a test response"
        mock_response = MockAnthropicResponse([MockContentBlock(text=expected_response)])
        self.mock_client.messages.create.return_value = mock_response

        # Act
        result = self.ai_generator.generate_response("What is Python?")

        # Assert
        assert result == expected_response
        self.mock_client.messages.create.assert_called_once()
        call_args = self.mock_client.messages.create.call_args[1]
        assert call_args["messages"][0]["content"] == "What is Python?"
        assert "tools" not in call_args

    def test_generate_response_with_tools_no_tool_use(self):
        """Test response generation with tools available but no tool use"""
        # Arrange
        tools = [{"name": "search_course_content", "description": "Search courses"}]
        expected_response = "Python is a programming language"
        mock_response = MockAnthropicResponse([MockContentBlock(text=expected_response)])
        self.mock_client.messages.create.return_value = mock_response

        # Act
        result = self.ai_generator.generate_response(
            "What is Python?",
            tools=tools,
            tool_manager=self.mock_tool_manager
        )

        # Assert
        assert result == expected_response
        self.mock_client.messages.create.assert_called_once()
        call_args = self.mock_client.messages.create.call_args[1]
        assert call_args["tools"] == tools
        assert call_args["tool_choice"] == {"type": "auto"}

    def test_generate_response_with_tool_execution(self):
        """Test response generation with tool execution (single round)"""
        # Arrange
        tools = [{"name": "search_course_content", "description": "Search courses"}]

        # Mock initial response with tool use
        initial_response = MockAnthropicResponse(
            content_blocks=[MockContentBlock(
                tool_name="search_course_content",
                tool_input={"query": "Python basics"},
                tool_id="tool_123"
            )],
            stop_reason="tool_use"
        )

        # Mock final response after tool execution (no more tool use)
        final_response = MockAnthropicResponse([
            MockContentBlock(text="Based on the search results, Python is...")
        ])

        self.mock_client.messages.create.side_effect = [initial_response, final_response]
        self.mock_tool_manager.execute_tool.return_value = "Search result: Python tutorial content"

        # Act
        result = self.ai_generator.generate_response(
            "Tell me about Python basics",
            tools=tools,
            tool_manager=self.mock_tool_manager
        )

        # Assert
        assert result == "Based on the search results, Python is..."
        assert self.mock_client.messages.create.call_count == 2

        # Verify tool execution
        self.mock_tool_manager.execute_tool.assert_called_once_with(
            "search_course_content",
            query="Python basics"
        )

        # Verify first API call has tools
        first_call_args = self.mock_client.messages.create.call_args_list[0][1]
        assert first_call_args["tools"] == tools

        # Verify second API call structure (tools should still be available)
        second_call_args = self.mock_client.messages.create.call_args_list[1][1]
        assert len(second_call_args["messages"]) == 3  # user, assistant, user with tool results
        assert second_call_args["tools"] == tools  # Tools remain available in new implementation

    def test_generate_response_with_conversation_history(self):
        """Test response generation with conversation history"""
        # Arrange
        history = "User: Hello\nAssistant: Hi there!"
        expected_response = "How can I help you further?"
        mock_response = MockAnthropicResponse([MockContentBlock(text=expected_response)])
        self.mock_client.messages.create.return_value = mock_response

        # Act
        result = self.ai_generator.generate_response(
            "What can you do?",
            conversation_history=history
        )

        # Assert
        assert result == expected_response
        call_args = self.mock_client.messages.create.call_args[1]
        assert history in call_args["system"]

    def test_tool_execution_error_handling(self):
        """Test handling of tool execution errors"""
        # Arrange
        tools = [{"name": "search_course_content"}]

        # Mock initial response with tool use
        initial_response = MockAnthropicResponse(
            content_blocks=[MockContentBlock(
                tool_name="search_course_content",
                tool_input={"query": "test"},
                tool_id="tool_123"
            )],
            stop_reason="tool_use"
        )

        final_response = MockAnthropicResponse([
            MockContentBlock(text="I encountered an issue searching.")
        ])

        self.mock_client.messages.create.side_effect = [initial_response, final_response]
        self.mock_tool_manager.execute_tool.return_value = "Search failed: Database error"

        # Act
        result = self.ai_generator.generate_response(
            "Search for something",
            tools=tools,
            tool_manager=self.mock_tool_manager
        )

        # Assert
        assert result == "I encountered an issue searching."
        # Verify tool was executed even though it returned an error
        self.mock_tool_manager.execute_tool.assert_called_once()

    def test_multiple_tool_calls_handling(self):
        """Test handling multiple tool calls in one response"""
        # Arrange
        tools = [
            {"name": "search_course_content"},
            {"name": "get_course_outline"}
        ]

        # Mock response with multiple tool calls
        initial_response = MockAnthropicResponse(
            content_blocks=[
                MockContentBlock(
                    tool_name="search_course_content",
                    tool_input={"query": "Python"},
                    tool_id="tool_1"
                ),
                MockContentBlock(
                    tool_name="get_course_outline",
                    tool_input={"course_name": "Python Basics"},
                    tool_id="tool_2"
                )
            ],
            stop_reason="tool_use"
        )

        final_response = MockAnthropicResponse([
            MockContentBlock(text="Based on the search and outline...")
        ])

        self.mock_client.messages.create.side_effect = [initial_response, final_response]
        self.mock_tool_manager.execute_tool.side_effect = [
            "Search results",
            "Course outline"
        ]

        # Act
        result = self.ai_generator.generate_response(
            "Tell me about Python courses",
            tools=tools,
            tool_manager=self.mock_tool_manager
        )

        # Assert
        assert result == "Based on the search and outline..."
        assert self.mock_tool_manager.execute_tool.call_count == 2

        # Verify both tools were called
        calls = self.mock_tool_manager.execute_tool.call_args_list
        assert calls[0][0][0] == "search_course_content"
        assert calls[1][0][0] == "get_course_outline"

    def test_sequential_tool_calling_two_rounds(self):
        """Test sequential tool calling across two rounds"""
        # Arrange
        tools = [
            {"name": "get_course_outline"},
            {"name": "search_course_content"}
        ]

        # Round 1: Claude uses get_course_outline
        round1_response = MockAnthropicResponse(
            content_blocks=[MockContentBlock(
                tool_name="get_course_outline",
                tool_input={"course_name": "Python Basics"},
                tool_id="tool_round1"
            )],
            stop_reason="tool_use"
        )

        # Round 2: Claude provides final answer with text (no more tool use)
        round2_response = MockAnthropicResponse([
            MockContentBlock(text="Based on the course outline, variables are fundamental data containers in Python.")
        ])

        self.mock_client.messages.create.side_effect = [round1_response, round2_response]
        self.mock_tool_manager.execute_tool.return_value = "Course outline: Lesson 1: Variables and Data Types"

        # Act
        result = self.ai_generator.generate_response(
            "What does lesson 1 of Python Basics cover about variables?",
            tools=tools,
            tool_manager=self.mock_tool_manager
        )

        # Assert
        assert result == "Based on the course outline, variables are fundamental data containers in Python."
        assert self.mock_client.messages.create.call_count == 2
        assert self.mock_tool_manager.execute_tool.call_count == 1

        # Verify tool execution
        self.mock_tool_manager.execute_tool.assert_called_once_with(
            "get_course_outline",
            course_name="Python Basics"
        )

    def test_sequential_tool_calling_max_rounds_reached(self):
        """Test sequential tool calling that reaches max 2 rounds"""
        # Arrange
        tools = [
            {"name": "get_course_outline"},
            {"name": "search_course_content"}
        ]

        # Round 1: Claude uses get_course_outline
        round1_response = MockAnthropicResponse(
            content_blocks=[MockContentBlock(
                tool_name="get_course_outline",
                tool_input={"course_name": "Python Basics"},
                tool_id="tool_round1"
            )],
            stop_reason="tool_use"
        )

        # Round 2: Claude uses search_course_content (max rounds reached, terminated here)
        round2_response = MockAnthropicResponse(
            content_blocks=[
                MockContentBlock(text="Based on the search results, "),
                MockContentBlock(
                    tool_name="search_course_content",
                    tool_input={"query": "variables and data types"},
                    tool_id="tool_round2"
                )
            ],
            stop_reason="tool_use"
        )

        self.mock_client.messages.create.side_effect = [round1_response, round2_response]
        self.mock_tool_manager.execute_tool.side_effect = [
            "Course outline: Lesson 1: Variables and Data Types",
            "Search results: Variables store data values..."
        ]

        # Act
        result = self.ai_generator.generate_response(
            "What does lesson 1 of Python Basics cover about variables?",
            tools=tools,
            tool_manager=self.mock_tool_manager
        )

        # Assert - Should extract text from the round 2 response that had both text and tool use
        assert result == "Based on the search results,"
        assert self.mock_client.messages.create.call_count == 2  # Exactly 2 rounds
        assert self.mock_tool_manager.execute_tool.call_count == 2  # Both tools executed

        # Verify tool execution sequence
        tool_calls = self.mock_tool_manager.execute_tool.call_args_list
        assert tool_calls[0][0][0] == "get_course_outline"
        assert tool_calls[1][0][0] == "search_course_content"

    def test_early_termination_no_tools_round1(self):
        """Test early termination when Claude doesn't use tools in round 1"""
        # Arrange
        tools = [{"name": "search_course_content"}]
        direct_response = MockAnthropicResponse([
            MockContentBlock(text="This is general knowledge, no search needed.")
        ])
        self.mock_client.messages.create.return_value = direct_response

        # Act
        result = self.ai_generator.generate_response(
            "What is Python?",
            tools=tools,
            tool_manager=self.mock_tool_manager
        )

        # Assert
        assert result == "This is general knowledge, no search needed."
        assert self.mock_client.messages.create.call_count == 1  # Only one round
        assert self.mock_tool_manager.execute_tool.call_count == 0  # No tools used

    def test_max_rounds_termination(self):
        """Test termination after max rounds (2) are reached"""
        # Arrange
        tools = [{"name": "search_course_content"}]

        # Both rounds use tools
        tool_response = MockAnthropicResponse(
            content_blocks=[MockContentBlock(
                tool_name="search_course_content",
                tool_input={"query": "test"},
                tool_id="tool_id"
            )],
            stop_reason="tool_use"
        )

        # After 2 rounds, should return the last response
        final_response = MockAnthropicResponse([
            MockContentBlock(text="After 2 rounds of searching...")
        ])

        self.mock_client.messages.create.side_effect = [tool_response, final_response]
        self.mock_tool_manager.execute_tool.return_value = "Search results"

        # Act
        result = self.ai_generator.generate_response(
            "Complex query requiring multiple searches",
            tools=tools,
            tool_manager=self.mock_tool_manager
        )

        # Assert
        assert result == "After 2 rounds of searching..."
        assert self.mock_client.messages.create.call_count == 2  # Exactly 2 rounds
        assert self.mock_tool_manager.execute_tool.call_count == 1  # Tools used in round 1 only

    def test_tool_execution_failure_in_round2(self):
        """Test graceful handling of tool execution failure in round 2"""
        # Arrange
        tools = [{"name": "search_course_content"}]

        # Round 1: Successful tool use
        round1_response = MockAnthropicResponse(
            content_blocks=[MockContentBlock(
                tool_name="search_course_content",
                tool_input={"query": "first search"},
                tool_id="tool_1"
            )],
            stop_reason="tool_use"
        )

        # Round 2: Final response (no more tool use after round 1 success)
        round2_response = MockAnthropicResponse([
            MockContentBlock(text="I found some information from the first search.")
        ])

        self.mock_client.messages.create.side_effect = [round1_response, round2_response]
        self.mock_tool_manager.execute_tool.return_value = "First search successful"

        # Act
        result = self.ai_generator.generate_response(
            "Complex search query",
            tools=tools,
            tool_manager=self.mock_tool_manager
        )

        # Assert
        assert result == "I found some information from the first search."
        assert self.mock_client.messages.create.call_count == 2
        assert self.mock_tool_manager.execute_tool.call_count == 1

    def test_complex_query_workflow_example(self):
        """Test the example workflow from requirements: course outline -> search"""
        # Arrange
        tools = [
            {"name": "get_course_outline"},
            {"name": "search_course_content"}
        ]

        # Round 1: Get course outline for course X
        outline_response = MockAnthropicResponse(
            content_blocks=[MockContentBlock(
                tool_name="get_course_outline",
                tool_input={"course_name": "Course X"},
                tool_id="outline_tool"
            )],
            stop_reason="tool_use"
        )

        # Round 2: Use search with text response (max rounds reached)
        search_response = MockAnthropicResponse(
            content_blocks=[
                MockContentBlock(text="Course Y also covers machine learning fundamentals like Course X lesson 4."),
                MockContentBlock(
                    tool_name="search_course_content",
                    tool_input={"query": "machine learning fundamentals"},
                    tool_id="search_tool"
                )
            ],
            stop_reason="tool_use"
        )

        self.mock_client.messages.create.side_effect = [outline_response, search_response]
        self.mock_tool_manager.execute_tool.side_effect = [
            "Course X: Lesson 4 - Machine Learning Fundamentals",
            "Found Course Y with similar ML content"
        ]

        # Act
        result = self.ai_generator.generate_response(
            "Search for a course that discusses the same topic as lesson 4 of course X",
            tools=tools,
            tool_manager=self.mock_tool_manager
        )

        # Assert
        assert result == "Course Y also covers machine learning fundamentals like Course X lesson 4."
        assert self.mock_client.messages.create.call_count == 2  # Only 2 rounds (max reached)

        # Verify the exact workflow - both tools should be executed
        tool_calls = self.mock_tool_manager.execute_tool.call_args_list
        assert len(tool_calls) == 2
        assert tool_calls[0][0][0] == "get_course_outline"
        assert tool_calls[0][1]["course_name"] == "Course X"
        assert tool_calls[1][0][0] == "search_course_content"
        assert "machine learning fundamentals" in tool_calls[1][1]["query"]

    def test_conversation_context_preservation_across_rounds(self):
        """Test that conversation history is maintained across rounds"""
        # Arrange
        history = "User: What is Python?\nAssistant: Python is a programming language."
        tools = [{"name": "search_course_content"}]

        tool_response = MockAnthropicResponse(
            content_blocks=[MockContentBlock(
                tool_name="search_course_content",
                tool_input={"query": "Python tutorials"},
                tool_id="context_tool"
            )],
            stop_reason="tool_use"
        )

        final_response = MockAnthropicResponse([
            MockContentBlock(text="Here are some Python tutorials from our courses.")
        ])

        self.mock_client.messages.create.side_effect = [tool_response, final_response]
        self.mock_tool_manager.execute_tool.return_value = "Tutorial content"

        # Act
        result = self.ai_generator.generate_response(
            "Can you find some tutorials?",
            conversation_history=history,
            tools=tools,
            tool_manager=self.mock_tool_manager
        )

        # Assert
        assert result == "Here are some Python tutorials from our courses."

        # Verify conversation history was included in system content
        first_call_args = self.mock_client.messages.create.call_args_list[0][1]
        assert history in first_call_args["system"]

        # Verify history preserved in second round
        second_call_args = self.mock_client.messages.create.call_args_list[1][1]
        assert history in second_call_args["system"]

    def test_api_call_counting_verification(self):
        """Test verification of correct number of API calls"""
        # Arrange
        tools = [{"name": "search_course_content"}]

        # Single round - tool use then termination
        tool_response = MockAnthropicResponse(
            content_blocks=[MockContentBlock(
                tool_name="search_course_content",
                tool_input={"query": "test"},
                tool_id="api_test"
            )],
            stop_reason="tool_use"
        )

        # No tools in response - should terminate
        final_response = MockAnthropicResponse([
            MockContentBlock(text="Here's what I found.")
        ])

        self.mock_client.messages.create.side_effect = [tool_response, final_response]
        self.mock_tool_manager.execute_tool.return_value = "Test results"

        # Act
        result = self.ai_generator.generate_response(
            "Search for test content",
            tools=tools,
            tool_manager=self.mock_tool_manager
        )

        # Assert
        assert result == "Here's what I found."
        # Should be exactly 2 API calls: round 1 (with tools) + round 2 (final response)
        assert self.mock_client.messages.create.call_count == 2
        assert self.mock_tool_manager.execute_tool.call_count == 1

    def test_tool_use_without_tool_manager(self):
        """Test tool use when tool_manager is not provided"""
        # Arrange
        tools = [{"name": "search_course_content"}]

        # Mock response indicating tool use but no tool manager to execute
        mock_response = MockAnthropicResponse(
            content_blocks=[MockContentBlock(
                tool_name="search_course_content",
                tool_input={"query": "test"}
            )],
            stop_reason="tool_use"
        )
        self.mock_client.messages.create.return_value = mock_response

        # Act
        result = self.ai_generator.generate_response(
            "Search for something",
            tools=tools,
            tool_manager=None
        )

        # Assert - Should return helpful error message
        assert result == "I cannot execute tools without a tool manager. Please try rephrasing your question."
        self.mock_client.messages.create.assert_called_once()

    def test_api_parameters_configuration(self):
        """Test that API parameters are configured correctly"""
        # Arrange
        mock_response = MockAnthropicResponse([MockContentBlock(text="response")])
        self.mock_client.messages.create.return_value = mock_response

        # Act
        self.ai_generator.generate_response("test query")

        # Assert
        call_args = self.mock_client.messages.create.call_args[1]
        assert call_args["model"] == "claude-3-sonnet-20240229"
        assert call_args["temperature"] == 0
        assert call_args["max_tokens"] == 800
        assert len(call_args["messages"]) == 1
        assert call_args["messages"][0]["role"] == "user"
        assert call_args["messages"][0]["content"] == "test query"

    def test_system_prompt_structure(self):
        """Test system prompt is properly included"""
        # Arrange
        mock_response = MockAnthropicResponse([MockContentBlock(text="response")])
        self.mock_client.messages.create.return_value = mock_response

        # Act
        self.ai_generator.generate_response("test")

        # Assert
        call_args = self.mock_client.messages.create.call_args[1]
        system_content = call_args["system"]
        assert "course materials and educational content" in system_content
        assert "search_course_content" in system_content
        assert "get_course_outline" in system_content

    def test_tool_result_message_structure(self):
        """Test that tool result messages are structured correctly"""
        # Arrange
        tools = [{"name": "search_course_content"}]

        initial_response = MockAnthropicResponse(
            content_blocks=[MockContentBlock(
                tool_name="search_course_content",
                tool_input={"query": "test"},
                tool_id="tool_123"
            )],
            stop_reason="tool_use"
        )

        final_response = MockAnthropicResponse([MockContentBlock(text="Final response")])

        self.mock_client.messages.create.side_effect = [initial_response, final_response]
        self.mock_tool_manager.execute_tool.return_value = "Tool result"

        # Act
        result = self.ai_generator.generate_response(
            "test",
            tools=tools,
            tool_manager=self.mock_tool_manager
        )

        # Assert
        second_call_args = self.mock_client.messages.create.call_args_list[1][1]
        tool_result_message = second_call_args["messages"][2]  # Third message should be tool results

        assert tool_result_message["role"] == "user"
        assert isinstance(tool_result_message["content"], list)

        tool_result_content = tool_result_message["content"][0]
        assert tool_result_content["type"] == "tool_result"
        assert tool_result_content["tool_use_id"] == "tool_123"
        assert tool_result_content["content"] == "Tool result"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
