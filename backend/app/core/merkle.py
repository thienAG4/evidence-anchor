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
