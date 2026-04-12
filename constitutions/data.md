# Data Domain Constitution

Applied when domain is 'data'. These rules govern data analysis, queries, and statistical work.

## Query correctness

- Verify that GROUP BY columns match the SELECT clause. Unlisted columns in
  GROUP BY silently produce non-deterministic results in MySQL; they are an
  error in standard SQL.
- Use explicit JOIN conditions. Never rely on implicit cross joins.
- For date arithmetic, use the database's date functions, not string manipulation.
- Test queries on a row-limited sample before running on full tables.

## Aggregation and statistics

- Report the sample size alongside any aggregate (mean, median, rate, percentage).
  An 80% success rate on 5 runs is not the same as on 500.
- State the time range for any time-series metric. "Average latency" is
  meaningless without "over what period".
- Distinguish correlation from causation explicitly if the analysis could be
  misread as causal.

## Data quality

- Flag missing data, NULLs, and outliers before drawing conclusions.
  Do not drop NULLs silently — state what was dropped and why.
- If a distribution is skewed, prefer median to mean and say so.
- Round to the significant figures warranted by the measurement precision,
  not to the maximum digits available.

## Schema and migrations

- Never drop a column without verifying it is unused in application code,
  dashboards, and downstream queries.
- Add new columns as nullable with a default before backfilling.
  Never add a NOT NULL column with no default to a populated table in one step.
- Test migrations on a copy of production data before running in production.

## Privacy and compliance

- Do not include PII (names, emails, IDs that identify individuals) in
  query results shared outside of secure channels.
- Aggregate or anonymize before sharing analysis results.
- If a dataset contains health, financial, or legal data, flag this before
  proceeding and confirm the handling is appropriate.
