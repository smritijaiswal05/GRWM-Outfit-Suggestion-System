import os
import uuid

# Determine the base directory for file paths (Fix #8 - CWD independence)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
import certifi
import requests
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image
from sklearn.cluster import KMeans
from torchvision.ops import nms
from transformers import OwlViTProcessor, OwlViTForObjectDetection, CLIPModel, CLIPProcessor
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional

# Load configuration (BUG FIX #13 - Standardized CORS, #6 - Environment variables)
try:
    from config import MONGO_CONNECTION_STRING, ALLOWED_ORIGINS, AI_SERVER_PORT
except ImportError:
    MONGO_CONNECTION_STRING = os.getenv(
        "MONGO_CONNECTION_STRING",
        "mongodb+srv://admin:admin123@cluster0.fzt0yhs.mongodb.net/?appName=Cluster0"
    )
    ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
    AI_SERVER_PORT = int(os.getenv("AI_SERVER_PORT", "8000"))


app = FastAPI(title="Stylist Engine API (Monolithic)")

# BUG FIX #13 - Standardized CORS configuration with environment variable support
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(os.path.join(STATIC_DIR, "detected_items"), exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

client = MongoClient(MONGO_CONNECTION_STRING, tlsCAFile=certifi.where())
db = client["stylist_engine"]
wardrobe = db["wardrobe"]
suggested_outfits = db["suggested_outfits"]

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"🚀 Booting AI Engine on: {device.upper()}")


class ImageUploadRequest(BaseModel):
    userID: str
    image_link: str
    local_path: Optional[str] = None

class ImageUploadResponse(BaseModel):
    message: str
    items_found: int

class SuggestionRequest(BaseModel):
    userID: str
    prompt: str
    skin_tone: Optional[str] = "#e0ac69"
    body_shape: Optional[str] = "rectangular"

class ClothingItem(BaseModel):
    itemID: str
    category: str
    sub_category: str
    rgb_color: List[int]
    local_path: str
    formality: Optional[str] = "casual"
    fit: Optional[str] = "regular"

class SuggestionResponse(BaseModel):
    shirt: ClothingItem
    pants: ClothingItem
    compatibility_score: float

class WardrobeUpdate(BaseModel):
    userID: str
    category: str
    formality: str
    fit: str

class OutfitTransformer(nn.Module):
    def __init__(self, embedding_dim=512, num_heads=8, num_layers=6):
        super().__init__()
        self.outfit_token = nn.Parameter(torch.randn(1, 1, embedding_dim))
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=embedding_dim, nhead=num_heads, 
            dim_feedforward=2048, dropout=0.2, 
            batch_first=True, dtype=torch.float32
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.mlp = nn.Sequential(
            nn.Linear(embedding_dim, 256, dtype=torch.float32),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, 1, dtype=torch.float32)
        )

    def forward(self, x):
        batch_size = x.size(0)
        tokens = self.outfit_token.expand(batch_size, -1, -1)
        x = torch.cat([tokens, x], dim=1)
        out = self.transformer(x)
        return self.mlp(out[:, 0, :])

# Load HuggingFace Models
owl_processor = OwlViTProcessor.from_pretrained("google/owlvit-base-patch32")
owl_model = OwlViTForObjectDetection.from_pretrained("google/owlvit-base-patch32").to(device)
clip_processor = CLIPProcessor.from_pretrained("patrickjohncyh/fashion-clip")
clip_model = CLIPModel.from_pretrained("patrickjohncyh/fashion-clip").to(device)

# Load Custom Model
transformer_model = OutfitTransformer().to(device)
model_path = "outfit_transformer_v2.pth"
if os.path.exists(model_path):
    transformer_model.load_state_dict(torch.load(model_path, map_location=device, weights_only=True))
    print("✅ Custom Outfit Transformer loaded.")
transformer_model.eval()

