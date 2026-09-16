Feature: Transaction Scoring
  As a fraud analyst
  I want to score transactions through the UI
  So that I can identify potentially fraudulent activity

  Scenario: Score a high-risk transfer transaction
    Given I navigate to the Transaction Scorer page
    When I fill in the transaction form with:
      | field           | value        |
      | step            | 12           |
      | type            | TRANSFER     |
      | amount          | 181920.00    |
      | nameOrig        | C1231006815  |
      | oldbalanceOrg   | 181920.00    |
      | newbalanceOrig  | 0.00         |
      | nameDest        | M1979787155  |
      | oldbalanceDest  | 0.00         |
      | newbalanceDest  | 0.00         |
    And I click the Score Transaction button
    Then I should see the Prediction Result section
    And the fraud probability should be displayed
    And a risk tier badge should be visible

  Scenario: Score a low-risk payment transaction
    Given I navigate to the Transaction Scorer page
    When I fill in the transaction form with:
      | field           | value        |
      | step            | 14           |
      | type            | PAYMENT      |
      | amount          | 42.50        |
      | nameOrig        | C9988776655  |
      | oldbalanceOrg   | 500.00       |
      | newbalanceOrig  | 457.50       |
      | nameDest        | M1122334455  |
      | oldbalanceDest  | 0.00         |
      | newbalanceDest  | 0.00         |
    And I click the Score Transaction button
    Then I should see the Prediction Result section
    And the fraud probability should be displayed

  Scenario: Default form values are pre-populated
    Given I navigate to the Transaction Scorer page
    Then the transaction form should have default values filled in
    And the Score Transaction button should be enabled
