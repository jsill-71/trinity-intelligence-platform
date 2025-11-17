"""
ML Training Service - Automated machine learning model training
Trains predictive models on knowledge graph data for RCA optimization
"""

from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Optional
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import joblib
import os
from datetime import datetime
import json

app = FastAPI(title="Trinity ML Training Service")

MODELS_DIR = "/app/models"
os.makedirs(MODELS_DIR, exist_ok=True)

class TrainingData(BaseModel):
    features: List[List[float]]
    labels: List[int]
    model_type: str = "random_forest"
    test_size: float = 0.2

class PredictionRequest(BaseModel):
    model_id: str
    features: List[List[float]]

class ModelMetrics(BaseModel):
    accuracy: float
    precision: float
    recall: float
    f1_score: float

class TrainingJob(BaseModel):
    job_id: str
    model_type: str
    status: str
    metrics: Optional[ModelMetrics] = None
    created_at: str
    completed_at: Optional[str] = None

# In-memory training jobs
training_jobs = {}

def train_model(job_id: str, X_train, X_test, y_train, y_test, model_type: str):
    """Background training task"""

    try:
        training_jobs[job_id]["status"] = "training"

        # Select model
        if model_type == "random_forest":
            model = RandomForestClassifier(n_estimators=100, random_state=42)
        elif model_type == "gradient_boosting":
            model = GradientBoostingClassifier(n_estimators=100, random_state=42)
        else:
            training_jobs[job_id]["status"] = "failed"
            training_jobs[job_id]["error"] = f"Unknown model type: {model_type}"
            return

        # Train
        model.fit(X_train, y_train)

        # Evaluate
        y_pred = model.predict(X_test)

        metrics = {
            "accuracy": float(accuracy_score(y_test, y_pred)),
            "precision": float(precision_score(y_test, y_pred, average='weighted', zero_division=0)),
            "recall": float(recall_score(y_test, y_pred, average='weighted', zero_division=0)),
            "f1_score": float(f1_score(y_test, y_pred, average='weighted', zero_division=0))
        }

        # Save model
        model_path = os.path.join(MODELS_DIR, f"{job_id}.joblib")
        joblib.dump(model, model_path)

        # Save metadata
        metadata_path = os.path.join(MODELS_DIR, f"{job_id}_metadata.json")
        with open(metadata_path, 'w') as f:
            json.dump({
                "job_id": job_id,
                "model_type": model_type,
                "metrics": metrics,
                "trained_at": datetime.now().isoformat()
            }, f)

        # Update job
        training_jobs[job_id]["status"] = "completed"
        training_jobs[job_id]["metrics"] = metrics
        training_jobs[job_id]["completed_at"] = datetime.now().isoformat()

    except Exception as e:
        training_jobs[job_id]["status"] = "failed"
        training_jobs[job_id]["error"] = str(e)

@app.post("/train", response_model=TrainingJob)
async def train_ml_model(data: TrainingData, background_tasks: BackgroundTasks):
    """Start model training job"""

    job_id = f"model-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # Prepare data
    X = np.array(data.features)
    y = np.array(data.labels)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=data.test_size, random_state=42
    )

    # Create job
    training_jobs[job_id] = {
        "job_id": job_id,
        "model_type": data.model_type,
        "status": "queued",
        "created_at": datetime.now().isoformat(),
        "metrics": None,
        "completed_at": None
    }

    # Start background training
    background_tasks.add_task(
        train_model, job_id, X_train, X_test, y_train, y_test, data.model_type
    )

    return TrainingJob(**training_jobs[job_id])

@app.get("/jobs/{job_id}", response_model=TrainingJob)
async def get_training_job(job_id: str):
    """Get training job status"""

    if job_id not in training_jobs:
        return {"error": "Job not found"}, 404

    return TrainingJob(**training_jobs[job_id])

@app.post("/predict")
async def predict(request: PredictionRequest):
    """Make predictions using trained model"""

    model_path = os.path.join(MODELS_DIR, f"{request.model_id}.joblib")

    if not os.path.exists(model_path):
        return {"error": "Model not found"}, 404

    # Load model
    model = joblib.load(model_path)

    # Predict
    X = np.array(request.features)
    predictions = model.predict(X)
    probabilities = model.predict_proba(X) if hasattr(model, 'predict_proba') else None

    return {
        "model_id": request.model_id,
        "predictions": predictions.tolist(),
        "probabilities": probabilities.tolist() if probabilities is not None else None
    }

@app.get("/models")
async def list_models():
    """List all trained models"""

    models = []

    for filename in os.listdir(MODELS_DIR):
        if filename.endswith("_metadata.json"):
            with open(os.path.join(MODELS_DIR, filename), 'r') as f:
                models.append(json.load(f))

    return {"models": models}

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "models_count": len([f for f in os.listdir(MODELS_DIR) if f.endswith('.joblib')])
    }