# Precompute CLIP text features for the preprocessor
def encode_text(texts):
    inputs = clip_processor(text=texts, return_tensors="pt", padding=True).to(device)
    with torch.no_grad():
        feats = clip_model.get_text_features(**inputs)
        feats = feats.pooler_output if hasattr(feats, "pooler_output") else (feats.text_embeds if hasattr(feats, "text_embeds") else feats)
    return F.normalize(feats, p=2, dim=-1)

formality_labels = ["formal", "business_casual", "casual", "loungewear"]
formality_feats = encode_text([
    "formal wear, suit, crisp dress shirt, dress pants, tuxedo", 
    "business casual, button-down shirt, polo, chinos, smart trousers", 
    "casual wear, graphic t-shirt, denim jeans, cargo pants, shorts", 
    "loungewear, sweatpants, hoodie, activewear, gym clothes"
])

fit_labels = ["slim", "regular", "loose", "oversized"]
fit_feats = encode_text([
    "slim fit tight clothing", "regular fit clothing", "loose fit baggy clothing", "oversized clothing"
])

category_labels = ["shirt", "pants", "pants", "dress", "dress", "outerwear", "TRASH"]
cat_feats = encode_text([
    "a photo of a shirt, t-shirt, or top", 
    "a photo of a pair of pants, trousers, or jeans", 
    "a photo of a pair of shorts", 
    "a photo of a skirt", "a photo of a dress", 
    "a photo of a jacket, sweater, or outerwear",
    "a close up of fabric, a pocket, a button, background, or noise"
])


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return (255, 224, 189)

def get_dominant_color(pil_img):
    img = pil_img.resize((50, 50))
    ar = np.asarray(img).reshape(-1, 3)
    kmeans = KMeans(n_clusters=3, n_init='auto').fit(ar)
    counts = np.unique(kmeans.labels_, return_counts=True)[1]
    dominant = kmeans.cluster_centers_[np.argmax(counts)]
    return [int(c) for c in dominant]

def get_color_harmony_score(colors):
    if len(colors) < 2: return 1.0
    dist = np.linalg.norm(np.array(colors[0]) - np.array(colors[1])) / 441.0
    if dist < 0.15 or dist > 0.6: return 1.0
    return 0.8

def get_skin_tone_score(rgb_color, skin_tone_hex):
    skin_rgb = hex_to_rgb(skin_tone_hex)
    skin_lum = (0.299 * skin_rgb[0] + 0.587 * skin_rgb[1] + 0.114 * skin_rgb[2]) / 255.0
    item_lum = (0.299 * rgb_color[0] + 0.587 * rgb_color[1] + 0.114 * rgb_color[2]) / 255.0
    return float(np.clip(abs(skin_lum - item_lum) * 1.5, 0.4, 1.0))

def get_body_shape_score(fit, body_shape):
    matrix = {
        "rectangular": {"slim": 1.0, "regular": 0.9, "loose": 0.7, "oversized": 0.6},
        "circular": {"loose": 1.0, "regular": 0.9, "slim": 0.6, "oversized": 0.8},
        "elliptical": {"regular": 1.0, "slim": 0.8, "loose": 0.8, "oversized": 0.7},
        "triangular": {"regular": 1.0, "loose": 0.9, "slim": 0.7, "oversized": 0.8},
        "inverted_triangle": {"slim": 1.0, "regular": 0.9, "loose": 0.7, "oversized": 0.6}
    }
    return float(matrix.get(body_shape.lower(), matrix["rectangular"]).get(fit.lower(), 0.8))

def filter_contained_boxes(boxes_tensor, iomin_threshold=0.85):
    boxes = boxes_tensor.tolist()
    keep = []
    for i in range(len(boxes)):
        is_contained = False
        for j in range(len(boxes)):
            if i == j: continue
            x1, y1, x2, y2 = max(boxes[i][0], boxes[j][0]), max(boxes[i][1], boxes[j][1]), min(boxes[i][2], boxes[j][2]), min(boxes[i][3], boxes[j][3])
            if x2 > x1 and y2 > y1:
                inter = (x2 - x1) * (y2 - y1)
                area_i = (boxes[i][2] - boxes[i][0]) * (boxes[i][3] - boxes[i][1])
                area_j = (boxes[j][2] - boxes[j][0]) * (boxes[j][3] - boxes[j][1])
                if (inter / area_i) > iomin_threshold and area_i < area_j:
                    is_contained = True; break
        if not is_contained: keep.append(i)
    return keep


