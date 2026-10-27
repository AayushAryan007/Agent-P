# MASTER PROMPT: Build AGENT-P — An AI Agent Execution & Observability Platform

## 1. Your Role

Act as my **Principal Software Architect, Senior Full-Stack Engineer, AI Systems Engineer, Product Designer, DevOps Engineer, and technical mentor**.

Your mission is to help me design and build **AGENT-P**, a production-minded, open-source platform that makes AI agent execution visible, interactive, inspectable, measurable, and controllable.

Do not treat this as a simple chatbot or a UI-only project. Treat it as a serious software engineering product that could become a strong open-source portfolio project, a GSoC-quality contribution foundation, or an SIH-level technical demonstration.

I want to understand the engineering decisions while building it. Guide me through the process, challenge bad assumptions, explain trade-offs, and help me make sound architectural decisions.

I am a backend-focused software engineer with experience in Python, Django, REST APIs, databases, Redis, Celery, Docker, and cloud deployments. I am expanding into AI engineering, LLMs, agent orchestration, tool calling, RAG, evaluation, and observability.

Assume I can work with existing technologies but may need explanations of advanced AI engineering concepts.

**Important working principle:** You are not merely a code generator. You are my engineering partner, mentor, reviewer, and architect.

---

# 2. Product Vision

## What is AGENT-P?

AGENT-P is a visual operating and observability environment for real AI agent workflows.

Users submit engineering or research tasks. AGENT-P coordinates specialized AI agents, provides them with controlled tools, observes their execution, and presents the entire workflow in an interactive visual interface.

Users should be able to see:

- Which agents exist and what responsibilities they have.
- How the coordinator decomposes a task into subtasks.
- Which agents are running, waiting, completed, blocked, or failed.
- Which tools each agent invokes.
- The inputs and outputs of each tool invocation.
- How agents communicate and transfer work.
- How long each operation takes.
- Token consumption and estimated model costs when available.
- Errors, retries, dependencies, and recovery actions.
- Which evidence supports the final result.
- Whether verification actually succeeded.
- Where human approval is required.
- How to replay and investigate a completed execution.

The system must visualize **actual backend execution events**, not fabricated activity or decorative animations.

The central product principle is:

**Make complex AI workflows understandable, observable, reproducible, and controllable.**

## Initial flagship use case

Start with an AI coding and debugging laboratory.

A user submits a Python repository or a supported Git repository and asks:

"Investigate why this Python API endpoint is slow, identify the root cause, propose a fix, and verify that the fix works."

A possible workflow:

1. A Coordinator Agent creates a task plan.
2. A Repository Agent inspects the repository and relevant files.
3. An Analysis Agent identifies potential root causes.
4. A Test Agent runs existing tests in an isolated environment.
5. A Coding Agent proposes a patch.
6. A Verification Agent runs tests and benchmarks against the patch.
7. A Reviewer Agent checks correctness, test coverage, and unintended changes.
8. The Coordinator produces a final report.

Agents may execute concurrently when dependencies allow it.

The application must distinguish between a proposed fix and a verified fix. It must never claim that tests passed, a bug was fixed, or performance improved unless actual execution evidence supports that claim.

For the MVP, prefer a small, carefully controlled workflow over an unnecessarily complex autonomous multi-agent system.

---

# 3. Your First Responsibility: Guide Me Through Requirements

Do not immediately generate the entire application.

Start by acting as a product architect.

Help me turn this idea into a concrete product specification.

Identify:

- The primary users and their needs.
- The core problem we solve.
- The most important user journeys.
- The minimum viable product.
- Features that belong in later versions.
- Functional requirements.
- Non-functional requirements.
- Security and privacy requirements.
- Performance and scalability targets.
- Acceptance criteria for each major feature.
- Risks, assumptions, and unknowns.
- What makes the project meaningfully different from existing tools.

Ask me a small number of high-value questions at a time. Do not overwhelm me with dozens of questions in a single message.

For each major decision, explain the options, your recommendation, and the reasoning.

If a decision can reasonably be made using sensible defaults, recommend a default instead of blocking progress.

Create and maintain these project documents:

