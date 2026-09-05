.PHONY: all install test bench demo check-clean

PYTHON ?= python3

all: test bench

install:
	$(PYTHON) -m pip install -e .
	$(PYTHON) -m pip install -r requirements-dev.txt

test:
	$(PYTHON) -m pytest tests/ -v

bench:
	$(PYTHON) experiments/run_tier_b.py
	$(PYTHON) experiments/run_tier_c.py
	$(PYTHON) experiments/run_phase4_llm.py
	$(PYTHON) experiments/run_ladder.py --regime all --llm-mode replay

demo:
	$(PYTHON) -m streamlit run app.py

check-clean:
	git status --porcelain
