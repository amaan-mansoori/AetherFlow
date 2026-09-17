# ADR-0001: Modular Monolith with Independent Processes

**Status:** Accepted  
**Date:** 2026-09-16

## Decision

Use one modular codebase with independently runnable API, worker, and scheduler capability. Extract a service only when runtime scaling, reliability isolation, or ownership provides evidence.

## Rationale

This preserves simple local development and end-to-end testing while separating the API and worker failure/scaling domains. It avoids microservices as decoration.

## Consequences

Modules require strict dependency direction and contract tests. Deployment has multiple process images/commands, but no premature network boundaries.

