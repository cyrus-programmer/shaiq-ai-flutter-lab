.PHONY: check test demo

test:
	PYTHONPATH=src python -m unittest discover -s tests -v

check:
	python -m compileall -q src tests
	PYTHONPATH=src python -m unittest discover -s tests -v

demo:
	mkdir -p /tmp/promptlab-demo
	PYTHONPATH=src python -m promptlab.cli run examples/support-triage.json --output /tmp/promptlab-demo/candidate.json --markdown /tmp/promptlab-demo/report.md --junit /tmp/promptlab-demo/junit.xml
	PYTHONPATH=src python -m promptlab.cli compare examples/baseline.json /tmp/promptlab-demo/candidate.json --max-regressions 0

