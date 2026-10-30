from app.config import Settings
from app.factory import create_app

# Missing or invalid config raises here, so the mock refuses to start.
app = create_app(Settings())
