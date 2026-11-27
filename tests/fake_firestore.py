"""Firestore in-memory minimal untuk menguji pairing_service tanpa jaringan.

Mendukung: collection/document, get/set(merge)/create/update/delete, where
(==), limit, stream, batch, dan transaksi sederhana. Transaksi meniru aturan
Firestore bahwa semua baca harus terjadi sebelum tulis pertama.
"""

import copy
from typing import Any, Dict, Iterable, List, Optional

from google.api_core.exceptions import AlreadyExists, NotFound
from google.cloud.firestore_v1.transforms import Increment


def _apply(current: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(current)
    for key, value in patch.items():
        if isinstance(value, Increment):
            out[key] = out.get(key, 0) + value.value
        else:
            out[key] = copy.deepcopy(value)
    return out


class Snap:
    def __init__(self, ref: "DocRef", data: Optional[Dict[str, Any]]) -> None:
        self.reference = ref
        self.id = ref.id
        self.exists = data is not None
        self._data = data

    def to_dict(self) -> Optional[Dict[str, Any]]:
        return copy.deepcopy(self._data) if self._data is not None else None


class DocRef:
    def __init__(self, db: "FakeDb", coll: str, doc_id: str) -> None:
        self._db, self._coll, self.id = db, coll, doc_id

    @property
    def _store(self) -> Dict[str, Dict[str, Any]]:
        return self._db.data.setdefault(self._coll, {})

    def get(self, transaction: Optional["Tx"] = None) -> Snap:
        if transaction is not None:
            transaction.check_read()
        return Snap(self, self._store.get(self.id))

    def create(self, data: Dict[str, Any]) -> None:
        if self.id in self._store:
            raise AlreadyExists("exists")
        self._store[self.id] = _apply({}, data)

    def set(self, data: Dict[str, Any], merge: bool = False) -> None:
        base = self._store.get(self.id, {}) if merge else {}
        self._store[self.id] = _apply(base, data)

    def update(self, data: Dict[str, Any]) -> None:
        if self.id not in self._store:
            raise NotFound("missing")
        self._store[self.id] = _apply(self._store[self.id], data)

    def delete(self) -> None:
        self._store.pop(self.id, None)


class Query:
    def __init__(self, db: "FakeDb", coll: str, filters=(), max_results=None) -> None:
        self._db, self._coll = db, coll
        self._filters = tuple(filters)
        self._limit = max_results

    def where(self, field: str, op: str, value: Any) -> "Query":
        assert op == "==", "fake hanya mendukung =="
        return Query(self._db, self._coll, self._filters + ((field, value),), self._limit)

    def limit(self, n: int) -> "Query":
        return Query(self._db, self._coll, self._filters, n)

    def stream(self, transaction: Optional["Tx"] = None) -> Iterable[Snap]:
        if transaction is not None:
            transaction.check_read()
        docs = self._db.data.get(self._coll, {})
        out: List[Snap] = []
        for doc_id, data in list(docs.items()):
            if all(data.get(f) == v for f, v in self._filters):
                out.append(Snap(DocRef(self._db, self._coll, doc_id), data))
        return iter(out[: self._limit] if self._limit else out)


class Collection(Query):
    def document(self, doc_id: str) -> DocRef:
        return DocRef(self._db, self._coll, doc_id)


class Tx:
    def __init__(self) -> None:
        self._wrote = False

    def check_read(self) -> None:
        if self._wrote:
            raise RuntimeError("Firestore: semua baca harus sebelum tulis dalam transaksi")

    def set(self, ref: DocRef, data, merge: bool = False) -> None:
        self._wrote = True
        ref.set(data, merge=merge)

    def update(self, ref: DocRef, data) -> None:
        self._wrote = True
        ref.update(data)

    def delete(self, ref: DocRef) -> None:
        self._wrote = True
        ref.delete()


class Batch:
    def __init__(self) -> None:
        self._ops = []

    def update(self, ref: DocRef, data) -> None:
        self._ops.append(lambda: ref.update(data))

    def commit(self) -> None:
        for op in self._ops:
            op()


class FakeDb:
    def __init__(self) -> None:
        self.data: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def collection(self, name: str) -> Collection:
        return Collection(self, name)

    def transaction(self) -> Tx:
        return Tx()

    def batch(self) -> Batch:
        return Batch()

    # helper untuk test
    def put(self, coll: str, doc_id: str, data: Dict[str, Any]) -> None:
        self.data.setdefault(coll, {})[doc_id] = copy.deepcopy(data)

    def doc(self, coll: str, doc_id: str) -> Optional[Dict[str, Any]]:
        d = self.data.get(coll, {}).get(doc_id)
        return copy.deepcopy(d) if d is not None else None
