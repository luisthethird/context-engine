---
tags: [docs, architecture, system-design]
description: High-level system architecture overview
---

# Architecture Overview

## Components

- **API layer** — Python/FastAPI, deployed on Kubernetes
- **Data layer** — PostgreSQL (primary), Redis (cache)
- **Infrastructure** — GCP, managed via Terraform
- **CI/CD** — GitHub Actions, Kubernetes deployments

## Data Flow

```
Client -> API (k8s) -> PostgreSQL
                    -> Redis (cache hits)
```

## Key Design Decisions

- All infrastructure is declarative (Terraform + Kubernetes manifests)
- No stateful workloads outside managed databases
- Schema changes go through migration files in `team-data/schemas/`
