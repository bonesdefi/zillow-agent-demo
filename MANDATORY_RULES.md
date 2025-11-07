# MANDATORY PROJECT RULES

## CRITICAL REQUIREMENTS (MUST FOLLOW EXACTLY)

### 1. Technology Stack (MANDATORY - NO SUBSTITUTIONS)
- ✅ **Agent Framework**: **LangChain + LangGraph** (NOT just LangGraph alone)
- ✅ **MCP Implementation**: FastMCP (https://github.com/jlowin/fastmcp)
- ✅ **LLM Provider**: Anthropic Claude (Claude 3.5 Sonnet) as primary
- ✅ **Language**: Python 3.11+
- ✅ **UI Framework**: Streamlit
- ✅ **Testing**: pytest with 80%+ coverage target
- ✅ **Type Checking**: mypy with strict mode
- ✅ **Linting**: ruff

### 2. Code Quality Requirements
- ✅ Every feature MUST have working tests
- ✅ Every component MUST have comprehensive documentation
- ✅ Code MUST be production-ready (error handling, logging, type hints)
- ✅ All functions MUST have type hints
- ✅ All functions MUST have docstrings (Google style)
- ✅ NO hardcoded credentials or API keys

### 3. Testing Requirements
- ✅ 80%+ test coverage target
- ✅ Unit tests for all functions
- ✅ Integration tests for workflows
- ✅ Mock external API calls in tests
- ✅ Test error cases explicitly
- ✅ All tests MUST pass before committing

### 4. Documentation Requirements
- ✅ README MUST include architecture diagrams (Mermaid)
- ✅ Every MCP tool MUST be documented
- ✅ Every agent MUST be documented
- ✅ LangGraph workflow MUST be documented with diagram
- ✅ API documentation MUST be complete
- ✅ Deployment guide MUST be complete

### 5. Project Structure (MUST MATCH EXACTLY)
```
real-estate-ai-assistant/
├── .github/workflows/tests.yml
├── docs/
│   ├── architecture.md
│   ├── mcp-servers.md
│   ├── agents.md
│   ├── deployment.md
│   └── api-documentation.md
├── src/
│   ├── mcp_servers/
│   │   ├── real_estate_server.py
│   │   ├── market_analysis_server.py
│   │   └── user_context_server.py
│   ├── agents/
│   │   ├── base_agent.py
│   │   ├── search_agent.py
│   │   ├── analysis_agent.py
│   │   ├── advisor_agent.py
│   │   └── coordinator.py
│   ├── graph/
│   │   ├── state.py
│   │   └── workflow.py
│   ├── tools/
│   │   └── property_tools.py
│   ├── ui/
│   │   └── streamlit_app.py
│   └── utils/
│       ├── logging.py
│       └── config.py
└── tests/
    ├── test_mcp_servers/
    ├── test_agents/
    ├── test_graph/
    └── conftest.py
```

### 6. Agent System Requirements (LANGCHAIN + LANGGRAPH)
- ✅ **BaseAgent** MUST use LangChain for LLM integration
- ✅ **All agents** MUST extend BaseAgent
- ✅ **LangGraph** MUST be used for workflow orchestration
- ✅ **State management** MUST use LangGraph TypedDict pattern
- ✅ **Nodes** MUST be LangGraph nodes
- ✅ **Edges** MUST be LangGraph edges (conditional and regular)

### 7. MCP Server Requirements
- ✅ MUST use FastMCP framework
- ✅ MUST have type hints for all parameters
- ✅ MUST use Pydantic models for validation
- ✅ MUST have comprehensive error handling
- ✅ MUST have detailed docstrings with examples
- ✅ MUST log all operations
- ✅ MUST implement retry logic (exponential backoff)
- ✅ MUST cache responses (with TTL)

### 8. LangGraph Workflow Requirements
- ✅ MUST use `StateGraph` from LangGraph
- ✅ MUST define `AgentState` as TypedDict
- ✅ MUST have these nodes:
  - `understand_intent`
  - `search_properties`
  - `analyze_properties`
  - `generate_recommendations`
  - `handle_clarification`
- ✅ MUST have conditional edges for routing
- ✅ MUST use `add_messages` for message handling

### 9. Git Requirements
- ✅ Meaningful commit messages (conventional commits)
- ✅ Frequent, small commits
- ✅ NO sensitive data in commits
- ✅ .env MUST be in .gitignore

### 10. Docker Requirements
- ✅ MUST be deployable via Docker
- ✅ docker-compose.yml MUST include all MCP servers
- ✅ Healthchecks MUST be configured
- ✅ Tests MUST run during Docker build

## IMPLEMENTATION CHECKLIST

### Phase 2: MCP Servers
- [x] Real Estate Data Server (4 tools) ✅
- [ ] Market Analysis Server (5 tools)
- [ ] User Context Server (6 tools)
- [ ] All tests with 80%+ coverage
- [ ] Integration tests

### Phase 3: Agent System (LANGCHAIN + LANGGRAPH)
- [ ] BaseAgent with LangChain LLM integration
- [ ] SearchAgent (extends BaseAgent)
- [ ] AnalysisAgent (extends BaseAgent)
- [ ] AdvisorAgent (extends BaseAgent)
- [ ] All agents use LangChain for LLM calls
- [ ] All agents tested

### Phase 4: LangGraph Orchestration
- [ ] AgentState TypedDict defined
- [ ] StateGraph created
- [ ] All nodes implemented
- [ ] Conditional edges implemented
- [ ] Workflow tested end-to-end
- [ ] Mermaid diagram in docs

### Phase 5: Streamlit UI (MANDATORY - MUST INCLUDE ALL FEATURES)
- [ ] **Chat Interface** - Main conversation area with chat input
- [ ] **Agent Activity Sidebar** - Real-time display of agent coordination (THE MAGIC PART)
  - [ ] Shows which agent is currently active
  - [ ] Shows MCP server calls being made
  - [ ] Shows timestamps for each action
  - [ ] Shows data being retrieved
  - [ ] Expandable logs for each agent action
- [ ] **Property Cards Display** - Visual property listings
  - [ ] Property images from API
  - [ ] Address, price, bedrooms, bathrooms, square feet
  - [ ] "View Details" button for each property
  - [ ] Expandable "AI Analysis" section under each property
- [ ] **Analysis Results Display** - Show analysis data
  - [ ] Neighborhood stats
  - [ ] School ratings
  - [ ] Market trends
  - [ ] Affordability calculations
- [ ] **Search Criteria Display** - Show extracted search parameters
  - [ ] Location
  - [ ] Budget range
  - [ ] Bedrooms/bathrooms
  - [ ] Property type
- [ ] **Conversation History** - Full chat history
- [ ] **Real-Time Updates** - Live agent activity monitoring
- [ ] **Loading Indicators** - Show when agents are working
- [ ] **Error Messages** - Styled error handling
- [ ] **Responsive Design** - Works on different screen sizes

### Phase 6: DevOps
- [ ] Dockerfile
- [ ] docker-compose.yml
- [ ] GitHub Actions CI/CD
- [ ] All healthchecks

### Phase 7: Documentation
- [ ] Architecture docs with diagrams
- [ ] API documentation
- [ ] Deployment guide
- [ ] Feature verification checklist

## VERIFICATION BEFORE EACH COMMIT

1. ✅ Run tests: `pytest tests/ -v`
2. ✅ Check coverage: `pytest --cov=src --cov-report=term`
3. ✅ Type check: `mypy src/ --strict`
4. ✅ Lint: `ruff check src/ tests/`
5. ✅ Verify no hardcoded credentials
6. ✅ Verify all functions have docstrings
7. ✅ Verify all functions have type hints

## CRITICAL: STREAMLIT UI REQUIREMENTS (PHASE 5)

### UI Layout (MUST MATCH EXACTLY):

```
┌─────────────────────────────────────────────────────────┐
│  🏠 Real Estate AI Assistant                            │
│  Multi-Agent Demo • LangGraph + MCP                     │
├──────────────────────────────────────┬──────────────────┤
│                                      │                  │
│  💬 Chat Interface                   │  🤖 Agent        │
│  ┌────────────────────────────────┐ │  Activity        │
│  │ User: Find 3-bed in Austin    │ │                  │
│  └────────────────────────────────┘ │  ⚡ Search Agent │
│  ┌────────────────────────────────┐ │  ├─ Parsing...   │
│  │ 🤖 Assistant: Found 12 props  │ │  └─ MCP: search  │
│  └────────────────────────────────┘ │                  │
│                                      │  📊 Analysis     │
│  🏘️ Property Results                │  Agent           │
│  ┌────────┬──────────────┬───────┐ │  ├─ Schools...   │
│  │ [IMG]  │ 123 Main St  │[View] │ │  └─ MCP: ratings │
│  │        │ $575,000     │       │ │                  │
│  │        │ 3 bed • 2 ba │       │ │  💡 Advisor      │
│  │        └──────────────┘       │ │  └─ Synthesizing │
│  └───────────────────────────────┘ │                  │
│                                      │  📈 Current      │
│                                      │  Search          │
│                                      │  Location: Austin│
│                                      │  Budget: $600k   │
└──────────────────────────────────────┴──────────────────┘
```

### Required UI Features:

1. **Main Chat Interface** (Left Column - 2/3 width)
   - Chat input: `st.chat_input("What are you looking for?")`
   - Message history with role-based styling
   - User messages on right, assistant on left
   - Real-time message updates

2. **Agent Activity Sidebar** (Right Column - 1/3 width)
   - Header: "🤖 Agent Activity"
   - Real-time agent coordination display
   - Shows timestamps: `[12:34:01] Search Agent started`
   - Shows MCP calls: `→ MCP: search_properties(...)`
   - Shows results: `✓ Found 12 properties`
   - Expandable sections for each agent action
   - JSON view of agent data/logs

3. **Property Cards** (Main Area)
   - Image from API (left column)
   - Property details (middle column): address, price, specs
   - Action button (right column): "View Details"
   - Expandable "📊 AI Analysis" section with:
     - Neighborhood stats
     - School ratings
     - Market trends
     - Pros/cons
   - Divider between properties

4. **Search Criteria Display** (Sidebar)
   - Current search parameters
   - Location, price range, bedrooms, etc.
   - Updates in real-time as agents extract criteria

5. **Loading States**
   - Spinner: `st.spinner("🤖 Agents are working...")`
   - Shows during workflow execution
   - Updates as each agent completes

6. **Error Handling**
   - Styled error messages
   - Clear user feedback
   - Graceful degradation

### UI Code Requirements:

```python
# MUST include these components:

# 1. Page config
st.set_page_config(
    page_title="Real Estate AI Assistant",
    page_icon="🏠",
    layout="wide"
)

# 2. Sidebar with agent activity
with st.sidebar:
    st.header("🤖 Agent Activity")
    # Real-time agent logs
    # MCP server call tracking
    # Current search criteria

# 3. Main chat interface
st.chat_input("What are you looking for?")
# Message history
# Property cards
# Analysis results

# 4. Agent activity logging
st.session_state.agent_logs.append({
    "agent": "Search Agent",
    "timestamp": datetime.now(),
    "action": "Calling MCP server",
    "data": {...}
})
```

### UI Transparency Features (CRITICAL):

The UI MUST show:
- ✅ Which agent is currently active
- ✅ Which MCP server is being called
- ✅ What parameters are being passed
- ✅ What data is being retrieved
- ✅ The reasoning process
- ✅ Timestamps for all actions

**This transparency is what makes the demo impressive in interviews!**

## CRITICAL: LANGCHAIN + LANGGRAPH USAGE

**MUST USE BOTH:**
- **LangChain**: For LLM integration, prompt management, tool calling
- **LangGraph**: For workflow orchestration, state management, agent coordination

**Example Pattern:**
```python
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage

# In BaseAgent:
self.llm = ChatAnthropic(model="claude-3-5-sonnet-20241022")

# In LangGraph workflow:
workflow = StateGraph(AgentState)
workflow.add_node("search", search_agent_node)
```

## NO SHORTCUTS ALLOWED

- ❌ NO skipping tests
- ❌ NO missing docstrings
- ❌ NO missing type hints
- ❌ NO hardcoded values
- ❌ NO mock data in production code
- ❌ NO incomplete error handling
- ❌ NO missing documentation
- ❌ NO simplified UI - MUST show agent activity sidebar
- ❌ NO black box - MUST show MCP server calls
- ❌ NO static displays - MUST show real-time agent coordination

## SUCCESS CRITERIA

Project is ONLY complete when:
1. ✅ All tests pass with 80%+ coverage
2. ✅ All three MCP servers functional
3. ✅ All agents implemented with LangChain
4. ✅ LangGraph workflow working end-to-end
5. ✅ **UI functional and professional WITH agent activity sidebar**
6. ✅ **Agent coordination visible in real-time**
7. ✅ **MCP server calls displayed in sidebar**
8. ✅ **Property cards with expandable analysis**
9. ✅ Docker deployment works
10. ✅ All documentation complete
11. ✅ GitHub Actions CI passes
12. ✅ Code quality checks pass
13. ✅ Can be demoed live with full UI transparency

---

**REMEMBER**: This is a PORTFOLIO PROJECT for senior engineers. Every detail matters.
