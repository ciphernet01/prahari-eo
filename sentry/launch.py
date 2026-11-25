import uvicorn

from .config import config


if __name__ == "__main__":
    uvicorn.run("sentry.server:app", host=config["server"]["host"],
                port=config["server"]["port"], access_log=True)
