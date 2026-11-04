# Staging

## Purpose & Focus Areas

Turn the raw response object into structured rows and columns that later stages can rely on.

Focus Areas:
- Flattening mechanics (sql JSON operations)
- What belongs in a staging table --> no business decisions, just processing and structure
- Idempotency and utilization of snapshots

## Flattening Mechanics

Basic jsonb operations:
- #> --> follows a path and returns a json object
- #>> --> follows a path to a single value and returns it as text
- jsonb_array_elements() unpacks array elements into rows

General recommendation: stay in jsonb until you reach the final value to avoid multiple type transformations in later layers.

Why? Unscrupulous type conversions in staging can force later layers to perform conversion operations to revert the change. Carefully considering data types and transformations prevents later layers applying the transformations to create a data format and type they can directly process.

## What Belongs in Staging

Staging changes the data's shape but leaves the meaning alone. Operations that extract values and cast types belong in staging; filtering to remove record types, mastering records and transforming values based on business knowledge lives in later layers.

Why? Staging builds a stable base (data contract) that successive layers can rely on to transform the data by applying domain and business knowledge to suit specific applications. Mixing the two layers can create rework, data duplication and forcing the same transformation to be applied multiple times in downstream layers.

## Idempotency and Snapshots

There are two separate concepts:
1. Idempotency --> running the same code gives the same result
2. Correctness --> the result returned by the code is correct
