tmux new -d -s "fastapi" uvicorn fastapi_server.main:app --host=0.0.0.0 --port=8000
