"""Tests never call a real LLM and never use the answer cache, even when .env has a JAIF key."""
import os

os.environ["LLM_PROVIDER"] = "none"
os.environ["LLM_CACHE"] = "false"
