"""用隔离数据库、模拟响应和本地 HTTP 服务验证检索链路。"""
import asyncio
import importlib.util
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pytest
from aiohttp import web


ROOT = Path(__file__).resolve().parent.parent
PACKAGE = "tag_retrieval_under_test"
spec = importlib.util.spec_from_file_location(
    PACKAGE, ROOT / "retrieval" / "__init__.py",
    submodule_search_locations=[str(ROOT / "retrieval")],
)
package = importlib.util.module_from_spec(spec)
sys.modules[PACKAGE] = package
spec.loader.exec_module(package)
client_module = importlib.import_module(f"{PACKAGE}.client")
source = importlib.import_module(f"{PACKAGE}.source")
index_module = importlib.import_module(f"{PACKAGE}.index")
service_module = importlib.import_module(f"{PACKAGE}.service")
Client = client_module.SiliconFlowClient
Error = client_module.RetrievalError
VectorIndex = index_module.VectorIndex
Service = service_module.CharacterRetrievalService


@pytest.fixture
def character_db(tmp_path):
    path = tmp_path / "角色 #1.db"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE characters (character TEXT PRIMARY KEY, name_cn TEXT, copyright_cn TEXT, "
            "trigger TEXT, core_tags TEXT, count INTEGER)"
        )
        connection.executemany("INSERT INTO characters VALUES (?, ?, ?, ?, ?, ?)", [
            ("ganyu", "甘雨", "原神", "ganyu (genshin impact)", "blue hair, horns", 100),
            ("ganyu_fan", "甘雨", "同人", "ganyu fan", "black hair", 20),
            ("miku", "初音未来", "VOCALOID", "hatsune miku", "aqua hair, twintails", 200),
            ("literal", "100%_角色", "测试", "literal", "", 1),
        ])
    return path


class FakeClient(Client):
    def __init__(self):
        super().__init__(api_key="仅供测试的占位凭据")
        self.calls = []
        self.fail = False

    async def embed(self, texts):
        self.calls.append(list(texts))
        if self.fail:
            raise Error("模拟请求失败")
        return np.asarray([
            [1, 0] if "甘雨" in text or "赶雨" in text else [0, 1]
            for text in texts
        ], dtype=np.float32)

    async def rerank(self, query, records):
        raise Error("模拟重排不可用")


def make_service(tmp_path, character_db, client=None, **kwargs):
    return Service(client or FakeClient(), character_db, tmp_path / "index.npz", **kwargs)


def test_batch_response_order_and_dimension(monkeypatch):
    client = Client("占位", batch_size=2)
    calls = []

    async def post(url, payload):
        calls.append(payload["input"])
        return {"data": [
            {"index": i, "embedding": [int(value), 1]}
            for i, value in reversed(list(enumerate(payload["input"])))
        ]}

    monkeypatch.setattr(client, "_post", post)
    result = asyncio.run(client.embed(["1", "2", "3"]))
    assert calls == [["1", "2"], ["3"]]
    np.testing.assert_array_equal(result, [[1, 1], [2, 1], [3, 1]])

    async def wrong_dimension(url, payload):
        return {"data": [{"index": i, "embedding": [1] * len(payload["input"])}
                         for i in range(len(payload["input"]))]}

    monkeypatch.setattr(client, "_post", wrong_dimension)
    with pytest.raises(Error, match="维度"):
        asyncio.run(client.embed(["1", "2", "3"]))


@pytest.mark.parametrize("data", [
    [], [{"index": 1, "embedding": [1, 2]}], [{"index": True, "embedding": [1]}],
    [{"index": 0, "embedding": [float("nan")]}], [{"index": 0, "embedding": [0, 0]}],
    [{"index": 0, "embedding": []}], [{"index": 0, "embedding": ["1"]}],
])
def test_invalid_embedding_response(data):
    with pytest.raises(Error):
        Client._parse_embeddings({"data": data}, 1)


def test_duplicate_and_ragged_vectors():
    for rows in [
        [{"index": 0, "embedding": [1]}, {"index": 0, "embedding": [2]}],
        [{"index": 0, "embedding": [1]}, {"index": 1, "embedding": [2, 3]}],
    ]:
        with pytest.raises(Error):
            Client._parse_embeddings({"data": rows}, 2)


def test_http_protocol_and_safe_errors():
    async def run():
        received = []

        async def embeddings(request):
            received.append(await request.json())
            assert request.headers["Authorization"].startswith("Bearer ")
            return web.json_response({"data": [{"index": 0, "embedding": [1, 2]}]})

        async def failed(request):
            return web.Response(status=401, text="不应泄露的响应正文")

        async def slow(request):
            await asyncio.sleep(0.05)
            return web.json_response({})

        app = web.Application()
        app.router.add_post("/embeddings", embeddings)
        app.router.add_post("/failed", failed)
        app.router.add_post("/slow", slow)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        base = f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}"
        try:
            client = Client("占位", embedding_url=base + "/embeddings")
            assert (await client.embed(["甘雨"])).shape == (1, 2)
            assert received[0]["model"] == "Qwen/Qwen3-Embedding-4B"
            with pytest.raises(Error, match="401") as caught:
                await client._post(base + "/failed", {})
            assert "不应泄露" not in str(caught.value)
            client.timeout = 0.01
            with pytest.raises(Error, match="超时"):
                await client._post(base + "/slow", {})
        finally:
            await runner.cleanup()

    asyncio.run(run())


