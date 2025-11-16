# Trinity Intelligence Platform

**AI-powered knowledge graph and investigation system for development teams**

Event-Driven CQRS architecture for real-time intelligence.

## What This Is

Developer intelligence platform providing:
- **Knowledge Graph**: Auto-updating graph of code, issues, solutions (Neo4j + AgentDB)
- **RCA Assistant API**: Root cause analysis in <30 seconds
- **Investigation API**: Pre-task investigation (find similar past work)
- **Architecture Monitor**: Real-time drift detection
- **Semantic Search**: Find similar issues/code via vector embeddings

## Features

- 🧠 **Automated Knowledge Graph**: Updates with every commit
- 🔍 **RCA in <30 sec**: Semantic search + graph traversal
- 📊 **Pre-Task Investigation**: Never repeat solved problems
- 🏥 **Health Monitoring**: Real-time service health scores
- 🏗️ **Architecture Monitor**: Live architecture state
- 🔒 **Enterprise Security**: RBAC, encryption, audit logging

## Architecture

```
trinity-intelligence-platform/
├── services/
│   ├── event-collector/       # GitHub webhooks
│   ├── code-analyzer/         # Parse commits
│   ├── kg-projector/          # Events → Neo4j
│   ├── vector-projector/      # Events → AgentDB
│   ├── rca-api/              # RCA endpoint
│   ├── investigation-api/    # Investigation endpoint
│   └── architecture-monitor/ # Drift detection
├── shared/
│   ├── events/               # Event schemas
│   ├── models/               # Pydantic models
│   └── utils/                # Common utilities
└── infrastructure/
    ├── docker-compose/       # Local dev (8 services)
    ├── kubernetes/           # Production
    └── terraform/            # Azure deployment
```

## Quick Start

```bash
# Local development
docker-compose up -d

# Call APIs
curl -X POST http://localhost:8000/api/rca \
  -H "Content-Type: application/json" \
  -d '{"issue": "calendar events not persisting"}'
```

## Status

**Version**: 0.1.0 (Week 1 pilot)
**Created**: November 16, 2025
**Implementation**: Phase 4 (Trinity Platform)
**Timeline**: 16 weeks starting June 2026
**Budget**: $188K (agent execution: $70K)

See [Phase 4 Execution Plan](https://github.com/jsill-71/NT-AI-Engine/blob/main/PHASE4_DETAILED_EXECUTION_PLAN.md) for complete roadmap.

## Integration

Monitors NT-AI-Engine repository:
- Receives GitHub webhooks
- Analyzes code changes
- Builds knowledge graph
- Provides intelligence APIs

Integrates with NT-AI-Engine:
- Trinity agent calls Investigation API before work
- Developers use RCA API for debugging
- GitHub App suggests solutions on issues
