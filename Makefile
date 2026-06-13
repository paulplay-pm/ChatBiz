# ChatBiz -- integration test command entrypoint
# This Makefile is TEST INFRASTRUCTURE ONLY, not a build tool.
# Usage: make test-integration up
#        make test-integration down
#        make test-integration logs
#        make test-integration test

COMPOSE_PROJECT := chatbiz-test
COMPOSE_FILE := infrastructure/docker-compose-test.yml
COMPOSE := docker compose -p $(COMPOSE_PROJECT) -f $(COMPOSE_FILE)

.PHONY: test-integration test-integration-up test-integration-down test-integration-logs test-integration-test

CMD := $(filter-out test-integration,$(MAKECMDGOALS))

test-integration:
	@$(if $(CMD),,echo "Usage: make test-integration <up|down|test|logs>" ; exit 1)
	@case "$(CMD)" in \
	  up) $(MAKE) test-integration-up ;; \
	  down) $(MAKE) test-integration-down ;; \
	  logs) $(MAKE) test-integration-logs ;; \
	  test) $(MAKE) test-integration-test ;; \
	  *) echo "Unknown subcommand: $(CMD)"; echo "Usage: make test-integration <up|down|test|logs>"; exit 1 ;; \
	esac

test-integration-up:
	@if docker compose -p chatbiz ps -q 2>/dev/null | grep -q .; then \
	  echo "ERROR: production compose 'chatbiz' is running."; \
	  echo "Please run: docker compose -p chatbiz down"; \
	  exit 1; \
	fi
	@echo "Building frontend dist for nginx..."
	cd web/canvas && pnpm exec vite build
	cd web/admin && pnpm exec vite build
	$(COMPOSE) up --wait --quiet-pull

test-integration-down:
	$(COMPOSE) down --volumes

test-integration-logs:
	$(COMPOSE) logs -f

test-integration-test:
	set -e; \
	cd web/canvas && pnpm test:integration; \
	cd ../admin && pnpm e2e:integration; \
	cd ../canvas && pnpm e2e:integration

%:
	@:
