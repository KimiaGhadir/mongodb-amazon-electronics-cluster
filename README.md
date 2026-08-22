# Distributed MongoDB Cluster for Amazon Electronics Analytics

This project implements a distributed database system using MongoDB for storing and analyzing Amazon Electronics product metadata.

The system is built around a three-node MongoDB Replica Set and includes data ingestion, schema transformation, query optimization, indexing, failover handling, race condition analysis, and performance evaluation.

## Project Overview

The project uses the Amazon Electronics Metadata dataset. Each record represents a product and contains information such as product identifiers, titles, categories, and dynamic technical specifications.

Because of the large size of the dataset, data ingestion is performed using a streaming approach to avoid loading the entire dataset into memory.

## System Architecture

The database is deployed as a three-node MongoDB Replica Set:

```
Node 1 : 27017
Node 2 : 27018
Node 3 : 27019
```

At any time:

* One node acts as the Primary node.
* Two nodes work as Secondary replicas.

The system follows these rules:

* Write operations are executed on the Primary node.
* Read operations can be distributed across replicas.
* If the Primary node fails, MongoDB automatically performs an election and selects a new Primary.

## Data Processing and Schema Design

Two main transformations are applied during preprocessing.

### Category Flattening

The original hierarchical category structure is converted into an array format.

Example:

```json
{
  "categories": [
    "Electronics",
    "Computers",
    "Laptops"
  ]
}
```

This design improves category filtering and allows efficient indexing.

### Dynamic Feature Modeling

Since different products have different technical specifications, the `details` field is stored as a Key-Value array.

Example:

```json
{
  "details": [
    {
      "k": "RAM",
      "v": "16GB"
    }
  ]
}
```

This structure provides a consistent way to query and index dynamic product attributes.

## Implemented Queries

The project supports five main query categories:

### 1. Product Lookup

Retrieve complete information of a product using its Amazon identifier.

### 2. Catalog Pagination

Retrieve product lists using pagination to avoid loading large amounts of data.

### 3. Category Search

Find products belonging to a specific category regardless of its depth in the hierarchy.

### 4. Technical Feature Search

Search products based on a specific technical feature and value.

### 5. Combined Filtering

Support multiple feature filtering using:

* AND conditions
* OR conditions

## Indexing and Optimization

Indexes are created to improve query performance, including:

* Product identifier index
* Multikey index for categories
* Compound index for technical attributes
* Text index for text search

Query performance is analyzed using MongoDB `explain()` before and after indexing.

## Failover Testing

A live failover scenario is implemented to evaluate system reliability.

The process includes:

1. Stopping the current Primary node.
2. Allowing MongoDB Replica Set election to select a new Primary.
3. Restarting the failed node and verifying that it rejoins as a Secondary.

## Race Condition Handling

A concurrent update scenario is designed to demonstrate race conditions.

The project evaluates how multiple users updating the same field can cause inconsistent results and uses MongoDB atomic update operations to prevent lost updates.

## Performance Evaluation

The system is evaluated in three different configurations:

1. Standalone MongoDB without indexes
2. MongoDB Cluster without indexes
3. Optimized MongoDB Cluster with indexes

Performance metrics such as query latency and throughput are collected and analyzed.

## Technologies

* MongoDB
* MongoDB Replica Set
* Docker
* Docker Compose
* Python
* PyMongo
* Pandas
* Matplotlib
* Pytest

## Running the Project

Start the MongoDB cluster:

```bash
docker compose up -d
```

Run the data ingestion process:

```bash
python src/ingest.py
```

Create indexes:

```bash
python src/indexes.py create
```

Query execution and benchmarking scripts are available inside the `src` directory.

## Project Structure

```
.
├── docker-compose.yml
├── src/
│   ├── ingest.py
│   ├── queries.py
│   ├── indexes.py
│   ├── benchmark.py
│   └── race_condition.py
│
├── scripts/
├── queries/
├── results/
├── tests/
└── docs/
```

## Project Goal

The goal of this project is to explore distributed database concepts using MongoDB, including Replica Sets, workload distribution, query optimization, indexing, fault tolerance, and concurrency management.
