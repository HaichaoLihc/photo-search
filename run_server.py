#!/usr/bin/env python3
import sys
import uvicorn

if __name__ == "__main__":
    print("=" * 60)
    print("  Starting Photo Search AI Engine & Web Interface")
    print("  URL: http://127.0.0.1:8000")
    print("=" * 60)
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False, access_log=True)
