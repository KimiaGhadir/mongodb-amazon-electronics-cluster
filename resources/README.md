# TA-provided resource

`docker-compose.yml` in this directory is the **original file supplied by the TA**, copied unchanged into the project for traceability.

The project root `../docker-compose.yml` keeps the same required core topology:

- `mongo:7`
- replica set name `rs0`
- nodes `mongo1`, `mongo2`, `mongo3`
- host ports `27017`, `27018`, `27019`
- automatic `mongo-init`
- `dev` service running inside the Compose network

The root file only adds safe project-level extensions:

1. `dev` waits for successful replica-set initialization before Python tools run.
2. An opt-in `mongo-standalone` service under profile `benchmark` is added for the required standalone/no-index benchmark phase.

Do not edit the original TA resource in this directory; make project changes in the root Compose file.
