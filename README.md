# NeuroStack AI

**Production-Grade Multi-Agent LLM Orchestration System** — A comprehensive containerized platform featuring real-time agent coordination, dynamic routing, server-sent events streaming, intelligent tool calling with retry mechanisms, custom evaluation frameworks, and self-improving prompt optimization loops.
---

## Executive Summary

NeuroStack AI is a sophisticated multi-agent orchestration system designed for production environments. It enables seamless collaboration between specialized AI agents through dynamic routing, shared context management, and real-time streaming capabilities. The system features a robust evaluation framework with 15 comprehensive test cases, human-in-the-loop prompt optimization, and enterprise-grade monitoring and observability.

---

# Screenshots

## Pipeline Dashboard

![Pipeline Dashboard](screenshots/Screenshot%202026-05-13%20162758.png)

---

## Agent Pipeline & SSE Streaming

![Agent Pipeline](screenshots/Screenshot%202026-05-13%20162909.png)

---

## Job History & Query Runs

![Job History](screenshots/Screenshot%202026-05-13%20162941.png)

---

## Evaluation Dashboard

![Evaluation Dashboard](screenshots/Screenshot%202026-05-13%20163030.png)

---
### Key Achievements

- **Real-time Multi-Agent Coordination**: Dynamic agent orchestration with intelligent routing based on query complexity
- **Production-Ready Infrastructure**: Fully containerized with Docker Compose, PostgreSQL persistence, and health monitoring
- **Comprehensive Evaluation System**: 15-case evaluation framework with multi-dimensional scoring and automated re-testing
- **Self-Improving Architecture**: Human-in-the-loop prompt optimization with approval workflows
- **Enterprise Monitoring**: Real-time dashboards, execution traces, and detailed job analytics

---

## Screenshots

Live dashboard captures from the NeuroStack AI UI (pipeline run, execution detail, evaluation metrics, and trace history).

### Pipeline dashboard

Live run with multi-stage agent pipeline, SSE token stream, tool calls, and context budgets.

![Pipeline dashboard](docs/screenshots/01-pipeline-execution.png)

### Agent pipeline and execution log

Orchestrated stages (decomposition, RAG, critique, synthesis) with tool usage and eval summary.

![Agent pipeline and execution log](docs/screenshots/02-execution-trace.png)

### Evaluation dashboard

Eval run summary with weighted metrics and per–test-case scores.

![Evaluation dashboard](docs/screenshots/03-evaluation-results.png)

### Execution traces

Recent traces with event and tool counts and quick navigation to full traces.

![Execution traces](docs/screenshots/04-execution-traces.png)

---

## System Architecture

### High-Level Design

```
┌─────────────────────────────────────────┐
│  CLIENT (Browser)                        │
│  SSE ◄────────────────────────► Frontend │
│  REST ◄────────────────────────► API     │
└─────────────────────────────────────────┘
                    │
                    ▼
              ┌───────────────────────────┐
              │  API Server (FastAPI)      │
              │  + Background Worker       │
              └─────────────┬─────────────┘
                            │
              ┌─────────────▼─────────────┐
              │  PostgreSQL                │
              │  jobs, events, eval,       │
              │  tool logs, prompts         │
              └─────────────┬─────────────┘
                            │
              ┌─────────────▼─────────────┐
              │  Orchestrator → agents     │
              │  (shared context only)     │
              └───────────────────────────┘
```

### Agent Architecture

The system employs a dynamic multi-agent architecture where the **Orchestrator Agent** intelligently routes queries to specialized agents based on complexity and requirements:

- **Orchestrator Agent**: Central coordinator managing query routing, budget allocation, and agent orchestration
- **Decomposition Agent**: Breaks down complex queries into manageable sub-tasks
- **RAG Agent**: Handles information retrieval and knowledge base queries
- **Critique Agent**: Evaluates and refines agent outputs for quality assurance
- **Synthesis Agent**: Combines multiple agent outputs into coherent responses
- **Compression Agent**: Dynamically activated when context approaches budget limits

### Dynamic Routing Logic

The system implements intelligent query routing that adapts based on:
- Query complexity and length
- Available budget constraints
- Historical performance patterns
- Real-time system load

### Request Execution Flow

The complete request path through the system, from client UI to persistent storage:

```
Client UI
   ↓
FastAPI API Layer
   ↓
Orchestrator Agent
   ↓
 ┌───────────────┬───────────────┬───────────────┐
 │               │               │               │
Decomposition   RAG Agent      Critique Agent
 │               │               │
 └───────────────┼───────────────┘
                 ↓
             Tool Layer
   (Web / SQL / Reflection / Sandbox)
                 ↓
         Synthesis Agent
                 ↓
       SSE Streaming Layer
                 ↓
      PostgreSQL + Eval Store
```