@app.post("/api/upload", response_model=ImageUploadResponse)
def upload_image(request: ImageUploadRequest):
    # Fix #4 - Initialize temp_path before try block to avoid NameError in except
    temp_path = None
    try:
        # Optimization: Use local path if provided to avoid redundant downloads
        if request.local_path and os.path.exists(request.local_path):
            img = Image.open(request.local_path).convert("RGB")
        else:
            response = requests.get(request.image_link, stream=True)
            response.raise_for_status()
            
            temp_path = os.path.join(BASE_DIR, f"temp_{uuid.uuid4()}.jpg")
            with open(temp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192): f.write(chunk)
            img = Image.open(temp_path).convert("RGB")
        queries = ["a full shirt", "a t-shirt", "a button down shirt", "a pair of pants", "jeans", "shorts", "slacks", "cargo pants", "a jacket", "a sweater"]
        
        inputs = owl_processor(text=[queries], images=img, return_tensors="pt").to(device)
        with torch.no_grad(): outputs = owl_model(**inputs)
        
        results = owl_processor.post_process_object_detection(
            outputs=outputs, threshold=0.25, target_sizes=torch.Tensor([img.size[::-1]]).to(device)
        )[0]

        boxes, scores = results["boxes"].cpu(), results["scores"].cpu()
        keep = nms(boxes, scores, iou_threshold=0.25)
        boxes, scores = boxes[keep], scores[keep]
        not_contained = filter_contained_boxes(boxes)
        boxes, scores = boxes[not_contained], scores[not_contained]

        count = 0
        for box in boxes:
            x1, y1, x2, y2 = box.tolist()
            if ((x2 - x1) * (y2 - y1)) < ((img.width * img.height) * 0.05): continue
                
            crop = img.crop((max(0, x1), max(0, y1), min(img.width, x2), min(img.height, y2)))
            clip_inputs = clip_processor(images=crop, return_tensors="pt").to(device)
            
            with torch.no_grad():
                feat = clip_model.get_image_features(**clip_inputs)
                feat = feat.pooler_output if hasattr(feat, "pooler_output") else (feat.image_embeds if hasattr(feat, "image_embeds") else feat)
            img_feat_norm = F.normalize(feat, p=2, dim=-1)
            
            cat_idx = torch.matmul(img_feat_norm, cat_feats.T).argmax().item()
            main_category = category_labels[cat_idx]
            if main_category == "TRASH": continue
                
            formality = formality_labels[torch.matmul(img_feat_norm, formality_feats.T).argmax().item()]
            fit = fit_labels[torch.matmul(img_feat_norm, fit_feats.T).argmax().item()]
            
            cat_dir = os.path.join(STATIC_DIR, "detected_items", main_category)
            os.makedirs(cat_dir, exist_ok=True)
            item_id = str(uuid.uuid4())
            file_name = f"{main_category}_{item_id[:8]}.png"
            crop.save(os.path.join(cat_dir, file_name))

            wardrobe.insert_one({
                "userID": request.userID, "itemID": item_id, "category": main_category, "sub_category": main_category,
                "embedding": img_feat_norm.cpu().numpy().flatten().tolist(),
                "rgb_color": get_dominant_color(crop),
                "local_path": f"/static/detected_items/{main_category}/{file_name}", "formality": formality, "fit": fit
            })
            count += 1

        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
        if count == 0: raise HTTPException(status_code=404, detail="No valid clothes found.")
        return ImageUploadResponse(message="Processed.", items_found=count)

    except HTTPException:
        if temp_path and os.path.exists(temp_path): os.remove(temp_path)
        raise
    except Exception as e:
        if temp_path and os.path.exists(temp_path): os.remove(temp_path)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/wardrobe/{userID}", response_model=List[ClothingItem])
