"""
Step definitions for the Page Navigation feature.

Tests sidebar navigation between all pages and verifies
active state highlighting in the sidebar.
"""

import pytest
from pytest_bdd import scenarios, given, when, then, parsers
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Link this file to the Gherkin feature file
scenarios("../features/navigation.feature")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _find_sidebar_button(driver, page_name):
    """Find a sidebar navigation button by its visible text label."""
    sidebar = driver.find_element(By.TAG_NAME, "aside")
    buttons = sidebar.find_elements(By.TAG_NAME, "button")
    for btn in buttons:
        if page_name in btn.text:
            return btn
    return None


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------

@given("I open the AML Detector application")
def open_app(driver, base_url):
    """Navigate to the application root URL and wait for it to load."""
    driver.get(base_url)
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.TAG_NAME, "aside"))
    )


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------

@when(parsers.parse('I click on "{page_name}" in the sidebar'))
def click_sidebar_nav(driver, page_name):
    """Click a navigation item in the sidebar."""
    btn = _find_sidebar_button(driver, page_name)
    assert btn is not None, f"Sidebar button '{page_name}' not found"
    btn.click()

    # Brief wait for the page transition animation
    import time
    time.sleep(0.5)


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------

@then(parsers.parse('the "{page_name}" sidebar item should be active'))
def verify_active_sidebar(driver, page_name):
    """Verify the sidebar item has the active visual state.

    The active state is indicated by the CSS class 'border-violet-500'
    (a left border highlight) applied in Sidebar.jsx.
    """
    btn = _find_sidebar_button(driver, page_name)
    assert btn is not None, f"Sidebar button '{page_name}' not found"

    classes = btn.get_attribute("class") or ""
    # The active button has: bg-white/10, border-l-4, border-violet-500
    assert "border-violet-500" in classes or "bg-white/10" in classes, (
        f"Expected '{page_name}' sidebar item to be active.\n"
        f"Button classes: {classes}"
    )


@then(parsers.parse('the "{page_name}" sidebar item should not be active'))
def verify_inactive_sidebar(driver, page_name):
    """Verify the sidebar item does NOT have the active visual state."""
    btn = _find_sidebar_button(driver, page_name)
    assert btn is not None, f"Sidebar button '{page_name}' not found"

    classes = btn.get_attribute("class") or ""
    # The inactive button should NOT have the active border
    assert "border-violet-500" not in classes, (
        f"Expected '{page_name}' sidebar item to be INACTIVE but it has active classes.\n"
        f"Button classes: {classes}"
    )
