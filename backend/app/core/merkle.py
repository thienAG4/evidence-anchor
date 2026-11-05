import hashlib

NODE_PREFIX = b"\x01"  # tách nút trong khỏi lá, để nút trong không giả làm bundle hash được


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


def verify_proof(leaf: str, proof: list[dict], root: str) -> bool:
    """Đi từ lá lên theo đường dẫn, phải ra đúng gốc đã neo."""
    current = leaf
    for step in proof:
        current = node_hash(step["hash"], current) if step["side"] == "L" else node_hash(current, step["hash"])
    return current == root


# ---------------------------------------------------------------- Cây theo bản ghi 164 byte (RFC 6962)
# build_tree ở trên đã chia cây đúng RFC 6962 (tách ở lũy thừa của 2 lớn nhất nhỏ hơn n, không nhân đôi lá);
# phần dưới chỉ thêm tiền tố lá 0x00 và gom hai tầng. build_tree giữ nguyên cho các lần neo bundle cũ.

LEAF_PREFIX = b"\x00"


def record_leaf(record_hash: bytes) -> str:
    """Lá Merkle của một bản ghi: SHA256(0x00 ‖ recordHash) (tài liệu kỹ thuật 5.4.1)."""
    return hashlib.sha256(LEAF_PREFIX + record_hash).hexdigest()


def build_two_level(records: list[tuple[int, str, bytes]]) -> dict:
    """Cây hai tầng của một đợt: tầng dưới gom bản ghi theo người ghi, tầng trên gom các sub_root.

    records: [(seq, actorRef hex, recordHash)], thuộc cùng một đợt. Nhóm xếp theo seq nhỏ nhất của nhóm,
    bản ghi trong nhóm xếp theo seq. sub_root đưa thẳng vào tầng trên như một nút (không thêm 0x00 lần nữa).
    Trả về groups, root và đường dẫn {seq: {"groupPath", "batchPath"}} để đưa vào biên nhận.
    """
    if not records:
        raise ValueError("Cần ít nhất 1 bản ghi để dựng cây.")
    by_actor: dict[str, list[tuple[int, bytes]]] = {}
    for seq, actor, record_hash in sorted(records):
        by_actor.setdefault(actor, []).append((seq, record_hash))
    groups = sorted(by_actor.items(), key=lambda item: item[1][0][0])

    group_views, sub_roots, group_proofs = [], [], []
    for actor, items in groups:
        leaves = [record_leaf(h) for _, h in items]
        sub_root, proofs = build_tree(leaves)
        group_views.append({"actorRef": actor, "seqs": [s for s, _ in items], "leaves": leaves, "subRoot": sub_root})
        sub_roots.append(sub_root)
        group_proofs.append(proofs)
    root, batch_proofs = build_tree(sub_roots)

    paths = {}
    for g, (view, proofs) in enumerate(zip(group_views, group_proofs)):
        for seq, group_path in zip(view["seqs"], proofs):
            paths[seq] = {"groupPath": group_path, "batchPath": batch_proofs[g]}
    return {"groups": group_views, "root": root, "paths": paths}


def verify_record_proof(record_hash: bytes, group_path: list[dict], batch_path: list[dict], root: str) -> bool:
    """Bản ghi -> lá -> (groupPath) sub_root -> (batchPath) root đã neo."""
    current = record_leaf(record_hash)
    for step in group_path:
        current = node_hash(step["hash"], current) if step["side"] == "L" else node_hash(current, step["hash"])
    return verify_proof(current, batch_path, root)