- `docs/PRODUCT_REQUIREMENTS.md`
- `docs/USER_JOURNEYS.md`
- `docs/MVP_SCOPE.md`
- `docs/ARCHITECTURE.md`
- `docs/TECH_STACK.md`
- `docs/DATABASE_DESIGN.md`
- `docs/API_SPECIFICATION.md`
- `docs/SECURITY_MODEL.md`
- `docs/IMPLEMENTATION_ROADMAP.md`
- `docs/ARCHITECTURE_DECISIONS/`

Keep the documents consistent as the project evolves.

Do not create all the documents as meaningless templates. Populate them with actual decisions and update them as we make progress.

---

# 4. Product Scope and Feature Priorities

Organize features into three levels.

## P0 — Essential MVP

- Task creation and execution.
- One LLM provider integration.
- A coordinator and a few specialized agents.
- Real tool calling.
- A Python repository inspection workflow.
- Controlled test execution.
- Human approval before applying proposed changes.
- Real-time execution updates.
- Interactive agent dependency graph.
- Agent detail panels.
- Tool-call and execution logs.
- Persistent task history.
- Final report containing evidence and verification status.
- Docker-based local development.
- Basic automated tests.
- A deployable demonstration environment.

## P1 — Advanced features

- Additional LLM providers through a common adapter.
- Execution replay and timeline scrubbing.
- Token usage, latency, and estimated cost analytics.
- Agent and tool performance comparisons.
- Evaluation datasets and repeatable benchmarks.
- Retry policies and failure recovery.
- Repository diff viewer.
- Before-and-after benchmark comparisons.
- Human-in-the-loop checkpoints.
- RAG over repository documentation.
- OpenTelemetry integration.
- Exportable execution traces.

## P2 — Research and advanced engineering

- Workflow templates.
- Parallel agent execution.
- Persistent and resumable workflows.
- Model routing and fallback policies.
- Custom agent and tool plugins.
- Multi-user workspaces and RBAC.
- Agent workflow comparison experiments.
- More advanced dependency visualization.
- Evaluation of correctness, reliability, and cost.
- A documented SDK or API for external integrations.

Do not attempt to build every feature before the MVP works end to end.

---

# 5. UI/UX Design Requirements

I want a polished, professional developer tool with the quality of a modern observability platform.

The interface should feel like a combination of a sophisticated engineering IDE, an AI execution control room, and an interactive data visualization application.

## Visual direction

Use a dark-first interface with:

- Deep navy and near-black surfaces.
- Restrained electric blue, violet, cyan, green, and amber accents.
- Clean typography.
- Strong visual hierarchy.
- Subtle borders and layered surfaces.
- Carefully designed loading, empty, error, and success states.
- Smooth but restrained animations.
- Consistent spacing and component design.
- Accessible contrast and keyboard interactions.

take examples of the attached pictures

Avoid generic AI landing pages, excessive neon, cluttered dashboards, unnecessary glassmorphism, and decorative elements that do not communicate information.

The UI must prioritize clarity and usability over visual effects.

## Core application screens

### A. Dashboard

Display:

- Recent executions.
- Running and failed workflows.
- Execution success rate.
- Average duration.
- Token consumption and estimated cost where available.
- Recent failures and alerts.
- Common task templates.
- A clear primary action to create a new task.

Metrics must be derived from stored execution data. Do not display invented statistics.

### B. New Task

Allow users to:

- Enter a natural-language task.
- Select a workflow template.
- Choose a configured model.
- Upload or connect a supported repository.
- Set execution limits.
- Review permissions and available tools.
- Start the workflow.

Clearly communicate what the system is authorized to do before execution starts.

### C. Live Execution Workspace

This is the signature screen.

Design a responsive workspace with:

1. A central interactive agent graph.
2. A task and workflow status panel.
3. A live event timeline.
4. An agent activity panel.
5. Tool invocation details.
6. A conversation or execution narrative.
7. A final output and evidence panel.

Provide both a 3D visualization and a 2D graph view.

Use React Three Fiber and Three.js for the 3D experience only where it adds genuine value. The 2D graph should remain a practical alternative for precise inspection and accessibility.

Represent actual execution states visually:

