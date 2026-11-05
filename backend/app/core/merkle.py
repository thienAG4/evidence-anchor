import hashlib

LEAF_PREFIX = b"\x00"  # lá = SHA256(0x00 ‖ recordHash)
NODE_PREFIX = b"\x01"  # tách nút trong khỏi lá, để nút trong không giả làm lá được


def record_leaf(record_hash: str) -> str:
    return hashlib.sha256(LEAF_PREFIX + bytes.fromhex(record_hash)).hexdigest()


def node_hash(left: str, right: str) -> str:
    """SHA256(0x01 ‖ trái ‖ phải), nối 32 byte nhị phân."""
    return hashlib.sha256(NODE_PREFIX + bytes.fromhex(left) + bytes.fromhex(right)).hexdigest()


def build_tree(leaves: list[str]) -> tuple[str, list[list[dict]]]:
    """Gốc Merkle + đường dẫn chứng minh cho từng lá (theo thứ tự đưa vào).

    Tầng lẻ thì nút cuối được đẩy thẳng lên (không nhân đôi). 1 lá: gốc = lá, đường dẫn rỗng.
    Mỗi bước: {"side": "L"|"R", "hash"} — hash anh em nằm bên trái hay bên phải.
    """
    if not leaves:
        raise ValueError("Cần ít nhất 1 lá để dựng cây Merkle.")
    proofs: list[list[dict]] = [[] for _ in leaves]
    level = [(h, [i]) for i, h in enumerate(leaves)]  # (hash, các lá nằm dưới nút này)
    while len(level) > 1:
        next_level = []
        for j in range(0, len(level) - 1, 2):
            (left, left_ids), (right, right_ids) = level[j], level[j + 1]
            for i in left_ids:
                proofs[i].append({"side": "R", "hash": right})
            for i in right_ids:
                proofs[i].append({"side": "L", "hash": left})
            next_level.append((node_hash(left, right), left_ids + right_ids))
        if len(level) % 2:
            next_level.append(level[-1])
        level = next_level
    return level[0][0], proofs


def build_batch(groups: list[list[str]]) -> tuple[str, list[list[dict]]]:
    """Cây hai tầng của một đợt neo. groups: recordHash theo từng nhóm (người ghi).

    Tầng dưới: mỗi nhóm một cây trên lá SHA256(0x00 ‖ recordHash) -> subRoot. Tầng trên: cây trên các subRoot, subRoot
    vào như một nút (không thêm 0x00). Trả root + mỗi lá {leafHash, groupPath, batchPath}, cùng thứ tự groups.
    """
    sub_roots, group_items = [], []
    for record_hashes in groups:
        leaves = [record_leaf(h) for h in record_hashes]
        sub_root, paths = build_tree(leaves)
        sub_roots.append(sub_root)
        group_items.append(list(zip(leaves, paths)))
    root, batch_paths = build_tree(sub_roots)
    return root, [[{"leafHash": leaf, "groupPath": path, "batchPath": batch_paths[g]} for leaf, path in items]
                  for g, items in enumerate(group_items)]


def walk(node: str, proof: list[dict]) -> str:
    """Đi từ một nút lên theo đường dẫn."""
    for step in proof:
        node = node_hash(step["hash"], node) if step["side"] == "L" else node_hash(node, step["hash"])
    return node


def verify_proof(leaf: str, proof: list[dict], root: str) -> bool:
    return walk(leaf, proof) == root


def verify_batch_proof(record_hash: str, group_path: list[dict], batch_path: list[dict], root: str) -> bool:
    """recordHash -> lá -> subRoot (groupPath) -> root đợt (batchPath)."""
    return walk(walk(record_leaf(record_hash), group_path), batch_path) == root
