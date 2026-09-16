"""
Step definitions for the Transaction Scoring feature.

Tests the Scorer page: filling the transaction form, submitting it,
and verifying prediction results appear with correct elements.
"""

import pytest
from pytest_bdd import scenarios, given, when, then, parsers
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

# Link this file to the Gherkin feature file
scenarios("../features/transaction_scorer.feature")


# ---------------------------------------------------------------------------
# Field mapping: Gherkin table field → form input matching strategy
# ---------------------------------------------------------------------------

# Maps the Gherkin datatable field names to how we locate and fill them.
# The Scorer page uses floating-label inputs. We identify them by label text.
FIELD_LABELS = {
    "step": "Step (hour)",
    "type": "Transaction Type",
    "amount": "Amount ($)",
    "nameOrig": "Originator Account",
    "oldbalanceOrg": "Old Balance (Orig)",
    "newbalanceOrig": "New Balance (Orig)",
    "nameDest": "Destination Account",
    "oldbalanceDest": "Old Balance (Dest)",
    "newbalanceDest": "New Balance (Dest)",
}


def _find_input_by_label(driver, label_text):
    """Find an input/select element by its associated floating label text."""
    # Find the label element
    labels = driver.find_elements(By.CSS_SELECTOR, "label.floating-label")
    for label in labels:
        if label.text.strip() == label_text:
            # The input is a sibling within the same .input-wrapper parent
            wrapper = label.find_element(By.XPATH, "..")
            inputs = wrapper.find_elements(By.CSS_SELECTOR, "input, select")
            if inputs:
                return inputs[0]
    return None


def _fill_field(driver, field_name, value):
    """Fill a form field identified by its Gherkin table name."""
    label_text = FIELD_LABELS.get(field_name)
    if not label_text:
        raise ValueError(f"Unknown field name: {field_name}")

    element = _find_input_by_label(driver, label_text)
    if not element:
        raise AssertionError(f"Could not find input for label '{label_text}'")

    tag = element.tag_name.lower()

    if tag == "select":
        select = Select(element)
        select.select_by_value(value)
    else:
        element.clear()
        element.send_keys(value)


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------

@given("I navigate to the Transaction Scorer page")
def navigate_to_scorer(driver, base_url):
    """Open the app and click on Transaction Scorer in the sidebar."""
    driver.get(base_url)
    # Wait for sidebar to load
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.TAG_NAME, "aside"))
    )
    # Click on "Transaction Scorer" in the sidebar nav
    sidebar = driver.find_element(By.TAG_NAME, "aside")
    buttons = sidebar.find_elements(By.TAG_NAME, "button")
    for btn in buttons:
        if "Transaction Scorer" in btn.text:
            btn.click()
            break
    # Wait for the scorer form to appear
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.TAG_NAME, "form"))
    )


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------

@when(parsers.parse("I fill in the transaction form with:\n{table}"))
def fill_transaction_form(driver, table):
    """Fill the transaction form using values from the Gherkin datatable.

    The datatable has two columns: field and value.
    """
    for line in table.strip().split("\n"):
        # Skip the header row
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if len(parts) == 2 and parts[0] != "field":
            field_name, value = parts
            _fill_field(driver, field_name, value)


@when("I click the Score Transaction button")
def click_score_button(driver):
    """Click the Score Transaction submit button."""
    # Find the submit button by its text content
    buttons = driver.find_elements(By.TAG_NAME, "button")
    score_btn = None
    for btn in buttons:
        if "Score Transaction" in btn.text or "Scoring" in btn.text:
            score_btn = btn
            break

    assert score_btn is not None, "Score Transaction button not found"
    score_btn.click()

    # Wait for the result to appear (the loading spinner to finish)
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located(
            (By.XPATH, "//*[contains(text(), 'Prediction Result')]")
        )
    )


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------

@then("I should see the Prediction Result section")
def verify_prediction_result(driver):
    """Verify that the prediction result card is visible."""
    result = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located(
            (By.XPATH, "//*[contains(text(), 'Prediction Result')]")
        )
    )
    assert result.is_displayed(), "Prediction Result section is not visible"


@then("the fraud probability should be displayed")
def verify_fraud_probability(driver):
    """Verify that a fraud probability value is shown."""
    # The probability is displayed with a % suffix
    prob_element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located(
            (By.XPATH, "//*[contains(text(), 'Fraud Probability')]")
        )
    )
    assert prob_element.is_displayed(), "Fraud Probability label not visible"


@then("a risk tier badge should be visible")
def verify_risk_tier(driver):
    """Verify that a risk tier badge (LOW/MEDIUM/HIGH/CRITICAL) is shown."""
    tier_label = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located(
            (By.XPATH, "//*[contains(text(), 'Risk Tier')]")
        )
    )
    assert tier_label.is_displayed(), "Risk Tier label not visible"

    # Check that one of the tier values is present
    page_text = driver.find_element(By.TAG_NAME, "body").text
    valid_tiers = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    found_tier = any(tier in page_text for tier in valid_tiers)
    assert found_tier, f"No valid risk tier found in page text"


@then("the transaction form should have default values filled in")
def verify_default_values(driver):
    """Verify the form has pre-populated default values."""
    # Check that the amount field has a value
    amount_input = _find_input_by_label(driver, "Amount ($)")
    assert amount_input is not None, "Amount field not found"
    value = amount_input.get_attribute("value")
    assert value and float(value) > 0, f"Amount field should have a default value, got: '{value}'"


@then("the Score Transaction button should be enabled")
def verify_button_enabled(driver):
    """Verify the submit button is not disabled."""
    buttons = driver.find_elements(By.TAG_NAME, "button")
    for btn in buttons:
        if "Score Transaction" in btn.text:
            assert btn.is_enabled(), "Score Transaction button is disabled"
            return
    pytest.fail("Score Transaction button not found")
