# `True` indicates server, `False` indicates local
IS_SERVER = False
# Set the global URL prefix
URL_PREFIX = "/praat" if IS_SERVER else ""

import os
# /project root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# /app
APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))
POOL_DIR = os.path.join(APP_DIR, "static", "videos", "pool")