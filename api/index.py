"""Vercel serverless entry point: every /api/* request is routed here (see vercel.json)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "_lib"))

from kalamela import Handler  # noqa: E402


class handler(Handler):  # Vercel's Python runtime looks for a class named `handler`
    serve_static = False
