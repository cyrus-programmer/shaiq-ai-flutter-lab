.PHONY: check test demo

test:
	PYTHONPATH=src python -m unittest discover -s tests -v

check:
	python -m compileall -q src tests
	PYTHONPATH=src python -m unittest discover -s tests -v

demo:
	PYTHONPATH=src python -m toolsafe.cli run --script examples/support-agent.json --message "Where is order ORD-100?"
