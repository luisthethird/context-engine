---
tags: [docs, onboarding, setup]
description: New engineer environment setup guide
---

# Onboarding Guide

## Prerequisites

- Install: git, python 3.10+, docker, kubectl
- Access: request VPN credentials from IT, Kubernetes cluster access from infra team

## First Week Checklist

- [ ] Clone all repos in the workspace
- [ ] Run `generate_index.py --vault . --split` to build the context index
- [ ] Read `CLAUDE.md` at the workspace root
- [ ] Review `docs/architecture.md`

## Common Commands

```bash
# Rebuild the context index after structural changes
python generate_index.py --vault /path/to/workspace --output /path/to/workspace --split
```
