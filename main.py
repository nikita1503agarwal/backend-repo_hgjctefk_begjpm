import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from bson.objectid import ObjectId

from database import db, create_document, get_documents
from schemas import Workout

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Workout Planner API"}

# Helper to convert Mongo document to JSON-friendly dict

def serialize_doc(doc: dict):
    if not doc:
        return doc
    doc = dict(doc)
    _id = doc.get("_id")
    if isinstance(_id, ObjectId):
        doc["id"] = str(_id)
        del doc["_id"]
    return doc

@app.get("/api/workouts", response_model=List[dict])
def list_workouts(day: Optional[str] = None):
    try:
        filter_q = {"day": day} if day else {}
        docs = get_documents("workout", filter_q)
        return [serialize_doc(d) for d in docs]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/workouts", status_code=201)
def create_workout(item: Workout):
    try:
        inserted_id = create_document("workout", item)
        # Return the created object with id
        created = db["workout"].find_one({"_id": ObjectId(inserted_id)})
        return serialize_doc(created)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class UpdateWorkout(BaseModel):
    title: Optional[str] = None
    sets: Optional[int] = None
    reps: Optional[int] = None
    day: Optional[str] = None
    notes: Optional[str] = None
    completed: Optional[bool] = None

@app.patch("/api/workouts/{workout_id}")
def update_workout(workout_id: str, payload: UpdateWorkout):
    try:
        update_data = {k: v for k, v in payload.model_dump(exclude_unset=True).items()}
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        update_data["updated_at"] = db.command({"serverStatus": 1}).get("localTime") if db else None
        res = db["workout"].update_one({"_id": ObjectId(workout_id)}, {"$set": update_data})
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Workout not found")
        updated = db["workout"].find_one({"_id": ObjectId(workout_id)})
        return serialize_doc(updated)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/workouts/{workout_id}", status_code=204)
def delete_workout(workout_id: str):
    try:
        res = db["workout"].delete_one({"_id": ObjectId(workout_id)})
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Workout not found")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        from database import db
        
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