- Pending.
- Running.
- Waiting for approval.
- Completed.
- Failed.
- Cancelled.

Use meaningful transitions, not random animation.

Selecting an agent should open a detailed inspector showing its role, status, task, timestamps, inputs, outputs, associated tool calls, errors, and metrics.

Selecting a tool invocation should display its sanitized inputs, output summary, duration, status, and related trace identifiers.

### D. Execution Details and Replay

Allow users to inspect completed executions.

Provide:

- An ordered event timeline.
- Workflow dependency graph.
- Agent-level traces.
- Tool invocation history.
- Errors and retry attempts.
- Final artifacts.
- Replay of recorded events at different playback speeds.

Replay must use persisted historical events. It must not call the LLM again simply to reconstruct a previous execution.

Clearly distinguish recorded events from any newly generated analysis.

### E. Final Results

For coding workflows, provide:

- Problem summary.
- Identified root cause.
- Proposed patch.
- File-by-file diff.
- Test results.
- Benchmark results when available.
- Evidence supporting the conclusions.
- Known limitations.
- Recommended next steps.

Use explicit verification labels such as "Verified", "Partially verified", and "Not verified", backed by actual execution outcomes.

### F. Settings and Provider Configuration

Support secure configuration of model providers, model selection, timeouts, and execution limits.

Never expose API keys to the browser or include them in logs.

## Design workflow

Before implementing the complete frontend:

1. Define the information architecture.
2. Map the primary user journey.
3. Create a screen-by-screen specification.
4. Establish reusable components and design tokens.
5. Define component states and interactions.
6. Build the application shell and representative screens.
7. Connect the UI to actual backend events.
8. Refine the visual design after real data is flowing.

Prefer a cohesive, functioning application over a collection of disconnected mockups.

---

# 6. Backend Architecture

Act as a senior Python backend architect.

Design a maintainable backend with clear boundaries between API handling, orchestration, model integration, tools, execution, persistence, and event delivery.

Start with a modular monolith. Do not introduce microservices unless a demonstrated requirement justifies them.

## Preferred backend stack

- Python.
- FastAPI.
- Pydantic.
- PostgreSQL.
- SQLAlchemy and Alembic.
- Redis where caching, coordination, or queueing requires it.
- WebSockets or Server-Sent Events for real-time updates.
- Docker and Docker Compose.
- Pytest.
- Ruff and static type checking.
- OpenTelemetry for observability.

Evaluate LangGraph or a custom state machine for orchestration. Explain the trade-offs before committing to either.

Do not add Celery, a message broker, a vector database, or other infrastructure merely because it is popular. Introduce it when the requirements justify it.

## Suggested logical modules

Keep these responsibilities separate:

- `api`: HTTP endpoints, request validation, authentication, and response schemas.
- `orchestrator`: workflow planning, state transitions, dependencies, and scheduling.
- `agents`: agent definitions, roles, prompts, and execution policies.
- `llm`: provider adapters, structured outputs, retries, and usage metadata.
- `tools`: typed tools and permission enforcement.
- `sandbox`: isolated code and test execution.
- `events`: execution events and streaming.
- `persistence`: database models, repositories, and migrations.
- `evaluations`: correctness checks, benchmark runs, and evaluation reports.
- `observability`: tracing, metrics, structured logs, and correlation IDs.
- `security`: authorization, secret handling, audit records, and policies.

These are logical boundaries, not a requirement to create dozens of tiny files.

## Core domain entities

Evaluate the need for the following entities:

- User.
- Workspace.
- Task.
- WorkflowRun.
- AgentRun.
- WorkflowNode.
- WorkflowEdge.
- ExecutionEvent.
- ToolInvocation.
- ApprovalRequest.
- Artifact.
- EvaluationResult.
- ModelUsage.
- AuditLog.

For each entity, explain its purpose, relationships, constraints, indexes, and lifecycle.

Avoid duplicating state unnecessarily. Define which component owns workflow state and which data is derived for presentation.

## API design

Propose and document endpoints such as:

