import os


def main() -> None:
    import uvicorn

    uvicorn.run(
        "cuno.server:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
        reload=os.environ.get("CUNO_RELOAD") == "1",
    )
