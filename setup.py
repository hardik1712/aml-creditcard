"""Minimal setup.py to make src/aml_detector installable as a package.

Usage:
    pip install -e .

This lets you import aml_detector from anywhere in the project:
    from aml_detector.data_loader import load_paysim
"""

from setuptools import setup, find_packages

setup(
    name="aml-detector",
    version="0.1.0",
    description="Anti-Money Laundering fraud detection on PaySim data",
    author="Hardi",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.10",
)