**Execution Flow Details:**
1. **Client Request**: User submits query via browser UI
2. **API Processing**: FastAPI receives and validates request
3. **Orchestration**: Orchestrator Agent assesses query complexity and budget
4. **Parallel Processing**: Decomposition, RAG, and Critique agents execute concurrently based on routing logic
5. **Tool Integration**: Required tools (Web Search, SQL Lookup, Code Reflection, Sandbox Execution) are invoked with retry mechanisms
6. **Synthesis**: Synthesis Agent combines outputs into final response
7. **Real-time Streaming**: Response streamed to client via Server-Sent Events (SSE)
8. **Persistence**: Complete execution history, logs, and evaluation data stored in PostgreSQL

---

## Technical Implementation

### Backend Stack

**Core Technologies:**
- **Python 3.11**: Modern Python with enhanced performance features
- **FastAPI**: High-performance async web framework with automatic OpenAPI documentation
- **Uvicorn**: ASGI server for production deployment
- **SQLAlchemy 2.0**: Modern async ORM with type safety
- **PostgreSQL**: Enterprise-grade relational database with async support via `asyncpg`
- **OpenAI API**: Primary LLM integration with flexible model configuration

**Advanced Features:**
- **Async/Await Architecture**: Full asynchronous processing for optimal performance
- **Connection Pooling**: Efficient database connection management
- **Background Task Processing**: Dedicated worker process for job execution
- **Server-Sent Events (SSE)**: Real-time streaming to frontend clients
- **Context Budget Management**: Intelligent token usage optimization

### Frontend Stack

**Core Technologies:**
- **React 18**: Modern React with concurrent features
- **Vite**: Lightning-fast build tool and development server
- **TypeScript**: Type-safe JavaScript development
- **TanStack Query**: Powerful server-state management with caching and synchronization
- **Wouter**: Lightweight routing solution
- **TailwindCSS**: Utility-first CSS framework
- **Radix UI**: Accessible component primitives
- **Recharts**: Data visualization library

**UI/UX Features:**
- **Real-time Dashboards**: Live monitoring of agent executions
- **Interactive Traces**: Detailed execution flow visualization
- **Responsive Design**: Mobile-optimized interface
- **Dark/Light Mode**: Theme switching capability
- **Accessibility**: WCAG compliant interface components

### Infrastructure & DevOps

**Container Architecture:**
- **Multi-stage Docker Builds**: Optimized container images for production
- **Docker Compose**: Complete development and deployment orchestration
- **Health Checks**: Comprehensive container health monitoring
- **Volume Management**: Persistent data storage for PostgreSQL
- **Network Isolation**: Secure inter-service communication

**Services:**
- **API Server**: FastAPI application on port 8000
- **Background Worker**: Dedicated job processing service
- **PostgreSQL Database**: Persistent data storage on port 5432
- **Frontend Dashboard**: React application on port 3000
- **Adminer**: Database management interface on port 8082

---

## Core Features & Capabilities

### 1. Multi-Agent Orchestration

**Dynamic Agent Selection:**
- Intelligent routing based on query analysis
- Adaptive agent composition for complex tasks
- Budget-aware agent activation
- Real-time performance monitoring

**Shared Context Management:**
- Unified context across all agents
- Efficient context compression when needed
- Token usage optimization
- Context persistence and retrieval

### 2. Real-time Streaming & Communication

**Server-Sent Events (SSE):**
- Live token streaming during generation
- Real-time agent status updates
- Tool call execution monitoring
- Budget consumption tracking

**Event Types:**
- `job_created`: New job initialization
- `token`: Individual token generation
- `routing`: Agent routing decisions
- `tool_call`: Tool execution events
- `budget`: Budget status updates
- `agent_*`: Agent-specific events
- `done`: Job completion
- `error`: Error handling and recovery

### 3. Intelligent Tool System

**Available Tools:**
- **web_search**: Stubbed web search integration (production-ready with external API)
- **sql_lookup**: Natural language to SQL conversion with in-memory data
- **code_executor**: Safe code execution environment
- **self_reflection**: Agent self-evaluation and improvement

**Tool Features:**
- Automatic retry mechanisms with exponential backoff
- Error handling and recovery
- Tool usage logging and analytics
- Performance optimization

