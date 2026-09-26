# Architecture

The program will contain a few modules:

- Requester: makes requests to the API. Handles connection issues, search parameters and pagination
- Response parser: create a class that parses the API response from clinicaltrials.gov, performs data validation / cleanin and packages the processed results in a tabular structure
- Writer: pushes the parsed data to the database