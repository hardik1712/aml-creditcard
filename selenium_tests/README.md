# Selenium BDD Tests — AML Fraud Detection

Automated browser tests for the AML Detector React frontend using
**Selenium WebDriver** + **pytest-bdd** (BDD/Gherkin syntax).

## Prerequisites

1. **Google Chrome** browser installed
2. Python dependencies installed:
   ```bash
   pip install selenium pytest-bdd webdriver-manager
   ```
3. **Both servers running** (FastAPI backend + Vite frontend):
   ```bash
   python scripts/run_app.py
   ```

## Running Tests

```bash
# Run all Selenium BDD tests (headless — no browser window)
pytest selenium_tests/ -v

# Run with visible browser window (useful for debugging)
pytest selenium_tests/ -v --headed

# Run a specific feature
pytest selenium_tests/step_defs/test_health_check.py -v
pytest selenium_tests/step_defs/test_navigation.py -v
pytest selenium_tests/step_defs/test_transaction_scorer.py -v

# Run against a different URL (e.g., production build)
pytest selenium_tests/ -v --base-url http://localhost:8000
```

## Test Structure

```
selenium_tests/
├── conftest.py                         # WebDriver fixtures, screenshot-on-failure
├── features/                           # Gherkin .feature files (BDD scenarios)
│   ├── health_check.feature            # App loading & sidebar verification
│   ├── navigation.feature              # Sidebar page navigation
│   └── transaction_scorer.feature      # Form submission & result validation
├── step_defs/                          # Python step implementations
│   ├── test_health_check.py            # Given/Then for health checks
│   ├── test_navigation.py              # When/Then for navigation
│   └── test_transaction_scorer.py      # When/Then for scoring
├── screenshots/                        # Auto-captured on test failure
└── README.md                           # This file
```

## BDD Feature Files

Feature files use **Gherkin syntax** — a human-readable format for
specifying test scenarios:

```gherkin
Feature: Transaction Scoring
  Scenario: Score a high-risk transfer
    Given I navigate to the Transaction Scorer page
    When I enter a TRANSFER of $181,920
    And I click the Score Transaction button
    Then I should see the Prediction Result section
    And the risk tier should be displayed
```

Each `Given/When/Then` step maps to a Python function in `step_defs/`.

## Failure Screenshots

When a test fails, a screenshot is automatically saved to
`selenium_tests/screenshots/` with the test name. This makes it easy
to debug UI issues in CI environments where you can't see the browser.

## CI/CD Integration

For GitHub Actions or similar CI:

```yaml
- name: Run Selenium tests
  run: |
    # Start the app in background
    python scripts/run_app.py &
    sleep 10  # Wait for servers to start
    pytest selenium_tests/ -v --tb=short
```