### 4. Comprehensive Evaluation Framework

**15-Case Test Suite:**
- **5 Straightforward Cases**: Basic functionality validation
- **5 Ambiguous Cases**: Complex reasoning and interpretation
- **5 Adversarial Cases**: Edge cases and error handling

**Multi-Dimensional Scoring:**
- **Correctness**: Answer accuracy and relevance
- **Citations**: Source attribution and verification
- **Contradiction Resolution**: Logical consistency checking
- **Tool Efficiency**: Resource usage optimization
- **Budget Compliance**: Cost-effectiveness evaluation
- **Critique Agreement**: Self-assessment accuracy

### 5. Self-Improving Prompt System

**Human-in-the-Loop Optimization:**
- Automated prompt generation based on performance
- Human approval/rejection workflows
- A/B testing capability for prompt variants
- Continuous improvement cycles

**Prompt Management:**
- Version control for prompt iterations
- Performance tracking per prompt version
- Automated rollback on performance degradation
- Prompt template management

---

## API Documentation

### Core API Endpoints (5-Endpoint Contract)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/query` | Submit query → **SSE** stream with real-time updates |
| `GET` | `/api/trace/{job_id}` | Retrieve complete execution trace with full context |
| `GET` | `/api/eval/summary` | Latest evaluation run summary with detailed scoring |
| `POST` | `/api/prompts/{id}/review` | Approve/reject prompt optimization proposals |
| `POST` | `/api/eval/re-eval` | Re-run evaluation on failed cases with updated prompts |

### Dashboard Support Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/jobs` | Recent jobs list with status and metadata |
| `GET` | `/api/traces` | Execution trace summaries with event counts |

### Development Endpoints (Non-Strict Mode)

Additional endpoints available when `STRICT_API_FIVE_ENDPOINTS=false`:
- `/api/eval/rerun`: Full evaluation suite execution
- `/api/jobs/{id}`: Detailed job information
- `/api/agent-turns`: Agent execution analytics
- `/api/tool-calls`: Tool usage statistics
- `/api/budgets`: Budget consumption reports
- `/api/prompts`: Prompt management interface

### Health Monitoring

- `GET /health`: Infrastructure health check (Docker/Kubernetes)
- `GET /api/health`: Application health status (development mode)

### Error Handling

All errors return structured JSON responses:
```json
{
  "detail": {
    "error_code": "string",
    "message": "string",
    "job_id": "optional_uuid"
  }
}
```

---

## Database Schema

### Core Tables

**Jobs Table:**
- Primary job tracking with status management
- Query storage and result persistence
- Timestamp tracking for performance analytics
- Budget allocation and consumption tracking

**Events Table:**
- Detailed event logging for audit trails
- Agent interaction tracking
- Tool call execution records
- Performance metrics collection

**Tool Call Logs:**
- Comprehensive tool usage analytics
- Execution time tracking
- Success/failure rates
- Resource consumption monitoring

**Evaluation Results:**
- Test case execution history
- Multi-dimensional scoring storage
- Performance trend analysis
- Comparison metrics across prompt versions

**Prompt Versions:**
- Version control for prompt iterations
- Performance metadata per version
- Approval workflow status
- A/B testing results

---

## Development & Deployment

### Quick Start

```bash
# Clone the repository
git clone https://github.com/anushree1206/neurostack-ai.git
cd neurostack-ai

# Environment configuration
cp .env.example .env  # Create if not exists
# Edit .env with your API keys and configuration

# Start the complete system
docker compose up --build
```

### Service URLs

| Service | URL | Description |
|---------|-----|-------------|
| API Server | http://localhost:8000 | FastAPI backend with OpenAPI docs |
| Frontend Dashboard | http://localhost:3000 | React-based monitoring interface |
| Database | localhost:5432 | PostgreSQL database |
| Adminer (DB UI) | http://localhost:8082 | Database management interface |

### Environment Configuration

**Required Variables:**
- `OPENAI_API_KEY`: OpenAI API key for LLM operations
- `AI_INTEGRATIONS_OPENAI_API_KEY`: Alternative OpenAI key format

**Optional Variables:**
- `OPENAI_BASE_URL`: Custom OpenAI endpoint
- `AI_INTEGRATIONS_OPENAI_BASE_URL`: Alternative base URL format
- `OPENAI_MODEL`: Default model selection (e.g., gpt-4, gpt-3.5-turbo)
- `ORCHESTRATOR_MODEL`: Specific model for orchestrator agent
- `AGENT_MODEL`: Default model for worker agents
- `STRICT_API_FIVE_ENDPOINTS`: Enable/disable strict API mode (default: true)

