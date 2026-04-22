# MemPalace 集成指南

## 前置条件

- Python 3.9+
- Windows 10/11（已测试）
- 至少 2GB 可用磁盘空间

## 安装步骤

### 1. 安装 MemPalace

```bash
pip install mempalace
```

### 2. 安装 FAISS（替代ChromaDB向量存储）

```bash
pip install faiss-cpu
```

> ⚠️ ChromaDB 1.5.8 在 Windows 上的 `upsert()` 操作会导致 HNSW 索引崩溃（exit code 1）。
> FAISS 是高性能向量搜索库，在 Windows 上完美运行。

### 3. 初始化宫殿

```python
from mempalace.config import MempalaceConfig
config = MempalaceConfig()
# 宫殿默认创建在 ~/.mempalace/palace/
```

### 4. 导入工作区

```bash
python scripts/faiss_import.py \
  --workspace /path/to/your/workspace \
  --palace /path/to/palace
```

参数说明：
- `--workspace`: 要索引的工作区根目录
- `--palace`: MemPalace 宫殿目录
- `--chunk-size`: 文本块最大字符数（默认500）
- `--overlap`: 文本块重叠字符数（默认50）
- `--extensions`: 扫描的文件扩展名（默认.md,.txt,.py,.json,.yaml,.yml,.toml）
- `--skip-dirs`: 跳过的目录（默认node_modules,.git等）

### 5. 语义搜索

```python
import faiss
import numpy as np
import chromadb

# 加载索引
index = faiss.read_index("workspace_drawers.faiss")

# 获取embedding函数
client = chromadb.PersistentClient(path=palace_path)
col = client.get_or_create_collection("drawers")
embed_fn = col._embedding_function

# 搜索
query = "微信自动化"
query_emb = np.array([embed_fn([query])[0]], dtype='float32')
faiss.normalize_L2(query_emb)
scores, ids = index.search(query_emb, 5)
```

## MCP 集成（可选）

如果使用 OpenClaw，可以通过 MCP 协议接入 MemPalace：

### 1. 配置 mcporter

编辑 `~/.mcporter/mcporter.json`：

```json
{
  "mcpServers": {
    "mempalace": {
      "command": "python",
      "args": ["-m", "mempalace.mcp_server", "--palace", "/path/to/palace"],
      "env": {}
    }
  }
}
```

### 2. 重启 Gateway

```bash
openclaw gateway restart
```

### 3. 可用工具（29个）

- 宫殿状态：`mempalace_status`, `mempalace_list_wings`, `mempalace_list_rooms`
- 知识图谱：`mempalace_kg_query`, `mempalace_kg_add`, `mempalace_kg_timeline`
- 抽屉操作：`mempalace_search`, `mempalace_add_drawer`, `mempalace_get_drawer`
- 日记系统：`mempalace_diary_write`, `mempalace_diary_read`
- 宫殿图：`mempalace_traverse`, `mempalace_find_tunnels`
- 设置：`mempalace_hook_settings`, `mempalace_reconnect`

## 性能数据

| 指标 | 数值 |
|------|------|
| 导入速度 | 108秒 / 2400条 |
| 索引大小 | 3.6 MB / 2400向量 |
| 搜索延迟 | <100ms |
| 搜索精度 | cosine相似度 0.48-0.88 |

## 故障排除

### ChromaDB upsert 崩溃
**症状**: `col.upsert()` 执行后进程 exit code 1
**解决**: 使用本项目的 FAISS 方案替代

### FAISS 安装失败
```bash
# Windows 预编译wheel
pip install faiss-cpu --extra-index-url https://download.pytorch.org/whl/cpu
```

### 搜索结果为空
确认 FAISS 索引文件和 SQLite metadata 文件在同一目录下。
