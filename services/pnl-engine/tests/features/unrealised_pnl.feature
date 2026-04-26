@pnl @unrealised-pnl @smoke
Feature: Unrealised P/L Engine
  As a portfolio manager
  I want unrealised P/L to be calculated automatically every week and on demand
  So that I can see the current paper gain/loss on all open positions at any time

  Background:
    Given the portfolio service is running
    And the price microservice at ":8300/get_prices" is available
    And the user is authenticated with a valid JWT token

  # ---------------------------------------------------------------------------
  # Happy Path — Scheduled Run
  # ---------------------------------------------------------------------------

  @smoke @scheduler
  Scenario: Weekly scheduled job recalculates unrealised P/L for all open positions
    Given the following open positions exist in the portfolio:
      | symbol | quantity | wac_cost | currency |
      | AAPL   | 100      | 150.00   | USD      |
      | TSLA   | 50       | 200.00   | USD      |
      | 0700.HK| 200      | 320.00   | HKD      |
    And the price microservice returns:
      | symbol  | current_price |
      | AAPL    | 175.00        |
      | TSLA    | 180.00        |
      | 0700.HK | 350.00        |
    When the APScheduler unrealised P/L cron job fires at "Mon 06:00 HKT"
    Then unrealised P/L is calculated for all 3 open positions
    And the results are persisted to the database
    And the unrealised P/L for "AAPL" is 2500.00 USD
    And the unrealised P/L for "TSLA" is -1000.00 USD
    And the unrealised P/L for "0700.HK" is 6000.00 HKD

  @scheduler
  Scenario: Scheduled job runs after price-fetch job completes successfully
    Given the price-fetch cron job completed successfully at "Mon 05:00 HKT"
    And fresh prices are available in the database for all active securities
    When the APScheduler unrealised P/L cron job fires at "Mon 06:00 HKT"
    Then the unrealised P/L engine uses the prices fetched at "Mon 05:00 HKT"
    And the job completes without error

  # ---------------------------------------------------------------------------
  # Happy Path — Ad-hoc API Trigger
  # ---------------------------------------------------------------------------

  @smoke @api
  Scenario: Ad-hoc calculation returns updated P/L summary for all positions
    Given 5 open positions exist in the portfolio with valid WAC cost data
    And the price microservice returns current prices for all 5 symbols
    When the portfolio manager calls "POST /api/v1/unrealised-pnl/calculate"
    Then the response status is 200
    And the response body contains "positions_updated" equal to 5
    And the response body contains a positive "execution_time_seconds" value

  @api
  Scenario: Ad-hoc calculation with symbol filter only recalculates the specified position
    Given open positions exist for "AAPL", "MSFT", and "GOOGL"
    When the portfolio manager calls "POST /api/v1/unrealised-pnl/calculate" with symbol "AAPL"
    Then the response status is 200
    And the response body contains "positions_updated" equal to 1
    And only the "AAPL" unrealised P/L record is updated in the database

  @api
  Scenario: Ad-hoc calculation with date range filter scopes results correctly
    Given historical trade data exists for "AAPL" between "2026-01-01" and "2026-03-31"
    When the portfolio manager calls "POST /api/v1/unrealised-pnl/calculate" with start_date "2026-01-01" and end_date "2026-03-31"
    Then the response status is 200
    And only positions opened within that date range are recalculated

  # ---------------------------------------------------------------------------
  # WAC Cost Basis Validation
  # ---------------------------------------------------------------------------

  @regression @wac
  Scenario: Unrealised P/L is calculated using Weighted Average Cost method
    Given "AAPL" was purchased in two lots:
      | lot | quantity | purchase_price |
      | 1   | 60       | 140.00         |
      | 2   | 40       | 165.00         |
    And the WAC cost basis for "AAPL" is 150.00 USD per share
    And the current market price for "AAPL" is 175.00 USD
    When the unrealised P/L engine processes "AAPL"
    Then the unrealised P/L for "AAPL" is 2500.00 USD
    And the calculation uses 150.00 as the cost basis, not 140.00 or 165.00

  # ---------------------------------------------------------------------------
  # Edge Cases
  # ---------------------------------------------------------------------------

  @regression
  Scenario: No open positions results in zero updates
    Given no open positions exist in the portfolio
    When the portfolio manager calls "POST /api/v1/unrealised-pnl/calculate"
    Then the response status is 200
    And the response body contains "positions_updated" equal to 0

  @regression
  Scenario: Position with zero quantity is excluded from calculation
    Given a position for "AAPL" exists with quantity 0 (fully closed)
    When the unrealised P/L engine runs
    Then the "AAPL" position is excluded from the unrealised P/L calculation

  @regression
  Scenario Outline: Unrealised P/L sign is correct for gain and loss positions
    Given an open position for "<symbol>" with WAC cost "<wac>" and current price "<price>"
    When the unrealised P/L engine calculates for "<symbol>"
    Then the unrealised P/L is "<expected_pnl>" USD

    Examples:
      | symbol | wac    | price  | expected_pnl |
      | AAPL   | 150.00 | 175.00 | +2500.00     |
      | TSLA   | 200.00 | 180.00 | -1000.00     |
      | MSFT   | 300.00 | 300.00 | 0.00         |

  # ---------------------------------------------------------------------------
  # Price Unavailability / Partial Failure
  # ---------------------------------------------------------------------------

  @negative @regression
  Scenario: Position is skipped and logged when market price is unavailable
    Given open positions exist for "AAPL" and "UNKNOWN_TICKER"
    And the price microservice returns a price for "AAPL" but not for "UNKNOWN_TICKER"
    When the unrealised P/L engine runs
    Then unrealised P/L is calculated and persisted for "AAPL"
    And "UNKNOWN_TICKER" is skipped
    And a warning is logged: "Price unavailable for UNKNOWN_TICKER — position skipped"
    And the job completes without raising an exception

  @negative @regression
  Scenario: Engine aborts if the price microservice is entirely unreachable
    Given the price microservice at ":8300/get_prices" is unreachable
    When the APScheduler unrealised P/L cron job fires
    Then the job is aborted
    And an error is logged: "Price microservice unavailable — unrealised P/L job aborted"
    And no P/L records are updated in the database

  # ---------------------------------------------------------------------------
  # Security
  # ---------------------------------------------------------------------------

  @negative @security
  Scenario: Unauthenticated request to ad-hoc endpoint is rejected
    Given the user does not provide a JWT token
    When the user calls "POST /api/v1/unrealised-pnl/calculate"
    Then the response status is 401
    And the response body contains "Unauthorized"

  @negative @security
  Scenario: Request with an expired JWT token is rejected
    Given the user provides an expired JWT token
    When the user calls "POST /api/v1/unrealised-pnl/calculate"
    Then the response status is 401
    And the response body contains "Token expired"

  # ---------------------------------------------------------------------------
  # Idempotency
  # ---------------------------------------------------------------------------

  @regression
  Scenario: Running the calculation twice does not duplicate records
    Given 3 open positions exist in the portfolio
    When the portfolio manager calls "POST /api/v1/unrealised-pnl/calculate" twice in succession
    Then exactly 3 unrealised P/L records exist in the database (no duplicates)
    And the second call overwrites the first call's results