- `POST /api/v1/tasks`
- `GET /api/v1/tasks`
- `GET /api/v1/tasks/{task_id}`
- `POST /api/v1/tasks/{task_id}/runs`
- `GET /api/v1/runs/{run_id}`
- `POST /api/v1/runs/{run_id}/cancel`
- `GET /api/v1/runs/{run_id}/events`
- `GET /api/v1/runs/{run_id}/trace`
- `POST /api/v1/approvals/{approval_id}/decision`
- `GET /api/v1/runs/{run_id}/artifacts`

Treat these as initial proposals, not immutable requirements.

Define request and response schemas, authentication and authorization, pagination, error formats, idempotency, validation, and API versioning.

Use OpenAPI documentation generated by FastAPI.

## Real-time events

Define a versioned event schema with fields such as:

- `event_id`
- `run_id`
- `sequence_number`
- `timestamp`
- `event_type`
- `agent_run_id`
- `parent_event_id`
- `payload`

Design event types for:

- Workflow created.
- Workflow started.
- Agent started.
- Agent status changed.
- Tool invocation started.
- Tool invocation completed.
- Tool invocation failed.
- Approval requested.
- Approval resolved.
- Agent completed.
- Agent failed.
- Retry scheduled.
- Artifact created.
- Workflow completed.
- Workflow failed.
- Workflow cancelled.

Explain how events are persisted and streamed, how reconnection works, how duplicate delivery is handled, and how clients recover from missed updates.

Do not assume that WebSocket delivery itself guarantees durable event storage.

---

# 7. AI Agent Engineering

The application must use actual LLMs and actual tools.

## Agent design

Start with a coordinator and a small number of specialized agents:

- Coordinator Agent.
- Repository Analysis Agent.
- Debugging Agent.
- Test and Verification Agent.
- Review Agent.

Do not create separate agents when a normal deterministic function would be simpler and more reliable.

Give every agent a clear purpose, input schema, output schema, allowed tools, execution budget, timeout, and stopping conditions.

Use structured outputs wherever possible.

The coordinator should manage workflow state and dependencies rather than relying on a single giant prompt to control the entire application.

## Model provider abstraction

Create a provider abstraction that separates orchestration from any specific LLM vendor.

Start with one provider, such as Groq, Gemini, or another suitable provider. Keep the architecture extensible to additional hosted providers and local models through Ollama.

Compare providers based on:

- Tool-calling support.
- Structured output reliability.
- Latency.
- Context limits.
- Rate limits.
- Pricing.
- Availability of suitable models.
- Ease of development.

Verify current model availability and provider capabilities against official documentation when implementing the integration.

Never hardcode an assumed model name or claim a provider supports a feature without checking.

Keep credentials in environment variables or an appropriate secrets manager. Do not commit credentials.

## Tool calling

Create typed, validated tools for operations such as:

- Inspecting repository structure.
- Reading permitted files.
- Searching code.
- Running static analysis.
- Running tests.
- Inspecting Git diffs.
- Producing benchmark results.
- Searching approved documentation.

A model's request to call a tool is not authorization to execute it.

Validate arguments, check permissions, enforce resource limits, record the invocation, execute the tool, and return a bounded result.

Do not allow arbitrary shell execution, unrestricted filesystem access, unrestricted network access, or production modifications.

## RAG and embeddings

Do not implement RAG by default.

First determine whether repository documentation or historical execution records need semantic retrieval. If they do, propose an ingestion pipeline, chunking strategy, embedding model, retrieval mechanism, provenance tracking, and evaluation plan.

Explain whether PostgreSQL full-text search, pgvector, or a dedicated vector database is appropriate for the actual scale.

## Evaluation

Build a repeatable evaluation suite.

Measure:

- Task completion rate.
- Test pass rate.
- Tool-call success rate.
- Failure and retry rates.
- Execution duration.
- Model token usage.
- Estimated cost.
- Output validity.
- Evidence coverage.
- Regression rate.

Where possible, use deterministic tests and verifiable execution evidence rather than an LLM judging another LLM.

Define how to reproduce evaluations and compare model or workflow versions.

---

# 8. Security and Safety

Treat code execution and autonomous tool use as high-risk capabilities.

Security must be designed into the architecture, not added at the end.

At a minimum:

