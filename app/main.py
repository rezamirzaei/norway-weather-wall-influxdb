from app.core.config import load_settings
from app.factory import create_app

app = create_app(load_settings())

