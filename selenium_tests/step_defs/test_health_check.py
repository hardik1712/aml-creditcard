"""
Step definitions for the Application Health Check feature.

Tests that the AML Detector frontend loads correctly, displays
expected UI elements, and shows API connectivity status.
"""

import pytest
from pytest_bdd import scenarios, given, then, parsers
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Link this file to the Gherkin feature file
scenarios("../features/health_check.feature")


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------

@given("I open the AML Detector application")
def open_app(driver, base_url):
    """Navigate to the application root URL and wait for it to load."""
    driver.get(base_url)
    # Wait for the React app to mount (sidebar renders)
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.TAG_NAME, "aside"))
    )


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------

@then(parsers.parse('I should see the page title "{title}"'))
def verify_page_title(driver, title):
    """Verify the main heading text is visible on the page."""
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.TAG_NAME, "h1"))
    )
    h1 = driver.find_element(By.TAG_NAME, "h1")
    assert title in h1.text, f"Expected title '{title}' but got '{h1.text}'"


@then(parsers.parse('the sidebar should display "{text}"'))
def verify_sidebar_text(driver, text):
    """Verify the sidebar contains the expected text."""
    sidebar = driver.find_element(By.TAG_NAME, "aside")
    assert text in sidebar.text, (
        f"Expected '{text}' in sidebar but sidebar text is:\n{sidebar.text}"
    )


@then("the sidebar should show an API status indicator")
def verify_api_status_indicator(driver):
    """Verify the API status pill/dot is present in the sidebar."""
    sidebar = driver.find_element(By.TAG_NAME, "aside")
    # The status indicator is a small colored dot (span with rounded-full class)
    dots = sidebar.find_elements(By.CSS_SELECTOR, "span.rounded-full")
    assert len(dots) > 0, "No API status indicator dot found in sidebar"


@then(parsers.parse('the API status should show "{status1}" or "{status2}"'))
def verify_api_status_text(driver, status1, status2):
    """Verify the API status text shows one of the expected states."""
    sidebar = driver.find_element(By.TAG_NAME, "aside")
    # Wait a moment for the health check to complete
    WebDriverWait(driver, 10).until(
        lambda d: status1 in sidebar.text or status2 in sidebar.text
    )
    sidebar_text = sidebar.text
    assert status1 in sidebar_text or status2 in sidebar_text, (
        f"Expected '{status1}' or '{status2}' in sidebar, got:\n{sidebar_text}"
    )


@then(parsers.parse('the sidebar footer should display "{text}"'))
def verify_footer_text(driver, text):
    """Verify the sidebar footer shows version information."""
    sidebar = driver.find_element(By.TAG_NAME, "aside")
    assert text in sidebar.text, (
        f"Expected footer text '{text}' in sidebar but not found"
    )
