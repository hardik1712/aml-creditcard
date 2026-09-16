"""
Pytest configuration and fixtures for Selenium BDD tests.

Provides:
    - Chrome WebDriver setup (headless by default, override with --headed)
    - Live server URL constant
    - Automatic screenshot capture on test failure
"""

import os
import pytest
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

try:
    from webdriver_manager.chrome import ChromeDriverManager
    HAS_WEBDRIVER_MANAGER = True
except ImportError:
    HAS_WEBDRIVER_MANAGER = False


# Directory for failure screenshots
SCREENSHOTS_DIR = Path(__file__).parent / "screenshots"


def pytest_addoption(parser):
    """Add custom CLI options for Selenium tests."""
    parser.addoption(
        "--headed",
        action="store_true",
        default=False,
        help="Run browser in headed (visible) mode instead of headless.",
    )
    parser.addoption(
        "--base-url",
        action="store",
        default="http://localhost:5173",
        help="Base URL for the frontend application.",
    )


@pytest.fixture(scope="session")
def base_url(request):
    """Base URL for the live frontend server."""
    return request.config.getoption("--base-url")


@pytest.fixture(scope="session")
def driver(request):
    """Create a Chrome WebDriver instance for the test session.

    Uses headless mode by default for CI environments.
    Pass --headed to see the browser during test execution.

    The WebDriver is shared across all tests in a session for performance.
    """
    chrome_options = Options()

    if not request.config.getoption("--headed"):
        chrome_options.add_argument("--headless=new")

    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")

    # Use webdriver-manager to auto-install matching ChromeDriver
    if HAS_WEBDRIVER_MANAGER:
        service = Service(ChromeDriverManager().install())
        browser = webdriver.Chrome(service=service, options=chrome_options)
    else:
        # Fallback: assume chromedriver is on PATH
        browser = webdriver.Chrome(options=chrome_options)

    browser.implicitly_wait(5)

    yield browser

    browser.quit()


@pytest.fixture(autouse=True)
def _screenshot_on_failure(request, driver):
    """Automatically capture a screenshot when a test fails.

    Screenshots are saved to selenium_tests/screenshots/ with the test name
    and a timestamp for easy debugging.
    """
    yield

    # After the test, check if it failed
    if request.node.rep_call and request.node.rep_call.failed:
        SCREENSHOTS_DIR.mkdir(exist_ok=True)
        test_name = request.node.name.replace("[", "_").replace("]", "_")
        screenshot_path = SCREENSHOTS_DIR / f"FAIL_{test_name}.png"
        driver.save_screenshot(str(screenshot_path))
        print(f"\n📸 Screenshot saved: {screenshot_path}")


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Store test outcome on the item for the screenshot fixture."""
    import pluggy

    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)
