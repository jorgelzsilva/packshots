"""
Inicia o servidor web do Packshots.

Uso:
    python run_web.py
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("webui.server:app", host="127.0.0.1", port=8000)
