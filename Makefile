# Trinity Intelligence Platform - Operational Commands

.PHONY: help setup start stop test clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: ## Initial setup (copy .env, install dependencies)
	@echo "Setting up Trinity Intelligence Platform..."
	@cp -n .env.example .env || true
	@echo "✅ Environment file ready (.env)"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Edit .env if needed"
	@echo "  2. Run: make start"

start: ## Start all services
	@echo "Starting Trinity Intelligence Platform..."
	docker-compose up -d
	@echo ""
	@echo "✅ Services starting..."
	@echo ""
	@echo "Endpoints:"
	@echo "  Event Collector: http://localhost:8001"
	@echo "  Neo4j Browser:   http://localhost:7474"
	@echo "  Grafana:         http://localhost:3000"
	@echo "  Prometheus:      http://localhost:9090"
	@echo ""
	@echo "Check status: docker-compose ps"
	@echo "View logs: docker-compose logs -f"

stop: ## Stop all services
	docker-compose down

test: ## Run tests
	docker-compose up -d
	@echo "Waiting for services to be ready..."
	@sleep 10
	@echo "Testing event collector..."
	@curl -X POST http://localhost:8001/health
	@echo ""
	@echo "Testing webhook endpoint..."
	@curl -X POST http://localhost:8001/webhooks/github \
		-H "Content-Type: application/json" \
		-H "X-GitHub-Event: push" \
		-d '{"repository":{"full_name":"test/repo"},"commits":[{"id":"test123","author":{"name":"Test","email":"test@test.com"},"message":"Test","added":[],"modified":[]}]}'
	@echo ""
	@echo "✅ Test complete"

clean: ## Clean up (remove containers and volumes)
	docker-compose down -v
	@echo "✅ All containers and volumes removed"

logs: ## Show logs
	docker-compose logs -f

restart: ## Restart all services
	docker-compose restart
