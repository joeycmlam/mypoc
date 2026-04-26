@ui @realised-pnl @smoke
Feature: UI — Ad-hoc Trigger for Realised P&L Calculation
  As a portfolio manager
  I want to trigger a Realised P&L recalculation from the portfolio dashboard UI
  So that I can review updated results without leaving the application or using technical API tooling

  Background:
    Given the portfolio manager is authenticated and on the P&L page
    And the "Recalculate Realised P&L" button is visible

  # ---------------------------------------------------------------------------
  # Happy Path — Button Trigger
  # ---------------------------------------------------------------------------

  @smoke
  Scenario: Portfolio manager triggers recalculation with no filters
    When the portfolio manager clicks "Recalculate Realised P&L"
    And submits the modal form without entering any filters
    Then a loading spinner is displayed while the calculation runs
    And on completion a success toast appears showing "positions_updated" and "execution_time_seconds"
    And the P&L figures on the dashboard are refreshed

  @smoke
  Scenario: Portfolio manager triggers recalculation with a date range filter
    When the portfolio manager clicks "Recalculate Realised P&L"
    And enters start_date "2026-01-01" and end_date "2026-03-31" in the modal form
    And submits the form
    Then a loading spinner is displayed
    And on completion a success toast confirms the recalculation scoped to that date range
    And only positions closed within "2026-01-01" to "2026-03-31" are updated on the dashboard

  @smoke
  Scenario: Portfolio manager triggers recalculation with a symbol filter
    When the portfolio manager clicks "Recalculate Realised P&L"
    And selects "AAPL" from the symbol multi-select in the modal form
    And submits the form
    Then a loading spinner is displayed
    And on completion a success toast confirms the recalculation for "AAPL"
    And only the "AAPL" P&L row is updated on the dashboard

  Scenario: Portfolio manager triggers recalculation with both date range and symbol filters
    When the portfolio manager clicks "Recalculate Realised P&L"
    And enters start_date "2026-02-01", end_date "2026-02-28", and selects symbol "TSLA"
    And submits the form
    Then the API is called with all three filters
    And a success toast confirms the scoped recalculation

  # ---------------------------------------------------------------------------
  # Loading State
  # ---------------------------------------------------------------------------

  @smoke
  Scenario: Button is disabled while a calculation is in progress
    Given the portfolio manager has clicked "Recalculate Realised P&L" and the calculation is running
    When the portfolio manager attempts to click "Recalculate Realised P&L" again
    Then the button is disabled (greyed out) and cannot be clicked
    And the loading spinner remains visible
    And no duplicate API call is made

  Scenario: Loading spinner disappears after the calculation completes
    Given the portfolio manager triggered a recalculation and the loading spinner is visible
    When the API call returns a 200 response
    Then the loading spinner disappears
    And the "Recalculate Realised P&L" button becomes enabled again

  # ---------------------------------------------------------------------------
  # Success Feedback
  # ---------------------------------------------------------------------------

  Scenario: Success toast displays positions updated and execution time
    Given the API returns: positions_updated=12, execution_time_seconds=1.43
    When the portfolio manager submits the recalculation form
    Then a success toast appears with the message "12 positions updated in 1.43s"
    And the toast auto-dismisses after a reasonable timeout

  # ---------------------------------------------------------------------------
  # Error Handling
  # ---------------------------------------------------------------------------

  @negative
  Scenario: Server error (HTTP 500) displays an error banner with detail
    Given the POST /api/v1/realised-pnl/calculate endpoint returns HTTP 500 with body "Internal Server Error"
    When the portfolio manager submits the recalculation form
    Then the loading spinner disappears
    And an error banner is displayed with the message "Internal Server Error"
    And the "Recalculate Realised P&L" button becomes enabled again

  @negative
  Scenario: Client error (HTTP 422) from invalid filter displays a descriptive error
    Given the portfolio manager enters an invalid date format "11-04-2026" in the start_date field
    When the portfolio manager submits the form
    Then the API returns HTTP 422
    And an error banner displays the server validation message referencing "start_date"
    And the form remains open so the manager can correct the input

  @negative
  Scenario: Network timeout displays a user-friendly error message
    Given the API call times out after the configured request timeout
    When the portfolio manager submits the recalculation form
    Then the loading spinner disappears
    And an error banner is displayed with the message "Request timed out. Please try again."
    And the button is re-enabled

  @negative
  Scenario: Session expiry during calculation redirects to login
    Given the portfolio manager's session expires while the calculation is running
    When the API returns HTTP 401
    Then the portfolio manager is redirected to the login page
    And a notification displays "Your session has expired. Please log in again."

  # ---------------------------------------------------------------------------
  # Modal Form Validation
  # ---------------------------------------------------------------------------

  @negative @regression
  Scenario Outline: Invalid date format in the modal shows an inline validation error
    When the portfolio manager enters "<invalid_date>" in the start_date field
    And attempts to submit the modal form
    Then the form is not submitted
    And an inline validation error "Please enter a valid date (YYYY-MM-DD)" is shown on start_date

    Examples:
      | invalid_date |
      | 11/04/2026   |
      | April 2026   |
      | 2026-13-01   |
      | not-a-date   |

  @regression
  Scenario: end_date must not be before start_date
    When the portfolio manager enters start_date "2026-03-31" and end_date "2026-01-01"
    And attempts to submit the modal form
    Then the form is not submitted
    And an inline validation error "End date must be on or after start date" is shown

  @regression
  Scenario: Submitting the modal with no filters sends the API call with an empty body
    When the portfolio manager opens the modal and immediately clicks "Submit" without any input
    Then the form is submitted
    And the API is called as "POST /api/v1/realised-pnl/calculate" with an empty request body

  # ---------------------------------------------------------------------------
  # Accessibility & UX
  # ---------------------------------------------------------------------------

  @regression
  Scenario: Modal is dismissible without triggering a calculation
    When the portfolio manager opens the recalculation modal
    And closes the modal by pressing "Escape" or clicking the "Cancel" button
    Then the modal closes
    And no API call is made
    And the button is enabled and ready

  @regression
  Scenario: Symbol multi-select shows only active securities
    When the portfolio manager opens the recalculation modal
    And inspects the symbol multi-select options
    Then only symbols with at least one active or historical position are listed
    And delisted or invalid tickers are not shown