def get_wardrobe(userID: str):
    items = list(wardrobe.find({"userID": userID}, {"_id": 0, "embedding": 0}))
    # Fix #7 - Return empty list instead of 404 for empty wardrobe
    return items

@app.post("/api/suggest", response_model=SuggestionResponse)
async def suggest_outfit(request: SuggestionRequest):
    try:
        p_lower = request.prompt.lower()
        is_formal = any(w in p_lower for w in ["formal", "suit", "wedding", "party", "business", "office"])

        all_shirts = [s for s in wardrobe.find({"userID": request.userID, "category": "shirt"}, {"_id": 0}) if "embedding" in s]
        all_pants = [p for p in wardrobe.find({"userID": request.userID, "category": "pants"}, {"_id": 0}) if "embedding" in p]

        if not all_shirts or not all_pants:
            raise HTTPException(status_code=404, detail="Upload shirts and pants first.")

        prompt_emb = encode_text([request.prompt])
        pants_tensors = torch.tensor([p["embedding"] for p in all_pants], dtype=torch.float32).to(device)
        
        combos = []

        for shirt in all_shirts:
            s_emb = torch.tensor(shirt["embedding"], dtype=torch.float32).to(device)
            # Batch evaluate this shirt against all pants via the learned transformer
            x = torch.stack([s_emb.unsqueeze(0).expand(len(all_pants), -1), pants_tensors], dim=1)
            
            with torch.no_grad():
                ai_scores = torch.sigmoid(transformer_model(x)).squeeze().cpu().tolist()
                if not isinstance(ai_scores, list): ai_scores = [ai_scores]

            for i, pant in enumerate(all_pants):
                combo_str = f"{shirt['itemID']}_{pant['itemID']}"
                if suggested_outfits.find_one({"userID": request.userID, "items": combo_str}): continue

                pant_emb = pants_tensors[i]
                
                # Autonomous alignment: does this clothing pair match the text context as a composite outfit?
                outfit_emb = F.normalize(s_emb + pant_emb, p=2, dim=-1)
                text_sim = torch.matmul(prompt_emb, outfit_emb).item()

                colors = [shirt.get("rgb_color", [255,255,255]), pant.get("rgb_color", [255,255,255])]
                
                bonus = 0
                if "casual" in p_lower and shirt.get("formality") == "casual": bonus += 0.05
                if "formal" in p_lower and shirt.get("formality") == "formal": bonus += 0.05

                combos.append({
                    "shirt": shirt,
                    "pant": pant,
                    "combo_str": combo_str,
                    "ai_score": ai_scores[i],
                    "text_sim": text_sim,
                    "color_score": get_color_harmony_score(colors),
                    "skin_score": sum(get_skin_tone_score(c, request.skin_tone) for c in colors)/2,
                    "bonus": bonus
                })

        if not combos: raise HTTPException(status_code=404, detail="No new combinations left.")

        t_sims = [c["text_sim"] for c in combos]
        max_t = max(t_sims); min_t = min(t_sims)
        
        # Absolute rejection threshold: lowered from 0.208 to 0.180 for better compatibility
        # CLIP scores for some valid items like 'grey pants' can be lower than 0.20
        if max_t < 0.180: 
            raise HTTPException(status_code=404, detail=f"No matching outfits in your wardrobe found for '{request.prompt}'. Try a different prompt or upload more clothes.")

        best_score, best_combo, best_str = -float('inf'), None, ""
        for c in combos:
            # Stricter boundary: lowered from 0.210 to 0.190 for better reach
            if c["text_sim"] < 0.190: continue

            # Exponentially emphasize higher text similarities - lowered intensity from 50 to 20
            # to prevent tiny CLIP differences from completely wiping out color/AI scores
            import math
            norm_text = math.exp((c["text_sim"] - min_t) * 20) / math.exp((max_t - min_t) * 20)
            
            # Holistic weighting
            score = (c["ai_score"] * 0.30) + (norm_text * 0.60) + (c["color_score"] * 0.05) + (c["skin_score"] * 0.05) + c["bonus"]
            
            if score > best_score:
                best_score = score
                best_combo = (c["shirt"], c["pant"])
                best_str = c["combo_str"]

        if not best_combo: raise HTTPException(status_code=404, detail=f"Cannot make any more outfits matching '{request.prompt}'.")
        
        try: suggested_outfits.insert_one({"userID": request.userID, "items": best_str})
        except DuplicateKeyError: pass

        s_data, p_data = best_combo
        del s_data["embedding"]; del p_data["embedding"]

        return SuggestionResponse(
            shirt=ClothingItem(**s_data), pants=ClothingItem(**p_data),
            compatibility_score=round(max(0.0, min(1.0, best_score)), 2)
        )

    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))


