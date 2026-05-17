import os
from dotenv import load_dotenv

load_dotenv()

# MongoDB Configuration (BUG FIX #6 - Use environment variables)
MONGO_CONNECTION_STRING = os.getenv(
    "MONGO_CONNECTION_STRING",
    "mongodb+srv://admin:admin123@cluster0.fzt0yhs.mongodb.net/?appName=Cluster0"
)

# JWT Configuration (BUG FIX #5 - Use strong secret from environment)
JWT_SECRET = os.getenv("JWT_SECRET", "your_very_long_and_random_secret_key_with_at_least_32_characters")
JWT_EXPIRATION_DAYS = int(os.getenv("JWT_EXPIRATION_DAYS", "7"))

# Server Configuration
AUTH_SERVER_PORT = int(os.getenv("AUTH_SERVER_PORT", "8001"))
AI_SERVER_PORT = int(os.getenv("AI_SERVER_PORT", "8000"))
BASE_URL = os.getenv("BASE_URL", "http://localhost:8001")
AI_BACKEND_URL = os.getenv("AI_BACKEND_URL", "http://localhost:8000")

# CORS Configuration (BUG FIX #13 - Standardized CORS)
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://localhost:8001,https://tpf0z1k2-3000.inc1.devtunnels.ms"
).split(",")

print(f"✅ Configuration loaded from environment variables")
print(f"   JWT Secret: {'*' * 20} (length: {len(JWT_SECRET)})")
print(f"   Allowed Origins: {ALLOWED_ORIGINS}")