- Execute untrusted code in an isolated environment.
- Never run generated code directly on the API server.
- Use non-root containers and restrict Linux capabilities.
- Apply CPU, memory, disk, and execution-time limits.
- Restrict network access by default.
- Mount repository files with least privilege.
- Never mount the Docker socket into an agent sandbox.
- Keep secrets outside agent-visible files and environments.
- Prevent path traversal and unauthorized file access.
- Treat repository contents and tool outputs as untrusted data.
- Protect against prompt injection and malicious repository instructions.
- Require human approval for consequential actions.
- Prevent agents from modifying production infrastructure.
- Redact credentials and sensitive information from logs.
- Implement authentication, authorization, rate limits, and audit trails.
- Define cleanup and retention policies for temporary workspaces and artifacts.

Explain the threat model and the residual risks of the proposed sandbox.

Do not claim that ordinary Docker isolation makes arbitrary code execution completely safe. Recommend stronger isolation where the threat model requires it.

---

# 9. System Design Expectations

Before implementation, explain the complete request lifecycle:

1. The user creates a task.
2. The API validates and stores the request.
3. A workflow run is created.
4. The orchestrator initializes the workflow.
5. The coordinator assigns tasks.
6. Agents request tools or produce structured results.
7. The execution layer validates and runs permitted actions.
8. Events are persisted and streamed.
9. The frontend updates the live graph.
10. Evaluation and verification determine the result.
11. Artifacts and reports are persisted.
12. The user can inspect or replay the completed execution.

Produce Mermaid diagrams for:

- System context.
- Container and component architecture.
- Agent workflow.
- Database relationships.
- Execution event lifecycle.
- Code execution and approval flow.
- Deployment topology.

Discuss:

- Synchronous versus asynchronous execution.
- Failure recovery.
- Workflow resumability.
- Idempotency.
- Database transaction boundaries.
- Event ordering.
- Concurrency limits.
- Rate limiting.
- Caching.
- Cost controls.
- Observability.
- Deployment and rollback.
- Horizontal scaling.
- Data retention.

Explain which architectural choices are necessary for the MVP and which are only justified at larger scale.

Do not overengineer for millions of users before we have a working application.

---

# 10. Development Workflow and Mentoring Rules

I want to build this with you in phases.

Do not dump an entire repository of code in one response.

Use this workflow:

## Phase 1 — Discovery

Clarify product requirements, identify the MVP, resolve major uncertainties, and define measurable acceptance criteria.

## Phase 2 — Architecture

Select the stack, define module boundaries, design the database, specify API contracts, define event schemas, and document security boundaries.

## Phase 3 — UI and interaction design

Design the application shell, task creation flow, execution workspace, graph interactions, logs, inspector, and result screens.

## Phase 4 — Backend foundation

Set up the project, configuration, database, migrations, health checks, validation, logging, and initial API endpoints.

## Phase 5 — Real AI execution

Integrate the model provider, coordinator, specialized agents, typed tools, execution state machine, and durable event records.

## Phase 6 — Frontend integration

Connect the interface to the API and real event stream. Implement the graph, agent inspector, timeline, tool-call details, and result viewer.

## Phase 7 — Safe coding workflow

Implement isolated repository execution, tests, proposed patches, approval gates, and verification reports.

## Phase 8 — Testing and evaluation

Add unit tests, integration tests, API tests, frontend tests, security checks, and repeatable agent evaluation tasks.

## Phase 9 — Deployment

Create Docker Compose for local development, CI checks, environment configuration, production deployment instructions, and monitoring.

## Phase 10 — Portfolio and open source

Prepare architecture documentation, setup instructions, screenshots, demo scenarios, issue templates, contribution guidelines, and a strong project README.

After every phase, review what works, what remains, and whether the acceptance criteria have been met.

## How you should write code

When implementing a feature:

1. Explain the goal and design.
2. Identify the relevant files.
3. Explain the implementation approach.
4. Provide complete, consistent code for the required changes.
5. Explain important design decisions.
6. Provide exact commands to run.
7. Explain how to test the implementation.
8. Describe expected output or behavior.
9. Identify likely failure modes.
10. Update relevant documentation.

When modifying an existing file, inspect its current contents first. Do not blindly replace files or remove existing functionality.

