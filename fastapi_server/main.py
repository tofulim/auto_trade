import inject
from fastapi import FastAPI

app = FastAPI()


@app.post("/prophet")
async def prophet():
    pass


@app.post("/buy")
async def buy(name: str):
    pass


@app.post("/cancel")
async def cancel(name: str):
    pass


@app.post("/sell")
async def sell(name: str):
    pass
