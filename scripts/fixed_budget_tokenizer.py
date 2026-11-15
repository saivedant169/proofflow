"""Count cl100k_base tokens for the frozen ASCII study inputs with stdlib BPE.

The vocabulary and splitting pattern are from OpenAI's tiktoken 0.14.0.
The release bundle carries that project's MIT license.
"""

from base64 import b64decode
from functools import lru_cache
from hashlib import sha256
import re


VOCABULARY_SHA256 = "223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7"
# For ASCII, tiktoken's letter/number classes reduce to these ranges.
PIECES = re.compile(
    r"'(?i:[sdmt]|ll|ve|re)|[^\r\nA-Za-z0-9]?[A-Za-z]+|[0-9]{1,3}|"
    r" ?[^\sA-Za-z0-9]+[\r\n]*|\s+\Z|\s*[\r\n]|\s+(?!\S)|\s", re.ASCII,
)


def token_counter(path):
    data = path.read_bytes()
    if sha256(data).hexdigest() != VOCABULARY_SHA256:
        raise ValueError("Frozen cl100k_base vocabulary digest differs")
    ranks = {b64decode(token, validate=True): int(rank)
             for token, rank in (line.split() for line in data.splitlines())}
    if len(ranks) != 100256 or len(set(ranks.values())) != 100256:
        raise ValueError("Invalid cl100k_base merge rank inventory")

    @lru_cache(maxsize=16384)
    def count_piece(piece):
        piece = piece.encode("ascii")
        if piece in ranks:
            return 1
        parts = [bytes((byte,)) for byte in piece]
        while len(parts) > 1:
            candidates = [(ranks[pair], index, pair) for index, (left, right) in
                          enumerate(zip(parts, parts[1:])) if (pair := left + right) in ranks]
            if not candidates:
                break
            _, index, prior_pair = min(candidates)
            parts[index:index + 2] = [prior_pair]
        return len(parts)

    def count(text):
        if not text.isascii():
            raise ValueError("This offline cl100k_base verifier accepts the frozen ASCII inputs")
        pieces = PIECES.findall(text)
        if sum(map(len, pieces)) != len(text):
            raise ValueError("Unrecognized byte in frozen cl100k_base input")
        return sum(map(count_piece, pieces))

    return count
