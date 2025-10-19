# Agent Framework

This project is a working implementation of a multi-agent system designed to automate software development tasks. It uses a `LangGraph`-based orchestrator to manage a team of specialized AI agents (PM, DevOps, Frontend, QA, etc.) that work together to complete user stories.

The entire system is containerized using Docker and exposes a FastAPI interface for control and monitoring.

## Architecture

The system is built on a set of core principles:

- **Database as the Source of Truth:** A PostgreSQL database stores all project data, including user stories, tasks, logs, and artifacts.
- **LangGraph Orchestration:** A central state machine built with LangGraph manages the flow of work between agents.
- **Specialized Agents:** Each agent has a specific role and set of skills, defined by a system prompt and a set of allowed tools/permissions.
- **Contextual Task Bundles (CTB):** Agents receive tasks packaged with all necessary context, including project documentation and file attachments.
- **Guardrails:** Agents operate within a secure sandbox, with strict permissions on which files they can modify.

For detailed architectural decisions, please see the records in the `/ADR` directory.

## Prerequisites

- [Docker](https://www.docker.com/get-started)
- [Docker Compose](https://docs.docker.com/compose/install/)

## Getting Started

Follow these steps to build and run the entire agent framework.

### 1. Configure Environment Variables

The system requires environment variables for database connections and LLM API keys. A template is provided.

```bash
# From the agent_framework directory
cp .env.example .env
```

Now, open the `.env` file and add your `OPENAI_API_KEY`.

### 2. Build and Run the Services

Use Docker Compose to build the container images and start all services (API, database, worker) in the background.

```bash
# From the agent_framework directory
docker compose up --build -d
```

- `--build`: Forces Docker to rebuild the container images if the Dockerfile or application code has changed.
- `-d`: Runs the services in detached mode (in the background).

### 3. Verify the Services

You can check the status of the running containers:

```bash
docker compose ps
```

You should see the `agent_db`, `agent_redis`, `agent_api`, and `agent_worker` services running. To view the logs for a specific service (e.g., the API):

```bash
docker compose logs -f api
```

## How to Use the Framework

Once the services are running, you can interact with the system via the FastAPI interface at `http://localhost:8000`.

### View All Stories

Retrieve the current backlog of user stories and their tasks.

```bash
curl http://localhost:8000/stories
```

### Trigger a Workflow

Start the agent workflow for a specific user story. This is a non-blocking, "fire-and-forget" operation. The API will return immediately while the agents work in the background.

For example, to run the workflow for story `G1`:

```bash
curl -X POST http://localhost:8000/run/G1
```

### Check Workflow Status

Check the status of a story and its tasks to see the progress of the workflow.

```bash
curl http://localhost:8000/status/G1
```

### View Artifacts

List all artifacts (e.g., code files, test reports, specs) generated during the workflow for a story.

```bash
curl http://localhost:8000/artifacts/G1
```

## Project Structure

- `/api`: Contains the FastAPI application that serves the public API.
- `/ADR`: Architecture Decision Records, documenting key design choices.
- `/config`: YAML files for configuring models and agent roles.
- `/db`: The database schema (`schema.sql`) and seeding logic.
- `/docs`: Contains story-specific "Room Docs" where agents log their work.
- `/orchestrator`: The core of the system, including the LangGraph graph (`graph.py`) and agent implementations.
- `/prompts`: System prompts that define the personality and goals of each agent.
- `/tools`: Shell scripts used by agents to perform tasks like linting and testing.
- `/workspace`: The directory where agents write and modify code.
- `docker-compose.yml`: Defines all the services required to run the framework.
- `BACKLOG.md`: A read-only mirror of the database, automatically updated by the `worker` service.

## The Worker Service

The `worker` service runs in the background and performs two periodic tasks every 60 seconds:

1.  **Backlog Rendering:** It runs `orchestrator/render_backlog.py` to keep `BACKLOG.md` synchronized with the database.
2.  **Knowledge Distillation:** It runs `orchestrator/knowledge_worker.py` to analyze logs for error patterns, providing simple feedback for system improvement.