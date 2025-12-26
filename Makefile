.PHONY: dev stop

DEV_PIDS := .dev-pids

dev:
	# use @ to prevent echoing commands
	@echo "Starting Loki port-forward..."
	# run in background with '&' and save PID to DEV_PIDS file
	kubectl port-forward -n logging svc/loki 3100:3100 & \
	# save PID of last background process ($$!) to DEV_PIDS file
	echo $$! >> $(DEV_PIDS)

	@echo "Starting LLaMA port-forward..."
	# run in background with '&' and save PID to DEV_PIDS file
	kubectl port-forward -n llm svc/llama-cpp 8080:8080 & \
	# save PID of last background process ($$!) to DEV_PIDS file
	echo $$! >> $(DEV_PIDS)

	@echo "Waiting for dependencies..."
	@helpers/wait-for.sh http://localhost:3100/ready
	@helpers/wait-for.sh http://localhost:8080/v1/models

	@echo "Starting FastAPI..."
	# when process recieves ctrl-c or exits run 'make stop' for clean shutdown
	trap 'make stop' INT TERM EXIT; \
	cd workloads/log-analyzer && \
	uv run fastapi dev src/log_analyzer/main.py

stop:
	@echo "Stopping dev processes..."
	# if pid file exists, kill the pids listed in it, prevent errors with '|| true'
	@-test -f $(DEV_PIDS) && kill `cat $(DEV_PIDS)` || true
	# remove runtime state
	@rm -f $(DEV_PIDS)