**Database Configuration:**
- `DATABASE_URL`: PostgreSQL connection string
- `PGUSER`: Database username (default: agentuser)
- `PGPASSWORD`: Database password (default: agentpass)
- `PGDATABASE`: Database name (default: agentdb)

### Development Workflow

**Local Development:**
```bash
# Install dependencies
pnpm install

# Start development servers
pnpm run dev:frontend  # Frontend development server
pnpm run dev:backend   # Backend development server

# Type checking
pnpm run typecheck     # Full project type checking
pnpm run build         # Production build
```

**Testing:**
```bash
# Run evaluation suite
curl -X POST http://localhost:8000/api/eval/rerun

# Test query submission
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the capital of France?"}'
```

---

## Performance & Scalability

### Optimization Features

**Context Management:**
- Intelligent token budget allocation
- Dynamic context compression
- Efficient context window utilization
- Memory usage optimization

**Async Processing:**
- Non-blocking I/O operations
- Concurrent job processing
- Efficient resource utilization
- Scalable architecture design

**Caching Strategy:**
- Query result caching
- Tool response caching
- Model response caching
- Database query optimization

### Monitoring & Observability

**Real-time Metrics:**
- Job execution times
- Agent performance tracking
- Tool usage statistics
- Budget consumption monitoring

**Historical Analytics:**
- Performance trend analysis
- Error rate tracking
- Resource usage patterns
- Cost optimization insights

---

## Security & Best Practices

### Security Measures

**API Security:**
- CORS configuration for cross-origin requests
- Input validation and sanitization
- SQL injection prevention via ORM
- Rate limiting capabilities

**Data Protection:**
- Environment variable management
- Secure API key handling
- Database connection encryption
- Audit trail implementation

### Code Quality

**Type Safety:**
- Full TypeScript implementation
- Python type hints throughout
- Strict type checking enabled
- Interface contracts enforced

**Testing Strategy:**
- Comprehensive evaluation framework
- Multi-dimensional scoring system
- Edge case coverage
- Performance benchmarking

---

## Future Enhancements & Roadmap

### Planned Features

**Production Integrations:**
- Real web search API integration
- Production RAG with vector databases
- Advanced tool ecosystem expansion
- Multi-modal AI capabilities

**Advanced Features:**
- Agent learning and adaptation
- Advanced prompt engineering techniques
- Multi-tenant architecture support
- Advanced analytics and reporting

**Infrastructure Improvements:**
- Kubernetes deployment manifests
- Advanced monitoring with Prometheus/Grafana
- Distributed caching with Redis
- Load balancing and auto-scaling

### Technical Debt & Improvements

**Current Limitations:**
- Stub web search implementation (production-ready with external API)
- In-memory SQL lookup data (production integration needed)
- Evaluation system resource intensity
- Limited agent learning capabilities

**Improvement Areas:**
- Enhanced error handling and recovery
- Advanced caching strategies
- Performance optimization for large-scale deployments
- Extended tool ecosystem

---

## Contributing & Development

### Project Structure

```
NeuroStack AI/
├── backend/                 # FastAPI backend application
│   ├── agents/             # Multi-agent implementations
│   ├── api/                # API endpoint definitions
│   ├── db/                 # Database models and migrations
│   ├── eval/               # Evaluation framework
│   ├── tools/              # Agent tool implementations
│   └── worker.py           # Background job processing
├── frontend/               # React dashboard application
│   ├── src/                # React components and logic
│   └── package.json        # Frontend dependencies
├── lib/                    # Shared libraries and utilities
├── scripts/                # Development and deployment scripts
├── docker-compose.yml      # Multi-service orchestration
└── README.md              # This documentation
```

### Development Guidelines

**Code Standards:**
- TypeScript for frontend development
- Python type hints for backend development
- Consistent code formatting with Prettier/Black
- Comprehensive documentation and comments

**Git Workflow:**
- Feature branch development
- Pull request code reviews
- Automated testing integration
- Semantic versioning for releases

---

## License

This project is licensed under the MIT License. Feel free to use, modify, and distribute according to your needs for portfolio, educational, or production purposes.

---

## Contact & Support

**Project Repository:** [https://github.com/anushree1206/neurostack-ai](https://github.com/anushree1206/neurostack-ai)

**Technical Documentation:** Comprehensive API documentation available at `/docs` endpoint when running the API server.

**Issues & Contributions:** Please use the GitHub issue tracker for bug reports and feature requests.
