Feature: Page Navigation
  As a user of the AML Detector application
  I want to navigate between different pages using the sidebar
  So that I can access all features of the system

  Scenario: Navigate to Agentic Pipeline page
    Given I open the AML Detector application
    When I click on "Agentic Pipeline" in the sidebar
    Then the "Agentic Pipeline" sidebar item should be active

  Scenario: Navigate to Compliance Copilot page
    Given I open the AML Detector application
    When I click on "Compliance Copilot" in the sidebar
    Then the "Compliance Copilot" sidebar item should be active

  Scenario: Navigate to Overview & KPIs page
    Given I open the AML Detector application
    When I click on "Overview & KPIs" in the sidebar
    Then the "Overview & KPIs" sidebar item should be active

  Scenario: Navigate to Batch File Ingestion page
    Given I open the AML Detector application
    When I click on "Batch File Ingestion" in the sidebar
    Then the "Batch File Ingestion" sidebar item should be active

  Scenario: Navigate to Transaction Scorer page
    Given I open the AML Detector application
    When I click on "Transaction Scorer" in the sidebar
    Then the "Transaction Scorer" sidebar item should be active

  Scenario: Sidebar highlights the active page
    Given I open the AML Detector application
    When I click on "Transaction Scorer" in the sidebar
    Then the "Transaction Scorer" sidebar item should be active
    When I click on "Agentic Pipeline" in the sidebar
    Then the "Agentic Pipeline" sidebar item should be active
    And the "Transaction Scorer" sidebar item should not be active
