# FAISS vector store. We L2-normalise embeddings so dot product equals cosine similarity.
# IndexFlatIP works fine for our current corpus size. If it grows a lot, HNSW would be faster.
import shutil
from pathlib import Path
from typing import Optional
import json
import numpy as np
import faiss
from logger import get_logger

log = get_logger("store")

# Bump when the meta schema changes so older caches get rebuilt.
META_VERSION = 4

CACHE_DIR = Path(__file__).parent / ".cache"
INDEX_PATH = CACHE_DIR / "faiss.index"
META_PATH = CACHE_DIR / "meta.json"
DELETED_PATH = CACHE_DIR / "deleted.json"  # persisted soft-delete set
SNAPSHOT_DIR = CACHE_DIR / "snapshots"
MAX_SNAPSHOTS = 5


class VectorStore:
    def __init__(self):
        self.index: Optional[faiss.Index] = None
        self.meta: list[dict] = []
        self._deleted_ids: set[str] = set()  # soft-deleted chunk IDs

    def build(self, items: list[dict], vectors: np.ndarray) -> None:
        d = vectors.shape[1]
        self.index = faiss.IndexFlatIP(d)
        self.index.add(vectors)
        self.meta = [
            {
                "id": it["id"],
                "domain": it["domain"],
                "topic": it["topic"],
                "text": it["text"],
                "source": it.get("source"),
                "lastVerifiedOn": it.get("lastVerifiedOn"),
                "verifiedBy": it.get("verifiedBy", "human"),
            }
            for it in items
        ]

    def _rotate_snapshots(self) -> None:
        """Shift existing snapshots up by one slot, evicting the oldest."""
        if not INDEX_PATH.exists():
            return
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        # Shift: slot N → N+1, drop anything beyond MAX_SNAPSHOTS
        for i in range(MAX_SNAPSHOTS, 0, -1):
            src = SNAPSHOT_DIR / str(i)
            dst = SNAPSHOT_DIR / str(i + 1)
            if src.exists():
                if i >= MAX_SNAPSHOTS:
                    shutil.rmtree(src, ignore_errors=True)
                else:
                    src.rename(dst)
        # Copy current live files into slot 1
        snap1 = SNAPSHOT_DIR / "1"
        snap1.mkdir(parents=True, exist_ok=True)
        if INDEX_PATH.exists():
            shutil.copy2(INDEX_PATH, snap1 / "faiss.index")
        if META_PATH.exists():
            shutil.copy2(META_PATH, snap1 / "meta.json")
        if DELETED_PATH.exists():
            shutil.copy2(DELETED_PATH, snap1 / "deleted.json")

    def save(self) -> None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        # Snapshot current state before overwriting
        self._rotate_snapshots()
        # Atomic write: write to .tmp files then rename (crash-safe)
        tmp_index = CACHE_DIR / "faiss.index.tmp"
        tmp_meta = CACHE_DIR / "meta.json.tmp"
        tmp_deleted = CACHE_DIR / "deleted.json.tmp"
        faiss.write_index(self.index, str(tmp_index))
        tmp_meta.write_text(
            json.dumps({"version": META_VERSION, "items": self.meta}),
            encoding="utf-8",
        )
        tmp_deleted.write_text(
            json.dumps(list(self._deleted_ids)),
            encoding="utf-8",
        )
        tmp_index.replace(INDEX_PATH)
        tmp_meta.replace(META_PATH)
        tmp_deleted.replace(DELETED_PATH)

    def load(self) -> bool:
        if not (INDEX_PATH.exists() and META_PATH.exists()):
            return False
        try:
            payload = json.loads(META_PATH.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or payload.get("version") != META_VERSION:
                log.warning("cache schema mismatch — rebuilding")
                return False
            self.index = faiss.read_index(str(INDEX_PATH))
            self.meta = payload["items"]
            # Load persisted soft-deletes
            if DELETED_PATH.exists():
                self._deleted_ids = set(json.loads(DELETED_PATH.read_text(encoding="utf-8")))
            return True
        except Exception as err:
            log.error("failed to load cache", error=str(err))
            return False

    def add_items(self, items: list[dict], vectors) -> None:
        """Add new chunks to a live index without rebuilding from scratch."""
        if self.index is None or not self.meta:
            self.build(items, vectors)
            self.save()
            return
        self.index.add(vectors)
        self.meta.extend([
            {
                "id": it["id"],
                "domain": it["domain"],
                "topic": it["topic"],
                "text": it["text"],
                "source": it.get("source"),
                "lastVerifiedOn": it.get("lastVerifiedOn"),
                "verifiedBy": it.get("verifiedBy", "human"),
            }
            for it in items
        ])
        self.save()

    def delete_chunks(self, ids: list[str]) -> int:
        """Soft-delete chunks by ID — masked at query time, persisted across loads."""
        before = len(self._deleted_ids)
        self._deleted_ids.update(ids)
        added = len(self._deleted_ids) - before
        if added:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            DELETED_PATH.write_text(
                json.dumps(list(self._deleted_ids)), encoding="utf-8"
            )
            log.info("soft-deleted chunks", added=added, total_deleted=len(self._deleted_ids))
        return added

    def size(self) -> int:
        """Number of live (non-deleted) chunks."""
        if self.index is None:
            return 0
        return self.index.ntotal - len(self._deleted_ids)

    def should_compact(self, threshold: float = 0.30) -> bool:
        """True when deleted vectors waste ≥ threshold fraction of total slots."""
        if self.index is None or self.index.ntotal == 0:
            return False
        return len(self._deleted_ids) / self.index.ntotal >= threshold

    def rebuild(self, embedder_fn) -> int:
        """Re-embed live chunks into a fresh index, physically evicting deleted vectors."""
        if self.index is None or not self.meta:
            return 0
        live_items = [m for m in self.meta if m["id"] not in self._deleted_ids]
        if not live_items:
            self.index = None
            self.meta = []
            self._deleted_ids = set()
            self.save()
            return 0
        texts = [f"passage: {it['topic']}\n{it['text']}" for it in live_items]
        vectors = embedder_fn(texts)
        self.build(live_items, vectors)
        self._deleted_ids = set()
        self.save()
        log.info("index compacted", live_chunks=self.index.ntotal)
        return self.index.ntotal

    def rollback(self, steps: int = 1) -> bool:
        """Restore from a snapshot. `steps=1` is the most recent. Returns False if snapshot missing."""
        snap = SNAPSHOT_DIR / str(steps)
        snap_index = snap / "faiss.index"
        snap_meta = snap / "meta.json"
        if not snap.exists() or not snap_index.exists() or not snap_meta.exists():
            return False
        shutil.copy2(snap_index, INDEX_PATH)
        shutil.copy2(snap_meta, META_PATH)
        snap_deleted = snap / "deleted.json"
        if snap_deleted.exists():
            shutil.copy2(snap_deleted, DELETED_PATH)
        elif DELETED_PATH.exists():
            DELETED_PATH.unlink()
        loaded = self.load()
        if loaded:
            log.info("rolled back", steps=steps)
        return loaded

    def list_snapshots(self) -> list[dict]:
        """Return info about available snapshots, newest first."""
        if not SNAPSHOT_DIR.exists():
            return []
        snaps = []
        for d in sorted(SNAPSHOT_DIR.iterdir(), key=lambda p: int(p.name) if p.name.isdigit() else 999):
            if not d.is_dir() or not d.name.isdigit():
                continue
            meta_f = d / "meta.json"
            try:
                payload = json.loads(meta_f.read_text(encoding="utf-8"))
                n = len(payload.get("items", []))
            except Exception:
                n = -1
            snaps.append({"step": int(d.name), "chunks": n})
        return snaps

    def search(self, query_vec: np.ndarray, k: int = 3, domain: Optional[str] = None) -> list[dict]:
        if self.index is None:
            return []
        # Overfetch to account for deleted items and domain filtering
        n_fetch = min(self.index.ntotal, k + len(self._deleted_ids) + 10)
        q = query_vec.reshape(1, -1).astype("float32")
        scores, idxs = self.index.search(q, n_fetch)
        out: list[dict] = []
        for score, idx in zip(scores[0], idxs[0]):
            if idx < 0:
                continue
            m = self.meta[idx]
            if m["id"] in self._deleted_ids:
                continue  # skip soft-deleted chunks
            if domain and m["domain"] != domain:
                continue
            out.append({**m, "score": float(score)})
            if len(out) == k:
                break
        return out
