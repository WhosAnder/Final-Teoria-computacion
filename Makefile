# Mini-Lang compiler - common tasks (requires only Python 3.9+)
PY ?= python3

.PHONY: test unit golden grammar demo demo-error clean

test: unit golden            ## run every test

unit:                        ## unit tests, one class per phase
	$(PY) -m unittest discover -s tests/unit -v

golden:                      ## end-to-end tests against tests/expected/
	$(PY) scripts/run_tests.py

grammar:                     ## FIRST/FOLLOW sets and LL(1) check
	$(PY) scripts/ll1_check.py docs/grammar.txt

demo:                        ## full pipeline on the sample program
	$(PY) scripts/minilangc.py examples/pdf_example.src -o build/demo

demo-error:                  ## semantic-error demo
	-$(PY) scripts/minilangc.py tests/programs/s02_type_error.src -o build/demo-error

clean:
	rm -rf build
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