# BUG FIX #4 + Fix #6 - Delete endpoint with user validation
@app.delete("/api/wardrobe/{itemID}")
def delete_wardrobe_item(itemID: str, userID: str = None):
    """Delete a clothing item from user's wardrobe
    
    Args:
        itemID: The ID of the item to delete
        userID: The user ID (query parameter for ownership validation)
    """
    try:
        # Fix #6 - Validate ownership: only delete items belonging to the requesting user
        query = {"itemID": itemID}
        if userID:
            query["userID"] = userID
        
        # Verify the item exists and belongs to the user
        item = wardrobe.find_one(query)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found or you don't have permission to delete it")
        
        # Delete the item
        result = wardrobe.delete_one(query)
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Item not found")
        
        # Also remove from suggested outfits to maintain consistency
        suggested_outfits.delete_many({
            "items": {"$regex": itemID}
        })
        
        # Clean up the image file if it exists
        if item.get("local_path"):
            img_path = os.path.join(BASE_DIR, item["local_path"].lstrip("/"))
            if os.path.exists(img_path):
                try:
                    os.remove(img_path)
                except OSError:
                    pass  # Non-critical: file cleanup failure
        
        return {
            "success": True,
            "message": f"Item {itemID} deleted successfully",
            "deleted_count": result.deleted_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete item: {str(e)}")

@app.put("/api/wardrobe/{itemID}")
def update_wardrobe_item(itemID: str, request: WardrobeUpdate):
    item = wardrobe.find_one({"itemID": itemID, "userID": request.userID})
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    wardrobe.update_one({"itemID": itemID}, {"$set": {
        "category": request.category,
        "formality": request.formality,
        "fit": request.fit
    }})
    return {"success": True}

@app.get("/api/history/{userID}")
def get_outfit_history(userID: str):
    history = list(suggested_outfits.find({"userID": userID}, {"_id": 0}))
    results = []
    for h in history:
        items_arr = h["items"].split("_")
        if len(items_arr) != 2: continue
        shirt_id, pant_id = items_arr[0], items_arr[1]
        shirt = wardrobe.find_one({"itemID": shirt_id}, {"_id": 0, "embedding": 0})
        pants = wardrobe.find_one({"itemID": pant_id}, {"_id": 0, "embedding": 0})
        if shirt and pants:
            results.append({
                "comboID": h["items"],
                "shirt": shirt,
                "pants": pants
            })
    return results

@app.delete("/api/history/{userID}/{comboID}")
def delete_outfit_history(userID: str, comboID: str):
    result = suggested_outfits.delete_one({"userID": userID, "items": comboID})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Combination not found")
    return {"success": True}


if __name__ == "__main__":
    import uvicorn
    print(f"🚀 Starting AI Engine on port {AI_SERVER_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=AI_SERVER_PORT)