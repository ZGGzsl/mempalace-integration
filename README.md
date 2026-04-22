# MemPalace Integration

> AI记忆宫殿集成工具包 —— 让AI拥有人类级的长期记忆

基于 [MemPalace](https://github.com/mempalace/mempalace) 开源项目，提供 Windows 环境下的完整集成方案，包括 FAISS 向量索引（替代 ChromaDB HNSW 崩溃问题）、批量导入工具和 MCP 接入配置。

## ✨ 特性

- **FAISS 替代方案**：解决 ChromaDB 1.5.8 在 Windows 上 HNSW 索引写入崩溃的问题
- **批量导入**：一键将本地文件系统（Markdown/文本）索引入 MemPalace
- **语义搜索**：基于向量相似度的秒级历史信息检索
- **MCP 集成**：29个 MemPalace 工具通过 MCP 协议接入 AI 助手
- **知识图谱**：实体-关系三元组存储，支持时间线查询
- **纯本地运行**：零API调用，数据完全隐私

## 🚀 快速开始

### 安装依赖

```bash
pip install mempalace faiss-cpu chromadb pyyaml
```

### 初始化宫殿

```bash
python -c "from mempalace.config import MempalaceConfig; MempalaceConfig()"
```

### 导入工作区

```bash
python scripts/faiss_import.py --workspace /path/to/your/workspace --palace /path/to/palace
```

### 语义搜索

```python
from mempalace.backends.chroma import ChromaBackend
import faiss
import numpy as np

# 加载 FAISS 索引
index = faiss.read_index("workspace_drawers.faiss")

# 搜索
query_embedding = embedding_function([query])
scores, ids = index.search(np.array(query_embedding).astype('float32'), top_k=5)
```

## 📁 项目结构

```
mempalace-integration/
├── README.md                    # 本文件
├── LICENSE                      # MIT
├── requirements.txt             # Python 依赖
├── scripts/
│   ├── faiss_import.py          # FAISS 批量导入脚本
│   └── batch_import.py          # MemPalace 原生批量导入
└── docs/
    ├── integration-guide.md     # 集成指南
    └── faiss-vs-chroma.md       # FAISS vs ChromaDB 对比
```

## 🔧 FAISS vs ChromaDB

| 特性 | ChromaDB | FAISS |
|------|----------|-------|
| Windows 兼容 | ❌ HNSW写入崩溃 | ✅ 完美运行 |
| 索引速度 | 慢（upsert挂起） | 快（108秒/2400条） |
| 搜索精度 | 高 | 高（IndexFlatIP） |
| 内存占用 | 高 | 低（3.6MB/2400向量） |
| 持久化 | 内置 | 需配合SQLite |

## 🏛️ MemPalace 架构

MemPalace 模拟古希腊"记忆宫殿"空间记忆法：

- **翼楼（Wing）**：人员、项目、系统等大类
- **走廊（Corridor）**：记忆类型分类
- **房间（Room）**：具体想法/事件
- **抽屉（Drawer）**：单条记忆记录

## ⚠️ 已知问题

- ChromaDB 1.5.8 的 `upsert()` 在 Windows 上会触发 HNSW 索引崩溃（exit code 1）
- 本项目用 FAISS + SQLite 替代向量存储，完美绕过此问题

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE)
