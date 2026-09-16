Feature: Application Health Check
  As a compliance officer
  I want to verify the AML Detector application loads correctly
  So that I can trust the system is operational

  Scenario: App loads successfully with all UI elements
    Given I open the AML Detector application
    Then I should see the page title "AML Autonomous Sentinel"
    And the sidebar should display "AML Detector"

  Scenario: API connectivity status is visible
    Given I open the AML Detector application
    Then the sidebar should show an API status indicator
    And the API status should show "API Online" or "API Offline"

  Scenario: Footer displays version information
    Given I open the AML Detector application
    Then the sidebar footer should display "AML Fraud Detection v1.0"
