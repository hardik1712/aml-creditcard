# 🛡️ AML Fraud Detection Web App

A modern, unified web application for real-time monitoring and analysis of transaction fraud risk. This project uses a highly optimized LightGBM model trained on the PaySim dataset to identify illicit transactions. 

The application is built with a **FastAPI** backend that engineers velocity and graph-based features on the fly, and serves a **custom Vanilla JS/CSS** frontend featuring a premium glassmorphism design, real-time KPI counters, and interactive scoring results.

---

## ✨ Features

- **Real-Time Scoring**: Submit transaction details via the UI and receive instant fraud probability predictions.
- **Risk Tiering**: Transactions are classified into dynamic risk tiers (LOW, MEDIUM, HIGH, CRITICAL) based on model thresholds.
- **Advanced Feature Engineering**: Implements complex historical velocity and degree-ratio features for originator/destination accounts.
- **Unified Architecture**: The FastAPI server directly serves the interactive frontend (`index.html`, `style.css`, `app.js`), meaning no separate frontend dev server is required.
- **Premium Aesthetics**: Features a fully responsive UI with smooth micro-animations, staggered loaders, dynamic gradients, and modern toast notifications.

## 📁 Project Structure

```
aml-creditcard/
├── frontend/                 # Static UI assets served by FastAPI
│   ├── index.html            # Main HTML layout
│   ├── style.css             # Glassmorphism and animations
│   └── app.js                # Frontend logic & API integration
├── src/aml_detector/         # Core Python package
│   ├── api.py                # FastAPI endpoints & static file routing
│   ├── config.py             # Project configurations & thresholds
│   ├── data_loader.py        # Dataset downloading and caching
│   ├── eda.py                # Exploratory Data Analysis utilities
│   ├── features.py           # Feature engineering pipeline
│   ├── graph.py              # Graph-based feature calculations
│   ├── models.py             # LightGBM training & prediction wrapper
│   └── schemas.py            # Pydantic models for API validation
├── scripts/                  # CLI execution scripts
│   ├── run_app.py            # Entrypoint to run the unified web app
│   ├── run_api.py            # Entrypoint for uvicorn server
│   ├── run_modeling.py       # Script to train the LightGBM model
│   └── run_eda.py            # Script to generate EDA reports
├── tests/                    # Pytest suite
└── data/                     # Raw and processed datasets (ignored in git)
```

## 🚀 Getting Started

### 1. Prerequisites
Ensure you have Python 3.10+ installed. 

### 2. Installation
Clone the repository and set up a virtual environment:

```bash
git clone https://github.com/hardik1712/aml-creditcard.git
cd aml-creditcard

# Create and activate virtual environment (Windows)
python -m venv venv
.\venv\Scripts\activate

# Install dependencies and the local package
pip install -r requirements.txt
python setup.py install
```

### 3. Running the Application

To launch the unified frontend and backend, simply run:

```bash
python scripts/run_app.py
```

The application will start on **`http://127.0.0.1:8000/`**. 

- **UI Dashboard**: `http://127.0.0.1:8000/`
- **Interactive API Docs (Swagger UI)**: `http://127.0.0.1:8000/docs`

### 4. Running Tests
To verify the installation and core logic, run the test suite:
```bash
pytest tests/ -v
```

## 🧠 Model Pipeline

If you wish to retrain the model on new data:
1. Ensure the raw dataset is available (the `run_modeling.py` script will automatically download the PaySim dataset from Kaggle if missing).
2. Run `python scripts/run_modeling.py`. This script will:
   - Load and clean the data.
   - Engineer graph and velocity features.
   - Train a LightGBM model with early stopping.
   - Save the model artifact to `models/model.joblib`.
   - Export evaluation metrics to `outputs/model_metrics.json`.

---
*Built as part of an advanced agentic coding exploration.*