def test_corpus_fingerprint_and_readonly(character_db):
    before = character_db.read_bytes()
    records, fingerprint = source.load_characters(character_db)
    assert "甘雨" in records[0].text and "blue hair" in records[0].text
    assert source.load_characters(character_db)[1] == fingerprint
    assert character_db.read_bytes() == before
    with sqlite3.connect(character_db) as connection:
        connection.execute("UPDATE characters SET core_tags='新标签' WHERE character='ganyu'")
    assert source.load_characters(character_db)[1] != fingerprint
    assert len(source.search_names(character_db, "%_")) == 1
    assert source.search_names(character_db, "hatsune")[0].record_id == "miku"


def test_cache_hit_database_and_model_invalidation(tmp_path, character_db):
    async def run():
        first = make_service(tmp_path, character_db)
        await first.start()
        assert len(first.client.calls) == 1
        second = make_service(tmp_path, character_db)
        await second.start()
        assert not second.client.calls
        assert second.index.records[0].payload["trigger"] == "ganyu (genshin impact)"
        with sqlite3.connect(character_db) as connection:
            connection.execute("UPDATE characters SET trigger='更新触发词' WHERE character='ganyu'")
        third = make_service(tmp_path, character_db)
        await third.start()
        assert len(third.client.calls) == 1
        assert third.index.records[0].payload["trigger"] == "更新触发词"
        fourth = make_service(tmp_path, character_db)
        fourth.client.embedding_model = "另一个模型"
        await fourth.start()
        assert len(fourth.client.calls) == 1

    asyncio.run(run())


def test_cache_corruption_and_atomic_replace(tmp_path, character_db, monkeypatch):
    records, _ = source.load_characters(character_db)
    path = tmp_path / "index.npz"
    path.write_bytes(b"corrupt")
    assert VectorIndex.load(path, records, {}) is None
    index = VectorIndex(records, np.ones((len(records), 2)))
    index.save(path, {"model": "测试"})
    original = path.read_bytes()

    def fail_replace(*args):
        raise OSError("模拟原子替换失败")

    monkeypatch.setattr(index_module.os, "replace", fail_replace)
    with pytest.raises(OSError):
        index.save(path, {"model": "新模型"})
    assert path.read_bytes() == original
    assert not list(tmp_path.glob("*.tmp"))
    assert VectorIndex.load(path, records, {"model": "测试"}) is not None
    assert VectorIndex.load(path, records, {"model": "其它"}) is None


def test_sqlite_fallback_without_key_or_on_failure(tmp_path, character_db):
    async def run():
        service = make_service(tmp_path, character_db)
        service.client.api_key = ""
        assert (await service.search("甘雨", "原神"))[0]["trigger"] == "ganyu (genshin impact)"
        assert not service.client.calls
        assert not service.index_path.exists()
        service.client.api_key = "占位"
        service.client.fail = True
        assert len(await service.search("甘雨")) == 2
        assert service.index is None
        assert await service.search("不存在") == []
        assert len(service.client.calls) == 1
        with pytest.raises(ValueError):
            await service.search(" ")

    asyncio.run(run())


def test_first_queries_share_build_and_wait(tmp_path, character_db):
    async def run():
        service = make_service(tmp_path, character_db)
        assert service.start() is service.start()
        results = await asyncio.gather(service.search("赶雨", "原神"), service.search("甘雨", "原神"))
        assert all(result[0]["name_cn"] == "甘雨" for result in results)
        assert sum(len(call) == 4 for call in service.client.calls) == 1
        service.client.fail = True
        assert (await service.search("初音"))[0]["name_cn"] == "初音未来"

    asyncio.run(run())


def test_cosine_threshold_dimension_and_copyright(character_db):
    records, _ = source.load_characters(character_db)
    index = VectorIndex(records, np.array([[3, 0], [2, 0], [0, 2], [0, 5]]))
    found = index.search(np.array([1, 0]), copyright="原神")
    assert [(record.record_id, score) for record, score in found] == [("ganyu", 1.0)]
    assert index.search(np.array([-1, -1]), min_similarity=0.9) == []
    with pytest.raises(Error):
        index.search(np.array([1, 2, 3]))


def test_missing_database_does_not_create_file(tmp_path):
    missing = tmp_path / "不存在.db"
    with pytest.raises(FileNotFoundError):
        source.load_characters(missing)
    with pytest.raises(FileNotFoundError):
        asyncio.run(make_service(tmp_path, missing).search("甘雨"))
    assert not missing.exists()
