# FAISS vs ChromaDB 对比

## 问题背景

在 Windows 环境下使用 MemPalace 时，ChromaDB 1.5.8 的 `upsert()` 操作会导致 HNSW 索引写入崩溃（进程 exit code 1）。

经过排查，这是 ChromaDB Rust 侧 HNSW 实现在 Windows 上的兼容性问题，不是数据量或配置问题。

## 对比

| 特性 | ChromaDB | FAISS + SQLite |
|------|----------|----------------|
| **Windows兼容** | ❌ HNSW写入崩溃 | ✅ 完美运行 |
| **索引速度** | 慢/挂起 | 快（108秒/2400条） |
| **搜索精度** | 高 | 高（IndexFlatIP） |
| **内存占用** | 高 | 低（3.6MB/2400向量） |
| **持久化** | 内置 | 需配合SQLite |
| **增量更新** | upsert（但崩溃） | 查重+add |
| **搜索API** | 内置 | 需手动写 |
| **依赖** | chromadb | faiss-cpu + chromadb(embedding only) |

## 方案说明

本方案采用**混合架构**：
- **ChromaDB**: 仅用于 embedding 计算（`DefaultEmbeddingFunction`），384维向量
- **FAISS**: 管理向量索引（`IndexFlatIP`，内积+L2归一化=cosine相似度）
- **SQLite**: 存储 metadata（文件路径、内容、分类信息）

## 索引结构

```
palace/
├── workspace_drawers.faiss      # FAISS向量索引
├── workspace_drawers_meta.sqlite # SQLite元数据
└── _import_done.json             # 导入状态记录
```

## 搜索流程

1. 用 ChromaDB embedding 函数将查询转为向量
2. L2归一化查询向量
3. FAISS `index.search()` 返回 top-K 结果
4. 从 SQLite 取出对应 metadata

## 增量导入

再次运行导入脚本时：
1. 计算每个文件的 MD5 hash
2. 与 SQLite 中已存储的 hash 对比
3. 只导入新增/修改的文件
4. 重复 ID 跳过（幂等性）
