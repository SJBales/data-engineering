# Raw

- What: append-only storage that includes the object identifier (nct_id), raw_response object, search params, url and fetched_at

- Why: preserving fetched_at in combination with nct_id creates a history of the API repsonses over time. A history allows you to inspect and understand changes in the underlying object. Retaining the raw response object allows for re-runs of logic for subsequent layers if issues in the code are discovered later, it changes, or extracting more variables later.

- How: Capturing search params and url created lineage -- knowing how that record landed in your database. Fetched_at creates a snapshot of each record that lands in the raw layer. History is preserved in the raw with this structure -- transformations creating staging in the mastering pipelines should remove duplicate nct_id's by calling distinct on (nct_id) and including "order by fetched_at desc" to grab the most recent API responses.

- Concepts: 
  - Immutable raw data --> data received never changes 
  - Reproducibility --> any downstream table can be rebuilt from raw plus code
  - Separation of concerns --> layers divide tasks into stages with specific goals
  - Idempotency --> running the same step twice yields the exact same result

- Open Questions: 

1. When would you choose append-only storage over other types? The updside of append-only storage is creating immutable raw data, allowing for changing and re-running transformation logic. The downside of append-only is the volume of storage and its cost. Choose upsert storage when the cost of storing the data exceeds the value from retaining a history.

2. What other considerations (i.e. cost, complexity, time, etc.) do organizations consider when choosing between options? (1) storage cost, mentioned above; (2) query complexity; (3) how long to retain the raw responses; (4) compliance requirements to see what actions where taken, changes made and by whom
