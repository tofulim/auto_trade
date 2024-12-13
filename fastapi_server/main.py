import os
import dotenv
from fastapi_server.initializer import Initializer
from fastapi_server.utils import FastAPIServer, get_controllers
from fastapi_server.utils import initialize_api_logger


dotenv.load_dotenv(f"/home/ubuntu/zed/auto_trade/config/prod.env")
initialize_api_logger()
Initializer()

server = FastAPIServer()
app = server.app

modules = get_controllers(
    [
        f"fastapi_server.controllers.{name.strip().replace('.py', '')}"
        for name in os.listdir("./fastapi_server/controllers")
        if "controller.py" in name
    ]
)

for module in modules:
    router = module.router
    app.include_router(router)

server.run()
