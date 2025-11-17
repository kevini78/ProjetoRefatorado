from modular_app import create_app
from modular_app.config import DevConfig, ProdConfig
import os

config_cls = ProdConfig if os.environ.get("APP_ENV") == "production" else DevConfig
app = create_app(config_cls)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
