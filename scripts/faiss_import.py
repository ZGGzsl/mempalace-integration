# -*- coding: utf-8 -*-
"""
FAISS批量导入脚本 —— 将工作区文件索引入MemPalace语义搜索
解决ChromaDB 1.5.8在Windows上HNSW索引写入崩溃的问题

用法：
  python faiss_import.py --workspace /path/to/workspace --palace /path/to/palace
  python faiss_import.py --workspace /path/to/workspace --palace /path/to/palace --chunk-size 500
"""
import os, sys, json, time, argparse, hashlib, sqlite3
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

def parse_args():
    parser = argparse.ArgumentParser(description='FAISS批量导入工作区到MemPalace')
    parser.add_argument('--workspace', required=True, help='工作区根目录')
    parser.add_argument('--palace', required=True, help='MemPalace宫殿目录')
    parser.add_argument('--chunk-size', type=int, default=500, help='文本块最大字符数')
    parser.add_argument('--overlap', type=int, default=50, help='文本块重叠字符数')
    parser.add_argument('--extensions', default='.md,.txt,.py,.json,.yaml,.yml,.toml', help='扫描的文件扩展名')
    parser.add_argument('--skip-dirs', default='node_modules,.git,__pycache__,.openclaw-yuanbao-backup', help='跳过的目录')
    return parser.parse_args()

def read_file(path):
    """尝试多种编码读取文件"""
    for enc in ['utf-8', 'utf-8-sig', 'gbk', 'latin-1']:
        try:
            with open(path, 'r', encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    return ''

def chunk_text(text, chunk_size=500, overlap=50):
    """将文本按段落和长度分块"""
    paragraphs = text.split('\n\n')
    chunks = []
    current = ''
    for para in paragraphs:
        if len(current) + len(para) + 2 > chunk_size and current:
            chunks.append(current.strip())
            # overlap: keep last N chars
            current = current[-overlap:] + '\n\n' + para
        else:
            current = current + '\n\n' + para if current else para
    if current.strip():
        chunks.append(current.strip())
    return chunks if chunks else [text[:chunk_size]]

def compute_id(filepath, chunk_index):
    """生成唯一ID"""
    raw = f"{filepath}:{chunk_index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]

def main():
    args = parse_args()
    workspace = os.path.abspath(args.workspace)
    palace = os.path.abspath(args.palace)
    extensions = set(args.extensions.split(','))
    skip_dirs = set(args.skip_dirs.split(','))

    # Init ChromaDB embedding function
    print("[1] 初始化Embedding函数...")
    import chromadb
    client = chromadb.PersistentClient(path=palace)
    col = client.get_or_create_collection("drawers", metadata={"hnsw:space": "cosine"})
    embed_fn = col._embedding_function
    print("[1] OK")

    # Init FAISS
    print("[2] 初始化FAISS索引...")
    import faiss
    import numpy as np

    faiss_path = os.path.join(palace, 'workspace_drawers.faiss')
    meta_path = os.path.join(palace, 'workspace_drawers_meta.sqlite')

    # Load or create FAISS index
    if os.path.exists(faiss_path):
        index = faiss.read_index(faiss_path)
        print(f"[2] 加载已有索引: {index.ntotal} 条向量")
    else:
        index = faiss.IndexFlatIP(384)  # ChromaDB default dim
        print("[2] 创建新索引")

    # Init SQLite metadata
    meta_db = sqlite3.connect(meta_path)
    meta_db.execute('''CREATE TABLE IF NOT EXISTS metadata (
        id TEXT PRIMARY KEY,
        filepath TEXT,
        chunk_index INTEGER,
        content TEXT,
        wing TEXT DEFAULT '',
        room TEXT DEFAULT '',
        added_at TEXT,
        file_hash TEXT
    )''')
    meta_db.commit()

    # Scan workspace
    print(f"[3] 扫描工作区: {workspace}")
    files = []
    for root, dirs, filenames in os.walk(workspace):
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext in extensions:
                files.append(os.path.join(root, fname))
    print(f"[3] 找到 {len(files)} 个文件")

    # Import
    print("[4] 开始导入...")
    t0 = time.time()
    total_new, total_skip, total_fail = 0, 0, 0
    batch_embeddings = []
    batch_metas = []

    for i, filepath in enumerate(files):
        try:
            content = read_file(filepath)
            if not content or len(content.strip()) < 20:
                continue

            rel_path = os.path.relpath(filepath, workspace).replace('\\', '/')
            file_hash = hashlib.md5(content.encode()).hexdigest()

            chunks = chunk_text(content, args.chunk_size, args.overlap)

            for ci, chunk in enumerate(chunks):
                chunk_id = compute_id(rel_path, ci)

                # Check if already imported (same hash = unchanged)
                existing = meta_db.execute(
                    'SELECT file_hash FROM metadata WHERE id=?', (chunk_id,)
                ).fetchone()

                if existing and existing[0] == file_hash:
                    total_skip += 1
                    continue

                # Compute embedding
                try:
                    emb = embed_fn([chunk])[0]
                    emb_np = np.array([emb], dtype='float32')
                    # Normalize for cosine similarity via inner product
                    faiss.normalize_L2(emb_np)
                except Exception as e:
                    print(f"  [X] Embedding失败 {rel_path}#{ci}: {e}")
                    total_fail += 1
                    continue

                batch_embeddings.append(emb_np[0])
                batch_metas.append({
                    'id': chunk_id,
                    'filepath': rel_path,
                    'chunk_index': ci,
                    'content': chunk[:5000],
                    'wing': os.path.dirname(rel_path).replace('/', '_')[:50] if os.path.dirname(rel_path) else 'root',
                    'room': os.path.splitext(os.path.basename(rel_path))[0][:50],
                    'added_at': datetime.now(timezone.utc).isoformat(),
                    'file_hash': file_hash,
                })
                total_new += 1

        except Exception as e:
            print(f"  [X] 读取失败 {filepath}: {e}")
            total_fail += 1

        if (i + 1) % 100 == 0:
            print(f"  进度: {i+1}/{len(files)} 文件, 新增{total_new}块")

    # Batch write
    if batch_embeddings:
        print(f"[5] 写入 {len(batch_embeddings)} 条向量...")
        emb_matrix = np.vstack(batch_embeddings).astype('float32')
        index.add(emb_matrix)
        faiss.write_index(index, faiss_path)

        for meta in batch_metas:
            meta_db.execute(
                'INSERT OR REPLACE INTO metadata (id,filepath,chunk_index,content,wing,room,added_at,file_hash) VALUES (?,?,?,?,?,?,?,?)',
                (meta['id'], meta['filepath'], meta['chunk_index'], meta['content'],
                 meta['wing'], meta['room'], meta['added_at'], meta['file_hash'])
            )
        meta_db.commit()

    elapsed = time.time() - t0
    print(f"\n[DONE] {elapsed:.1f}s | 新增={total_new} 跳过={total_skip} 失败={total_fail}")
    print(f"FAISS索引: {index.ntotal} 条向量, {os.path.getsize(faiss_path)/1024/1024:.1f}MB")

    # Save result
    result = {
        "new": total_new, "skipped": total_skip, "failed": total_fail,
        "total_vectors": index.ntotal, "elapsed_s": elapsed,
        "timestamp": datetime.now().isoformat()
    }
    result_path = os.path.join(palace, '_import_done.json')
    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"结果保存到 {result_path}")

    meta_db.close()

if __name__ == '__main__':
    main()
