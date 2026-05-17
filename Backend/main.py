import os
import sys
import uuid
import shutil
import certifi
import bcrypt
import jwt
import requests
import uvicorn
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
from pymongo import MongoClient

# Determine the base directory for file paths (Fix #8 - CWD independence)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load configuration from environment or config file
try:
    from config import (
        MONGO_CONNECTION_STRING,
        JWT_SECRET,
        JWT_EXPIRATION_DAYS,
        ALLOWED_ORIGINS,
        AUTH_SERVER_PORT,
        AI_BACKEND_URL,
        BASE_URL
    )
except ImportError:
    # Fallback if config.py doesn't exist
    MONGO_CONNECTION_STRING = os.getenv(
        "MONGO_CONNECTION_STRING",
        "mongodb+srv://admin:admin123@cluster0.fzt0yhs.mongodb.net/?appName=Cluster0"
    )
    JWT_SECRET = os.getenv("JWT_SECRET", "super_secret_jwt_key_12345")
    JWT_EXPIRATION_DAYS = int(os.getenv("JWT_EXPIRATION_DAYS", "7"))
    ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
    AUTH_SERVER_PORT = int(os.getenv("AUTH_SERVER_PORT", "8001"))
    AI_BACKEND_URL = os.getenv("AI_BACKEND_URL", "http://localhost:8000")
    BASE_URL = os.getenv("BASE_URL", "http://localhost:8001")

# Warn if using weak JWT secret
if len(JWT_SECRET) < 32:
    print("⚠️  WARNING: JWT_SECRET is too weak! Use at least 32 characters for production.")

app = FastAPI(title="GRWM Auth & Profile Server")

# BUG FIX #13 - Standardized CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Fix #8 - Use absolute paths for file system operations
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "detected_items"), exist_ok=True)

# Serve uploaded files (profile pictures, clothing uploads)
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")
# Fix #5 - Also serve static/detected_items from app.py so frontend can access wardrobe images via port 8001
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

client = MongoClient(MONGO_CONNECTION_STRING, tlsCAFile=certifi.where())
db = client["stylist_engine"]
users_collection = db["users"]

class UserRegister(BaseModel):
    username: str
    password: str

class SuggestionReq(BaseModel):
    prompt: str
    skin_tone: Optional[str] = "#e0ac69"
    body_shape: Optional[str] = "rectangular"

class WardrobeUpdateReq(BaseModel):
    category: str
    formality: str
    fit: str

# BUG FIX #7 - Improved error handling and authorization validation
def verify_token(authorization: str):
    """Verify JWT token and return userID"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid or missing token")
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired. Please login again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        raise HTTPException(status_code=401, detail="Token validation failed")

# ==========================================
# AUTHENTICATION & ONBOARDING
# ==========================================

@app.post("/api/register")
def register(user: UserRegister):
    # BUG FIX - Input validation for username and password length
    if not user.username or len(user.username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if not user.password or len(user.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    
    if users_collection.find_one({"username": user.username}):
        raise HTTPException(status_code=400, detail="Username already exists")
    
    hashed = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt())
    user_id = str(uuid.uuid4())
    
    # Initialize empty profile fields and onboarding status
    users_collection.insert_one({
        "userID": user_id,
        "username": user.username,
        "password": hashed,
        "is_onboarded": False,
        "body_shape": None,
        "skin_tone": None,
        "profile_picture_url": None
    })
    
    token = jwt.encode(
        {"sub": user_id, "exp": datetime.utcnow() + timedelta(days=JWT_EXPIRATION_DAYS)},
        JWT_SECRET,
        algorithm="HS256"
    )
    
    return {
        "success": True, 
        "token": token, 
        "userID": user_id,
        "username": user.username,
        "is_onboarded": False
    }

@app.post("/api/login")
def login(user: UserRegister):
    db_user = users_collection.find_one({"username": user.username})
    if not db_user or not bcrypt.checkpw(user.password.encode('utf-8'), db_user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = jwt.encode(
        {"sub": db_user["userID"], "exp": datetime.utcnow() + timedelta(days=JWT_EXPIRATION_DAYS)},
        JWT_SECRET,
        algorithm="HS256"
    )
    
    # Return all profile data on login
    return {
        "token": token, 
        "userID": db_user["userID"],
        "username": db_user["username"],
        "is_onboarded": db_user.get("is_onboarded", False),
        "body_shape": db_user.get("body_shape"),
        "skin_tone": db_user.get("skin_tone"),
        "profile_picture_url": db_user.get("profile_picture_url")
    }

# ==========================================
# USER PROFILE MANAGEMENT
# ==========================================

@app.get("/api/profile")
def get_profile(authorization: str = Header(None)):
    """Get current user's profile (BUG FIX #8 - Authorization validation)"""
    user_id = verify_token(authorization)
    db_user = users_collection.find_one(
        {"userID": user_id},
        {"_id": 0, "password": 0}
    )
    
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Only return the requested user's own profile (multi-user security)
    return db_user

