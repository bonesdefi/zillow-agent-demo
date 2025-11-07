# Agent System Documentation

## Overview

The agent system consists of three specialized AI agents coordinated by a LangGraph workflow. Each agent has a specific role in the real estate assistance process.

## Base Agent

All agents inherit from `BaseAgent` which provides:

- LLM initialization (Anthropic Claude 3.5 Sonnet)
- MCP client connections
- Logging setup
- Error handling framework
- Common utilities

### Base Agent Methods

- `process(state)`: Abstract method for processing state
- `_call_mcp_tool(server, tool, params)`: Helper for calling MCP tools
- `_extract_structured_data(prompt, schema)`: Extract structured data from LLM

## Search Agent

**Purpose**: Parse user search intent and retrieve matching properties.

### Responsibilities

1. Extract search criteria from natural language
2. Handle ambiguous requests
3. Call Real Estate MCP server
4. Format results for presentation

### Example Workflow

```
User: "Find me a 3-bedroom house in Austin under $600k"
  ↓
Search Agent extracts:
  - location: "Austin, TX"
  - bedrooms: 3
  - max_price: 600000
  - property_type: "house"
  ↓
Calls Real Estate MCP: search_properties()
  ↓
Returns formatted property list
```

### Handling Ambiguity

When search criteria are unclear, the agent:
1. Identifies missing information
2. Generates clarification questions
3. Sets `needs_clarification` flag in state
4. Returns to workflow for user interaction

## Analysis Agent

**Purpose**: Analyze properties using market data and neighborhood information.

### Responsibilities

1. Get neighborhood statistics
2. Check school ratings
3. Analyze market trends
4. Calculate affordability
5. Identify pros/cons

### Analysis Output

For each property, the agent provides:

- **Neighborhood Score**: Overall neighborhood quality
- **School Ratings**: Nearby school quality
- **Market Trends**: Price trends and velocity
- **Affordability**: Based on user income (if provided)
- **Pros**: Positive aspects
- **Cons**: Potential concerns
- **Risk Factors**: Market or location risks

## Advisor Agent

**Purpose**: Synthesize information and provide recommendations.

### Responsibilities

1. Combine search and analysis results
2. Rank properties by suitability
3. Generate natural language recommendations
4. Explain reasoning
5. Suggest next steps

### Personality

The advisor agent is:
- **Helpful**: Provides actionable advice
- **Knowledgeable**: Demonstrates expertise
- **Honest**: Acknowledges limitations
- **Conversational**: Engages naturally

### Recommendation Format

1. **Summary**: Brief overview of findings
2. **Top Recommendations**: Ranked property suggestions
3. **Reasoning**: Why these properties were selected
4. **Next Steps**: Suggested actions for the user

## Agent Coordination

Agents are coordinated by the LangGraph workflow:

1. **Sequential Processing**: Agents run in sequence
2. **State Passing**: State is passed between agents
3. **Error Handling**: Errors are caught and handled gracefully
4. **Logging**: All agent actions are logged

## Testing

Each agent has comprehensive tests:

- Unit tests for individual methods
- Integration tests with MCP servers
- End-to-end workflow tests
- Error handling tests

