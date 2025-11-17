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
import asyncpg
import uuid

app = FastAPI(title="Trinity ML Training Service")

MODELS_DIR = "/app/models"
POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://trinity:trinity@postgres:5432/trinity")

os.makedirs(MODELS_DIR, exist_ok=True)

pool = None

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

@app.on_event("startup")
async def startup():
    global pool
    pool = await asyncpg.create_pool(POSTGRES_URL, min_size=2, max_size=10)

    # Create training_jobs table
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS training_jobs (
                id SERIAL PRIMARY KEY,
                job_id VARCHAR(100) UNIQUE NOT NULL,
                model_type VARCHAR(50) NOT NULL,
                status VARCHAR(50) NOT NULL,
                metrics JSONB,
                error TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                completed_at TIMESTAMP
            )
        """)

@app.on_event("shutdown")
async def shutdown():
    if pool:
        await pool.close()

async def train_model(job_id: str, X_train, X_test, y_train, y_test, model_type: str):
    """Background training task"""

    try:
        # Update status to training
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE training_jobs
                SET status = 'training'
                WHERE job_id = $1
            """, job_id)

        # Select model
        if model_type == "random_forest":
            model = RandomForestClassifier(n_estimators=100, random_state=42)
        elif model_type == "gradient_boosting":
            model = GradientBoostingClassifier(n_estimators=100, random_state=42)
        else:
            async with pool.acquire() as conn:
                await conn.execute("""
                    UPDATE training_jobs
                    SET status = 'failed',
                        error = $1,
                        completed_at = NOW()
                    WHERE job_id = $2
                """, f"Unknown model type: {model_type}", job_id)
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

        # Update job in database
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE training_jobs
                SET status = 'completed',
                    metrics = $1,
                    completed_at = NOW()
                WHERE job_id = $2
            """, json.dumps(metrics), job_id)

    except Exception as e:
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE training_jobs
                SET status = 'failed',
                    error = $1,
                    completed_at = NOW()
                WHERE job_id = $2
            """, str(e), job_id)

@app.post("/train", response_model=TrainingJob)
async def train_ml_model(data: TrainingData, background_tasks: BackgroundTasks):
    """Start model training job"""

    # Use UUID to prevent timestamp collisions
    job_id = f"model-{uuid.uuid4().hex[:12]}"

    # Prepare data
    X = np.array(data.features)
    y = np.array(data.labels)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=data.test_size, random_state=42
    )

    # Create job in database
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO training_jobs (job_id, model_type, status)
            VALUES ($1, $2, 'queued')
        """, job_id, data.model_type)

    # Start background training
    background_tasks.add_task(
        train_model, job_id, X_train, X_test, y_train, y_test, data.model_type
    )

    return TrainingJob(
        job_id=job_id,
        model_type=data.model_type,
        status="queued",
        created_at=datetime.now().isoformat(),
        metrics=None,
        completed_at=None
    )

@app.get("/jobs/{job_id}", response_model=TrainingJob)
async def get_training_job(job_id: str):
    """Get training job status"""

    async with pool.acquire() as conn:
        job = await conn.fetchrow("""
            SELECT job_id, model_type, status, metrics, error, created_at, completed_at
            FROM training_jobs
            WHERE job_id = $1
        """, job_id)

    if not job:
        return {"error": "Job not found"}, 404

    return TrainingJob(
        job_id=job["job_id"],
        model_type=job["model_type"],
        status=job["status"],
        metrics=ModelMetrics(**json.loads(job["metrics"])) if job["metrics"] else None,
        created_at=job["created_at"].isoformat(),
        completed_at=job["completed_at"].isoformat() if job["completed_at"] else None
    )

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
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {
            "status": "healthy",
            "database": "connected",
            "models_count": len([f for f in os.listdir(MODELS_DIR) if f.endswith('.joblib')])
        }
    except:
        return {
            "status": "degraded",
            "database": "disconnected",
            "models_count": len([f for f in os.listdir(MODELS_DIR) if f.endswith('.joblib')])
        }
