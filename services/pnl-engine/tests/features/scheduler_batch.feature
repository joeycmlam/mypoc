@scheduler @pnl @smoke
Feature: APScheduler Sunday-Night P/L Batch
  As a portfolio manager
  I want P/L figures to be automatically refreshed every week without manual intervention
  So that Monday morning figures are always up to date

  Background:
    Given the portfolio service is running with APScheduler enabled
    And the price microservice at ":8300/get_prices" is available
    And at least one open position exists in the portfolio

  # ---------------------------------------------------------------------------
  # Job Registration
  # ---------------------------------------------------------------------------

  @smoke
  Scenario: All three cron jobs are registered at application startup
    When the portfolio service starts up
    Then the APScheduler contains exactly 3 registered cron jobs:
      | job_id                | schedule_utc | description                     |
      | price_fetch_sync      | Sun 21:00    | Fetch prices and sync to DB      |
      | unrealised_pnl_engine | Sun 22:00    | Unrealised P/L engine (WAC)      |
      | realised_pnl_engine   | Sun 22:00    | Realised P/L engine (WAC)        |
    And each job is in "active" state

  @regression
  Scenario: Scheduler configuration is loaded from external config, not hardcoded
    Given the scheduler cron expressions are defined in the application configuration file
    When the portfolio service starts up
    Then the registered job schedules match the values in the configuration file
    And changing the configuration and restarting the service updates the job schedules accordingly

  # ---------------------------------------------------------------------------
  # Execution Sequence
  # ---------------------------------------------------------------------------

  @smoke @scheduler
  Scenario: Price-fetch job runs before P/L jobs on Sunday night
    When Sunday 21:00 UTC arrives
    Then the "price_fetch_sync" job starts
    And the job fetches latest prices from ":8300/get_prices"
    And the job syncs prices to the portfolio database
    And the job completes before "Sun 22:00 UTC"

  @smoke @scheduler
  Scenario: Unrealised and realised P/L jobs run after prices are fetched
    Given the "price_fetch_sync" job completed successfully at "Sun 21:00 UTC"
    And fresh prices are available in the database for all active securities
    When Sunday 22:00 UTC arrives
    Then the "unrealised_pnl_engine" job runs using the freshly fetched prices
    And the "realised_pnl_engine" job runs using the WAC cost basis data
    And both jobs complete without error

  # ---------------------------------------------------------------------------
  # Logging & Observability
  # ---------------------------------------------------------------------------

  @regression
  Scenario: Each job logs start time, end time, records processed, and status
    When the "realised_pnl_engine" scheduled job completes
    Then the application log contains an entry with:
      | field              | presence   |
      | job_id             | required   |
      | start_time         | required   |
      | end_time           | required   |
      | records_processed  | required   |
      | status             | required   |
      | error_details      | if_failed  |

  @regression
  Scenario: Successful job run is logged with status "completed"
    Given all three cron jobs complete without error
    When the Sunday-night batch finishes
    Then each job has a log entry with status "completed"
    And "records_processed" is greater than or equal to 0

  # ---------------------------------------------------------------------------
  # Failure Handling — Price Fetch Failure
  # ---------------------------------------------------------------------------

  @negative @regression
  Scenario: Downstream P/L jobs are aborted when price-fetch job fails
    Given the price microservice at ":8300/get_prices" returns HTTP 500
    When the "price_fetch_sync" job runs at "Sun 21:00 UTC"
    Then the "price_fetch_sync" job is marked as "failed"
    And an error is logged: "Price fetch failed — downstream P/L jobs aborted"
    And the "unrealised_pnl_engine" job does not start
    And the "realised_pnl_engine" job does not start
    And no stale P/L records are written to the database

  @negative @regression
  Scenario: Price-fetch job fails gracefully when price microservice is unreachable
    Given the price microservice at ":8300/get_prices" is unreachable (connection timeout)
    When the "price_fetch_sync" job runs
    Then the job retries up to the configured maximum retry count
    And if all retries are exhausted, the job is marked "failed"
    And an alert is logged with severity "ERROR"

  # ---------------------------------------------------------------------------
  # Failure Handling — P/L Job Failure (Partial)
  # ---------------------------------------------------------------------------

  @negative @regression
  Scenario: A failing P/L job does not affect the other P/L job
    Given prices were fetched successfully
    And the "unrealised_pnl_engine" job encounters an unexpected database error mid-run
    When both P/L jobs attempt to run at "Sun 22:00 UTC"
    Then the "unrealised_pnl_engine" job is marked "failed" and its error is logged
    And the "realised_pnl_engine" job still runs independently
    And the "realised_pnl_engine" job completes with status "completed"

  # ---------------------------------------------------------------------------
  # Missed Run Behaviour
  # ---------------------------------------------------------------------------

  @regression
  Scenario: A missed scheduled run is not automatically retried by APScheduler
    Given the portfolio service was offline during "Sun 21:00–22:00 UTC"
    When the service comes back online
    Then no missed job runs are automatically triggered
    And a warning is logged: "Missed scheduled run — use ad-hoc endpoint to recalculate manually"

  @regression
  Scenario: Portfolio manager can use ad-hoc endpoint to compensate for a missed run
    Given the Sunday-night batch was missed due to a service outage
    When the portfolio manager calls "POST /api/v1/realised-pnl/calculate" manually
    Then the realised P/L is recalculated for all eligible positions
    And the response confirms "positions_updated" with a count greater than 0

  # ---------------------------------------------------------------------------
  # Edge Cases
  # ---------------------------------------------------------------------------

  @regression
  Scenario: Scheduler handles an empty portfolio without error
    Given no positions exist in the portfolio
    When the Sunday-night batch runs
    Then all three jobs complete with status "completed"
    And each job logs "records_processed: 0"
    And no errors are raised

  @regression
  Scenario: Two simultaneous scheduler trigger attempts do not cause duplicate runs
    Given the portfolio service is running with APScheduler
    When the same cron job is triggered twice within the same schedule window
    Then only one instance of the job executes
    And the second trigger is ignored or queued according to the misfire policy
