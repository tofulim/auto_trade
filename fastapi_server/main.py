import os

from initializer import Initializer
from utils import FastAPIServer, get_controllers, setup_logger

Initializer()

api_logger = setup_logger(__name__)

server = FastAPIServer()
app = server.app

modules = get_controllers(
    [
        f"controllers.{name.strip().replace('.py', '')}"
        for name in os.listdir("./controllers")
        if "controller.py" in name
    ]
)

for module in modules:
    router = module.router
    app.include_router(router)

server.run()
