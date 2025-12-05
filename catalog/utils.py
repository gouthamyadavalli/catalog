import hashlib

def generate_sequence_id(sequence: str) -> str:
    """
    Generate a deterministic ID for a sequence using SHA-256.
    Normalizes the sequence to uppercase before hashing.
    """
    normalized_seq = sequence.strip().upper()
    return hashlib.sha256(normalized_seq.encode('utf-8')).hexdigest()

def canonicalize_sequence(sequence: str) -> str:
    """
    Simple canonicalization: uppercase and remove whitespace.
    """
    return "".join(sequence.split()).upper()
