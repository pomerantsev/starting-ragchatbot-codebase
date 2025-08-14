from typing import List, Optional

import anthropic


class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""

    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to comprehensive search tools for course information.

Available Tools:
1. **search_course_content**: For searching specific course content and materials
2. **get_course_outline**: For retrieving complete course outlines with all lesson details

Tool Usage Guidelines:
- Use **search_course_content** for questions about specific course content or detailed educational materials
- Use **get_course_outline** for course overview requests, lesson lists, or structural information about courses
- **You can make up to 2 rounds of tool calls** to thoroughly answer complex questions
- **Progressive search strategy**: Start with broader searches, then narrow down based on initial results
- **Sequential reasoning**: Each tool call should build on previous results when multiple rounds are needed
- For outline queries, ensure you return the course title, course link, and complete lesson list with lesson numbers and titles
- Synthesize tool results into accurate, fact-based responses
- If tools yield no results, state this clearly without offering alternatives
- **When you have sufficient information to provide a complete answer, respond without additional tool calls**

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without using tools
- **Course content questions**: Use search_course_content tool first, then answer
- **Course outline/structure questions**: Use get_course_outline tool first, then answer
- **Complex queries requiring multiple searches**: Use tools sequentially to build comprehensive understanding
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, tool explanations, or question-type analysis
 - Do not mention "based on the search results" or "using the tool"

All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""

    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

        # Pre-build base API parameters
        self.base_params = {"model": self.model, "temperature": 0, "max_tokens": 800}

    def generate_response(
        self,
        query: str,
        conversation_history: Optional[str] = None,
        tools: Optional[List] = None,
        tool_manager=None,
        max_rounds: int = 2,
    ) -> str:
        """
        Generate AI response with support for sequential tool calling.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools
            max_rounds: Maximum number of tool calling rounds (default: 2)

        Returns:
            Generated response as string
        """

        # Initialize conversation state
        messages = [{"role": "user", "content": query}]
        system_content = self._build_system_content(conversation_history, max_rounds)

        # Execute up to max_rounds of tool calling
        response = None
        for round_num in range(1, max_rounds + 1):
            response = self._execute_single_round(
                messages, system_content, tools, round_num, max_rounds
            )

            # Handle tool execution if tools were used
            if response.stop_reason == "tool_use" and tool_manager:
                # If we haven't reached max rounds, prepare for next round
                if round_num < max_rounds:
                    messages = self._prepare_next_round(
                        messages, response, tool_manager
                    )
                    continue
                else:
                    # Max rounds reached, execute tools one final time then return
                    self._execute_tools_with_error_handling(response, tool_manager)
                    return self._extract_final_response(response)
            elif response.stop_reason == "tool_use" and not tool_manager:
                # No tool manager but tools requested, return error message
                return "I cannot execute tools without a tool manager. Please try rephrasing your question."
            else:
                # No tool use, terminate early
                return self._extract_final_response(response)

        # Fallback: return last response if max rounds reached
        return self._extract_final_response(response)

    def _build_system_content(
        self, conversation_history: Optional[str], max_rounds: int
    ) -> str:
        """Build system content with conversation history and round context."""
        base_content = self.SYSTEM_PROMPT
        if conversation_history:
            base_content = (
                f"{base_content}\n\nPrevious conversation:\n{conversation_history}"
            )
        return base_content

    def _execute_single_round(
        self,
        messages: List,
        system_content: str,
        tools: Optional[List],
        round_num: int,
        max_rounds: int,
    ):
        """Execute a single round of Claude API interaction with error handling."""
        try:
            # Build API parameters
            api_params = {
                **self.base_params,
                "messages": messages.copy(),
                "system": self._add_round_context(
                    system_content, round_num, max_rounds
                ),
            }

            # Add tools if available (keep tools available in each round)
            if tools:
                api_params["tools"] = tools
                api_params["tool_choice"] = {"type": "auto"}

            # Get response from Claude
            response = self.client.messages.create(**api_params)
            return response
        except Exception as e:
            # Create a mock response for API failures
            return self._create_error_response(f"API call failed: {str(e)}")

    def _create_error_response(self, error_message: str):
        """Create a mock response for error scenarios."""

        class MockResponse:
            def __init__(self, error_message):
                self.stop_reason = "end_turn"
                self.content = [MockContentBlock(error_message)]

        class MockContentBlock:
            def __init__(self, text):
                self.type = "text"
                self.text = text

        return MockResponse(error_message)

    def _add_round_context(
        self, system_content: str, round_num: int, max_rounds: int
    ) -> str:
        """Add round-specific context to system content."""
        if max_rounds > 1:
            context_note = f"\n\nCURRENT CONTEXT: Round {round_num} of {max_rounds} maximum tool calling rounds."
            if round_num == max_rounds:
                context_note += " This is your final round - provide complete answer."
            return system_content + context_note
        return system_content

    def _prepare_next_round(self, messages: List, response, tool_manager) -> List:
        """
        Prepare message history for the next round.

        Args:
            messages: Current message history
            response: Claude's response containing tool calls
            tool_manager: Tool execution manager

        Returns:
            Updated message history for next round
        """
        # Copy messages to avoid mutation
        next_messages = messages.copy()

        # Add Claude's tool use response to conversation
        next_messages.append({"role": "assistant", "content": response.content})

        # Execute tools and add results
        tool_results = self._execute_tools_with_error_handling(response, tool_manager)
        if tool_results:
            next_messages.append({"role": "user", "content": tool_results})

        return next_messages

    def _execute_tools_with_error_handling(self, response, tool_manager) -> List:
        """Execute tools with comprehensive error handling."""
        tool_results = []

        for content_block in response.content:
            if content_block.type == "tool_use":
                try:
                    tool_result = tool_manager.execute_tool(
                        content_block.name, **content_block.input
                    )
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": content_block.id,
                            "content": tool_result,
                        }
                    )
                except Exception as e:
                    # Add error result to prevent API failure
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": content_block.id,
                            "content": f"Tool execution failed: {str(e)}",
                        }
                    )

        return tool_results

    def _extract_final_response(self, response) -> str:
        """Extract text content from Claude's response."""
        if hasattr(response, "content") and response.content:
            # Handle multi-block responses (text + tool calls)
            text_blocks = []
            for block in response.content:
                if hasattr(block, "text") and block.text and block.text.strip():
                    text_blocks.append(block.text.strip())

            if text_blocks:
                return " ".join(text_blocks)

        return "I wasn't able to generate a proper response. Please try rephrasing your question."
