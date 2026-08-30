PY=docker compose --profile tools run --rm dev python

up:
	docker compose up -d

build-tools:
	docker compose --profile tools build dev

down:
	docker compose down

reset:
	docker compose --profile benchmark down -v --remove-orphans

sample:
	$(PY) src/ingest.py data/sample_500.jsonl --drop --batch-size 100

indexes:
	$(PY) src/indexes.py create

no-index:
	$(PY) src/indexes.py drop

status:
	$(PY) src/failover_check.py

race:
	$(PY) src/race_condition.py --workers 50

race-benchmark:
	$(PY) src/race_benchmark.py --workers 10,25,50,100 --operations 500 --out results/race_benchmark.csv

plots:
	$(PY) src/plot_results.py

test:
	docker compose --profile tools run --rm --no-deps dev pytest -q