When working in a repository through an available coding environment, inspect the actual codebase, run relevant tests, and make changes incrementally. Do not claim to have run commands or tests that you did not actually run.

Prefer small, reviewable changes over massive code dumps.

Explain important concepts such as asynchronous execution, state machines, transactions, dependency graphs, model tool calling, and distributed tracing when they become relevant.

Challenge unnecessary complexity and explain when a simpler implementation is better.

---

# 11. Code Quality Standards

Write code as if another engineer will maintain it.

Requirements:

- Clear module boundaries.
- Type hints.
- Pydantic validation.
- Explicit error handling.
- Structured logging.
- Centralized configuration.
- No hardcoded credentials.
- No unnecessary global mutable state.
- Database migrations.
- Meaningful automated tests.
- Reusable frontend components.
- Consistent formatting and linting.
- Documented public interfaces.
- Sensible naming conventions.
- Reproducible development setup.
- No fake data presented as live execution results.

Avoid enormous functions, unnecessary abstractions, magic constants, circular imports, and duplicated business logic.

Use mocks in tests where appropriate, but maintain at least one genuine end-to-end workflow that exercises the actual backend, configured model provider, permitted tools, event persistence, and frontend updates.

Clearly distinguish automated tests using mocks from tests requiring real API credentials.

---

# 12. Deployment and Open-Source Readiness

Design for a publicly accessible demonstration without assuming unlimited infrastructure or API budgets.

Plan for:

- Dockerized services.
- A simple local setup.
- Secure environment configuration.
- Database migrations.
- Health and readiness checks.
- CI/CD.
- Structured logs and error reporting.
- Usage quotas and execution timeouts.
- API provider limits.
- Resource cleanup.
- Safe handling of untrusted repositories.
- Basic uptime and failure monitoring.
- Clear deployment and rollback procedures.

Keep the public demo restricted to predefined tasks or controlled repositories until safe execution isolation is established.

Do not expose unrestricted shell access or allow anonymous users to execute arbitrary code on the host.

Prepare the repository for public contribution with:

- An excellent README.
- Architecture and sequence diagrams.
- A clear problem statement.
- A documented technology stack.
- Reproducible setup instructions.
- Example tasks.
- Tests and CI.
- Roadmap and contribution guidelines.
- Known limitations.
- A demo video or walkthrough.
- Meaningful issue and pull request templates.

Do not claim GSoC acceptance or SIH suitability as a guarantee. Help me identify relevant open-source communities and align any proposal with their actual contribution opportunities and requirements.

---

# 13. Definition of Done

The MVP is not complete merely because the dashboard looks good.

A successful MVP must allow a user to:

1. Open the application.
2. Create a real task.
3. Start an actual workflow.
4. Watch agents progress through real backend execution events.
5. Inspect agent details and actual tool invocations.
6. Observe a failure or retry when one occurs.
7. Review a proposed patch.
8. Approve or reject the patch.
9. Run verification in an isolated environment.
10. Inspect real test output and verification status.
11. View the final report and generated artifacts.
12. Reopen the execution history after the workflow finishes.
13. Replay the stored event sequence without rerunning the model.
14. Understand what happened, what failed, and why.

The application must also have automated tests for important business logic, event persistence, state transitions, authorization, and failure handling.

Every displayed metric and status must be backed by real data or clearly labeled as illustrative.

---

# 14. Your First Response

Begin with **Phase 1: Product Discovery**.

Do not start coding immediately.

In your first response, provide:

1. A concise product brief for AGENT-P.
2. The primary user persona and the problem being solved.
3. Your recommended MVP scope and what should be deferred.
4. The three most important architectural decisions we must make.
5. A proposed technology stack with a brief justification for each choice.
6. The biggest technical risks and how we should address them.
7. A short set of high-value questions that require my input.
8. A proposed development roadmap with milestones and acceptance criteria.

Explain the relationship between the product requirements, UI, backend architecture, agent execution engine, and security model.

Recommend sensible defaults where possible.

After I respond, refine the requirements and proceed step by step.

**Your ultimate goal is to help me build a real, polished, technically credible AGENT-P—not merely generate a large amount of code.**