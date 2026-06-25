VENV = .venv

.PHONY: create_environment
create_environment:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -r requirements.txt

.PHONY: run
run:
	$(VENV)/bin/python server.py

.PHONY: run_reload
run_reload:
	$(VENV)/bin/uvicorn server:app --host 0.0.0.0 --port 8000 --reload