@app.post("/api/profile")
def update_profile(
    authorization: str = Header(None),
    body_shape: str = Form(None),
    skin_tone: str = Form(None),
    profile_picture: UploadFile = File(None)
):
    """Update current user's profile"""
    user_id = verify_token(authorization)
    update_data = {"is_onboarded": True}
    
    if body_shape:
        update_data["body_shape"] = body_shape
    if skin_tone:
        update_data["skin_tone"] = skin_tone
        
    # Handle Profile Picture Upload with validation (BUG FIX #14)
    if profile_picture:
        # Validate file type
        allowed_types = {'image/jpeg', 'image/png', 'image/webp'}
        if profile_picture.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail="Only JPEG, PNG, or WebP images are allowed")
        
        # Validate file size (max 5MB)
        file_content = profile_picture.file.read()
        file_size = len(file_content)
        if file_size > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File size must be less than 5MB")
        
        file_ext = profile_picture.filename.split(".")[-1]
        file_name = f"profile_{user_id}.{file_ext}"
        file_path = os.path.join(UPLOADS_DIR, file_name)
        
        with open(file_path, "wb") as buffer:
            buffer.write(file_content)
            
        update_data["profile_picture_url"] = f"{BASE_URL}/uploads/{file_name}"
        
    # Update the database
    users_collection.update_one(
        {"userID": user_id},
        {"$set": update_data}
    )
    
    # Return the updated profile
    updated_user = users_collection.find_one({"userID": user_id}, {"_id": 0, "password": 0})
    return updated_user


# ==========================================
# AI ENGINE PROXIES
# ==========================================

