"""In-memory cosine index over stored ticket embeddings."""

import threading

import numpy as np


class DimensionMismatch(Exception):
    pass


def to_bytes(value) -> bytes:
    if value is None:
        return b""
    if isinstance(value, memoryview):
        return value.tobytes()
    return bytes(value)


class EmbeddingIndex:
    def __init__(self):
        self.lock = threading.Lock()
        self.ids = np.zeros((0,), dtype=np.int64)
        self.matrix = np.zeros((0, 0), dtype=np.float32)

    def rebuild(self, rows) -> None:
        parsed = []
        for ticket_id, blob in rows:
            raw = to_bytes(blob)
            if not raw or len(raw) % 4:
                continue
            parsed.append((int(ticket_id), np.frombuffer(raw, dtype=np.float32).copy()))
        with self.lock:
            if not parsed:
                self.ids = np.zeros((0,), dtype=np.int64)
                self.matrix = np.zeros((0, 0), dtype=np.float32)
                return
            dimension = int(parsed[0][1].shape[0])
            parsed = [(ticket_id, vector) for ticket_id, vector in parsed if vector.shape[0] == dimension]
            matrix = np.zeros((len(parsed), dimension), dtype=np.float32)
            ids = np.zeros((len(parsed),), dtype=np.int64)
            for index, (ticket_id, vector) in enumerate(parsed):
                matrix[index] = vector
                ids[index] = ticket_id
            self.matrix = matrix
            self.ids = ids

    def add(self, ticket_id: int, vector) -> None:
        vector = np.asarray(vector, dtype=np.float32).ravel()
        with self.lock:
            if self.matrix.size == 0:
                self.matrix = vector.reshape(1, -1)
                self.ids = np.array([ticket_id], dtype=np.int64)
                return
            if vector.shape[0] != self.matrix.shape[1]:
                return
            self.matrix = np.vstack([self.matrix, vector.reshape(1, -1)])
            self.ids = np.append(self.ids, int(ticket_id))

    def search(self, vector, k: int = 8, exclude: int | None = None):
        query = np.asarray(vector, dtype=np.float32).ravel()
        with self.lock:
            if self.ids.size == 0:
                return []
            if query.shape[0] != self.matrix.shape[1]:
                raise DimensionMismatch(
                    f"Query dimension {query.shape[0]} does not match the stored embeddings "
                    f"({self.matrix.shape[1]}). Re-run bootstrap so both use the same embedder."
                )
            scores = self.matrix @ query
            ids = self.ids
            if exclude is not None:
                scores = scores.copy()
                scores[ids == int(exclude)] = -1.0
            k = min(int(k), int(scores.shape[0]))
            if k <= 0:
                return []
            top = np.argpartition(scores, -k)[-k:]
            top = top[np.argsort(scores[top])[::-1]]
            return [(int(ids[index]), float(scores[index])) for index in top if scores[index] > 0]


index = EmbeddingIndex()
