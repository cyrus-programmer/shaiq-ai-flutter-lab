.PHONY: run test check docker-build

run:
	PYTHONPATH=src python -m citeguard.api

test:
	PYTHONPATH=src python -m unittest discover -s tests -v

check:
	python -m compileall -q src tests
	PYTHONPATH=src python -m unittest discover -s tests -v

docker-build:
	docker build -t citeguard-rag-api .

