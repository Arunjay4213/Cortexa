.PHONY: install-dev test lint format build docker run-demo clean

install-dev:
	pip install -e ".[all,dev]"

test:
	pytest tests/ -v

lint:
	ruff check .

format:
	ruff format .

build:
	python -m build

docker:
	docker build -t cortexa .

run-demo:
	cx --demo

clean:
	rm -rf build/ dist/ *.egg-info __pycache__
