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
        """Test response generation with tool execution"""
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
        
        # Mock final response after tool execution
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
        
        # Verify second API call structure
        second_call_args = self.mock_client.messages.create.call_args_list[1][1]
        assert len(second_call_args["messages"]) == 3  # user, assistant, user with tool results
        assert "tools" not in second_call_args  # No tools in final call
    
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
        
        # Act & Assert - This should raise an AttributeError
        # because the code tries to access .text on a tool_use content block
        with pytest.raises(AttributeError):
            self.ai_generator.generate_response(
                "Search for something",
                tools=tools,
                tool_manager=None
            )
        
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