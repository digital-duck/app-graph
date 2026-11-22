Let me read the relevant files to understand the system structure before writing the README.

# Dispatch

Dispatch is an incident management system built around a FastAPI backend that exposes CRUD endpoints for reference data and incident records. It models the core operational domain: severity levels, priority tiers, and incident types serve as reference tables that classify incidents, while the incident resource itself carries full foreign-key relationships back to each of them. The system is designed as a single-backend service — no frontend — giving integrators a clean HTTP API for building dashboards, alerting pipelines, or on-call tooling on top.

## Status

| Application | Result | Duration |
|---|---|---|
| manage_priorities | PASS | 13.1s |
| manage_severities | PASS | 14.1s |
| manage_incident_types | PASS | 17.7s |
| browse_incidents | PASS | 20.5s |
| create_incident | PASS | 13.7s |
| update_incident | PASS | 16.2s |

## Architecture

Single FastAPI backend running at `http://localhost:8006` — see [apps/dispatch/backend/README.md](apps/dispatch/backend/README.md) for setup, run, and test instructions.

## Running the full system

**1. Build the backend**

```bash
spl3 run spl/build_app.spl apps/dispatch/blueprint/main.graph.yaml
```

**2. Start the backend**

```bash
cd apps/dispatch/backend
uvicorn app.main:app --port 8006
```

## Applications

- **manage_priorities** — create, read, update, and delete priority levels used to classify incident urgency
- **manage_severities** — manage severity definitions that describe the impact scale of an incident
- **manage_incident_types** — maintain the taxonomy of incident categories (e.g. outage, degradation, security)
- **browse_incidents** — list and filter the incident log with FK-resolved reference fields
- **create_incident** — open a new incident record linked to a priority, severity, and type
- **update_incident** — edit an existing incident's fields, including reassigning its reference FK relationships