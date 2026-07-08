"""Run at Docker build time to pre-embed the RAG corpus into a FAISS index.
Baking the index into the image means cold-start is instant."""
import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))

from rag import retriever

asyncio.run(retriever.init())
print("RAG index pre-built successfully", flush=True)
