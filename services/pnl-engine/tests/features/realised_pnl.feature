@pnl @realised-pnl @smoke
Feature: Realised P/L Engine
  As a portfolio manager
  I want realised P/L to be calculated automatically every week and on demand
  So that I can see the confirmed gain/loss on all closed or partially-closed positions

  Background:
    Given the portfolio service is running
    And the user is authenticated with a valid JWT token

  # ---------------------------------------------------------------------------
  # Happy Path — Scheduled Run
  # ---------------------------------------------------------------------------

  @smoke @scheduler
  Scenario: Weekly scheduled job recalculates realised P/L for all closed positions
    Given the following closed positions exist in the portfolio:
      | symbol | quantity_sold | wac_cost | sell_price | sell_date  |
      | AAPL   | 50            | 150.00   | 175.00     | 2026-03-10 |
      | TSLA   | 30            | 200.00   | 180.00     | 2026-03-15 |
    When the APScheduler realised P/L cron job fires at "Mon 06:00 HKT"
    Then realised P/L is calculated for all 2 closed positions
    And the results are persisted to the database
    And the realised P/L for "AAPL" lot is +1250.00 USD
    And the realised P/L for "TSLA" lot is -600.00 USD

  @scheduler
  Scenario: Scheduled job processes partially-closed positions correctly
    Given "AAPL" was bought as 100 shares at WAC 150.00
    And 40 shares of "AAPL" were sold at 175.00 on "2026-03-10"
    And 60 shares of "AAPL" remain open
    When the APScheduler realised P/L cron job fires
    Then realised P/L for the 40 sold "AAPL" shares is +1000.00 USD
    And unrealised P/L is still tracked for the remaining 60 shares

  # ---------------------------------------------------------------------------
  # Happy Path — Ad-hoc API Trigger (POST /api/v1/realised-pnl/calculate)
  # ---------------------------------------------------------------------------

  @smoke @api
  Scenario: Ad-hoc calculation with no filters processes all eligible positions
    Given 4 closed positions exist in the portfolio with complete trade data
    When the portfolio manager calls "POST /api/v1/realised-pnl/calculate" with no filters
    Then the response status is 200
    And the response body contains "positions_updated" equal to 4
    And the response body contains a positive "execution_time_seconds" value

  @api
  Scenario: Ad-hoc calculation with symbol filter recalculates only that symbol
    Given closed positions exist for "AAPL", "MSFT", and "GOOGL"
    When the portfolio manager calls "POST /api/v1/realised-pnl/calculate" with symbol "MSFT"
    Then the response status is 200
    And the response body contains "positions_updated" equal to 1
    And only the "MSFT" realised P/L record is updated

  @api
  Scenario: Ad-hoc calculation with date range scopes by sell date
    Given closed positions exist with sell dates across January, February and March 2026
    When the portfolio manager calls "POST /api/v1/realised-pnl/calculate" with start_date "2026-02-01" and end_date "2026-02-28"
    Then the response status is 200
    And only positions sold between "2026-02-01" and "2026-02-28" are recalculated

  @api
  Scenario: Ad-hoc calculation combining symbol and date range filters
    Given multiple closed "AAPL" trades exist across different months
    When the portfolio manager calls "POST /api/v1/realised-pnl/calculate" with symbol "AAPL", start_date "2026-03-01" and end_date "2026-03-31"
    Then only "AAPL" trades closed within March 2026 are included in the calculation

  # ---------------------------------------------------------------------------
  # WAC Cost Basis Validation
  # ---------------------------------------------------------------------------

  @regression @wac
  Scenario: Realised P/L uses Weighted Average Cost and not individual lot prices
    Given "AAPL" was purchased in two lots:
      | lot | quantity | purchase_price |
      | 1   | 60       | 140.00         |
      | 2   | 40       | 165.00         |
    And the WAC cost basis is computed as 150.00 USD per share
    And 50 shares of "AAPL" are sold at 175.00 USD
    When the realised P/L engine processes the "AAPL" sell trade
    Then the realised P/L is +1250.00 USD
    And the calculation uses 150.00 as the cost basis, not 140.00 or 165.00

  @regression @wac
  Scenario: WAC cost basis is updated after a buy trade before next sell
    Given "AAPL" has an existing WAC of 150.00 for 100 shares
    And 50 additional "AAPL" shares are bought at 180.00
    And the new WAC is 160.00 USD per share
    When 80 shares of "AAPL" are sold at 170.00
    Then the realised P/L is +800.00 USD
    And the calculation uses 160.00 as the cost basis

  # ---------------------------------------------------------------------------
  # Edge Cases
  # ---------------------------------------------------------------------------

  @regression
  Scenario: No closed positions results in zero updates
    Given no closed or partially-closed positions exist in the portfolio
    When the portfolio manager calls "POST /api/v1/realised-pnl/calculate"
    Then the response status is 200
    And the response body contains "positions_updated" equal to 0

  @regression
  Scenario Outline: Realised P/L sign is correct for various trade outcomes
    Given a sell trade: "<quantity>" shares of "<symbol>" sold at "<sell_price>" with WAC "<wac>"
    When the realised P/L engine processes the trade
    Then the realised P/L is "<expected_pnl>" USD

    Examples:
      | symbol | quantity | wac    | sell_price | expected_pnl |
      | AAPL   | 50       | 150.00 | 175.00     | +1250.00     |
      | TSLA   | 30       | 200.00 | 180.00     | -600.00      |
      | MSFT   | 20       | 300.00 | 300.00     | 0.00         |

  @regression
  Scenario Outline: Invalid date format in request returns HTTP 422
    When the portfolio manager calls "POST /api/v1/realised-pnl/calculate" with start_date "<date>"
    Then the response status is 422
    And the response body contains a validation error mentioning "start_date"

    Examples:
      | date        |
      | 11-04-2026  |
      | April 2026  |
      | 2026/04/11  |
      | not-a-date  |

  # ---------------------------------------------------------------------------
  # Incomplete / Missing Trade Data
  # ---------------------------------------------------------------------------

  @negative @regression
  Scenario: Position with missing cost data is skipped and logged
    Given a closed position for "BAD_TICKER" exists with no WAC cost data
    And a valid closed position for "AAPL" also exists
    When the realised P/L engine runs
    Then realised P/L is calculated and persisted for "AAPL"
    And "BAD_TICKER" is skipped
    And a warning is logged: "Missing cost data for BAD_TICKER — position skipped"
    And the job completes without raising an exception

  @negative @regression
  Scenario: Position with missing sell price record is skipped
    Given a partially-closed position for "ORPHAN" exists with no corresponding sell trade record
    When the realised P/L engine runs
    Then "ORPHAN" is skipped
    And a warning is logged: "No sell trade record found for ORPHAN — position skipped"

  # ---------------------------------------------------------------------------
  # Security
  # ---------------------------------------------------------------------------

  @negative @security
  Scenario: Unauthenticated request is rejected with HTTP 401
    Given the user does not provide a JWT token
    When the user calls "POST /api/v1/realised-pnl/calculate"
    Then the response status is 401
    And the response body contains "Unauthorized"

  @negative @security
  Scenario: Request with an expired JWT token is rejected with HTTP 401
    Given the user provides an expired JWT token
    When the user calls "POST /api/v1/realised-pnl/calculate"
    Then the response status is 401
    And the response body contains "Token expired"

  # ---------------------------------------------------------------------------
  # Idempotency & Concurrency
  # ---------------------------------------------------------------------------

  @regression
  Scenario: Running the calculation twice does not duplicate records
    Given 3 closed positions exist in the portfolio
    When the portfolio manager calls "POST /api/v1/realised-pnl/calculate" twice in succession
    Then exactly 3 realised P/L records exist in the database
    And the second call overwrites the first call's results with no duplicates

  @regression
  Scenario: Concurrent duplicate requests are handled gracefully
    Given a realised P/L calculation is already in progress
    When a second "POST /api/v1/realised-pnl/calculate" request arrives concurrently
    Then the second request either queues or returns HTTP 409 with message "Calculation already in progress"
    And the database is not left in a corrupted or partial state