@app.post("/api/upload")
def upload_image(authorization: str = Header(None), file: UploadFile = File(...)):
    """Upload clothing item image"""
    user_id = verify_token(authorization)
    
    # Use absolute path for file storage (Fix #8)
    file_path = os.path.join(UPLOADS_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    image_link = f"{BASE_URL}/uploads/{file.filename}"
    
    resp = requests.post(f"{AI_BACKEND_URL}/api/upload", json={
        "userID": user_id,
        "image_link": image_link,
        "local_path": file_path
    })
    
    if resp.status_code != 200:
        error_detail = resp.json().get("detail", resp.json()) if isinstance(resp.json(), dict) else resp.json()
        raise HTTPException(status_code=resp.status_code, detail=error_detail)
        
    return resp.json()

@app.get("/api/wardrobe")
def get_wardrobe(authorization: str = Header(None)):
    """Get current user's wardrobe"""
    user_id = verify_token(authorization)
    
    resp = requests.get(f"{AI_BACKEND_URL}/api/wardrobe/{user_id}")
    
    # Fix #7 - Handle empty wardrobe gracefully (return empty array instead of 404)
    if resp.status_code == 404:
        return []
    
    if resp.status_code != 200:
        error_detail = resp.json().get("detail", resp.json()) if isinstance(resp.json(), dict) else resp.json()
        raise HTTPException(status_code=resp.status_code, detail=error_detail)
        
    return resp.json()

# BUG FIX #3 - Delete endpoint for wardrobe items
@app.delete("/api/wardrobe/{item_id}")
def delete_wardrobe_item(item_id: str, authorization: str = Header(None)):
    """Delete a clothing item from user's wardrobe"""
    user_id = verify_token(authorization)
    
    # Fix: Pass userID as query parameter for validation
    resp = requests.delete(
        f"{AI_BACKEND_URL}/api/wardrobe/{item_id}",
        params={"userID": user_id}
    )
    
    if resp.status_code != 200:
        raise HTTPException(
            status_code=resp.status_code,
            detail=resp.json().get("detail", "Failed to delete item")
        )
    
    return resp.json()

@app.post("/api/suggest")
def suggest(req: SuggestionReq, authorization: str = Header(None)):
    """Get outfit suggestion"""
    user_id = verify_token(authorization)
    
    # Fetch skin_tone and body_shape from DB if not provided
    user_profile = users_collection.find_one({"userID": user_id})
    if not user_profile:
        raise HTTPException(status_code=404, detail="User profile not found")
    
    final_skin_tone = req.skin_tone or user_profile.get("skin_tone", "#e0ac69")
    final_body_shape = req.body_shape or user_profile.get("body_shape", "rectangular")
    
    resp = requests.post(f"{AI_BACKEND_URL}/api/suggest", json={
        "userID": user_id,
        "prompt": req.prompt,
        "skin_tone": final_skin_tone,
        "body_shape": final_body_shape
    })
    
    if resp.status_code != 200:
        error_detail = resp.json().get("detail", resp.json()) if isinstance(resp.json(), dict) else resp.json()
        raise HTTPException(status_code=resp.status_code, detail=error_detail)
        
    return resp.json()

@app.put("/api/wardrobe/{item_id}")
def update_wardrobe_item(item_id: str, req: WardrobeUpdateReq, authorization: str = Header(None)):
    """Update a clothing item's parameters"""
    user_id = verify_token(authorization)
    
    resp = requests.put(
        f"{AI_BACKEND_URL}/api/wardrobe/{item_id}",
        json={"userID": user_id, "category": req.category, "formality": req.formality, "fit": req.fit}
    )
    
    if resp.status_code != 200:
        error_detail = resp.json().get("detail", resp.json()) if isinstance(resp.json(), dict) else resp.json()
        raise HTTPException(status_code=resp.status_code, detail=error_detail)
    return resp.json()

@app.get("/api/history")
def get_outfit_history(authorization: str = Header(None)):
    """Get user's generated outfit history"""
    user_id = verify_token(authorization)
    
    resp = requests.get(f"{AI_BACKEND_URL}/api/history/{user_id}")
    if resp.status_code != 200:
        error_detail = resp.json().get("detail", resp.json()) if isinstance(resp.json(), dict) else resp.json()
        raise HTTPException(status_code=resp.status_code, detail=error_detail)
    return resp.json()

@app.delete("/api/history/{combo_id}")
def delete_outfit_history(combo_id: str, authorization: str = Header(None)):
    """Delete an outfit suggestion history"""
    user_id = verify_token(authorization)
    
    resp = requests.delete(f"{AI_BACKEND_URL}/api/history/{user_id}/{combo_id}")
    if resp.status_code != 200:
        error_detail = resp.json().get("detail", resp.json()) if isinstance(resp.json(), dict) else resp.json()
        raise HTTPException(status_code=resp.status_code, detail=error_detail)
    return resp.json()

if __name__ == "__main__":
    print(f"Starting Auth & Profile Server on port {AUTH_SERVER_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=AUTH_SERVER_PORT)