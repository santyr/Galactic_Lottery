# galactic_lottery_secp256k1_same_line.py

import sys
import hashlib
import base58
from math import log, ceil
from bitarray import bitarray

# Python bindings for libsecp256k1
import secp256k1

# Keys from KeyDatabase.py — assumed to be a list of hex-encoded strings.
from KeyDatabase import satoshi_keys


def hash_key(key_bytes: bytes) -> bytes:
    """
    Hashes a public key (in bytes) using SHA-256, then RIPEMD-160.
    Returns the raw RIPEMD-160 bytes.
    """
    sha_result = hashlib.sha256(key_bytes).digest()
    ripe = hashlib.new('ripemd160')
    ripe.update(sha_result)
    return ripe.digest()


def private_key_to_wif(private_key_bytes: bytes, compressed: bool = True) -> str:
    """
    Converts a 32-byte private key (raw bytes) into WIF (Wallet Import Format).
    """
    # Ensure the private key is 32 bytes. If not, pad or handle accordingly.
    if len(private_key_bytes) != 32:
        raise ValueError("Private key must be 32 bytes.")

    # Add a prefix byte (0x80 for mainnet private key).
    prefix = b'\x80' + private_key_bytes

    # If the private key will correspond to a compressed public key, append 0x01.
    if compressed:
        prefix += b'\x01'

    # Calculate the double SHA-256 checksum (first 4 bytes).
    checksum = hashlib.sha256(hashlib.sha256(prefix).digest()).digest()[:4]

    # Create WIF by Base58 encoding the prefix + checksum.
    return base58.b58encode(prefix + checksum).decode('utf-8')


def create_bloom_filter(keys: list[bytes], error_rate: float = 0.1):
    """
    Creates a Bloom filter for the given list of byte-strings (keys).
    :param keys: List of keys in bytes.
    :param error_rate: Desired false-positive probability.
    :return: (bloom_filter, num_hashes)
    """
    num_keys = len(keys)
    # Calculate the optimal size (in bits) for the Bloom filter.
    bit_size = ceil(-num_keys * log(error_rate) / (log(2) ** 2))
    # Calculate the optimal number of hash functions.
    num_hashes = ceil(bit_size / num_keys * log(2))

    bloom_filter = bitarray(bit_size)
    bloom_filter.setall(False)

    # Insert each key into the Bloom filter using multiple hash functions.
    for key in keys:
        for i in range(num_hashes):
            digest = hashlib.sha256(i.to_bytes(2, 'big') + key).digest()
            index = int.from_bytes(digest, byteorder='big') % bit_size
            bloom_filter[index] = True

    return bloom_filter, num_hashes


def is_key_match(candidate_key: bytes, bloom_filter: bitarray, num_hashes: int) -> bool:
    """
    Checks whether a candidate key might be in the Bloom filter.
    :param candidate_key: The key (in bytes) to check.
    :param bloom_filter: Bloom filter bitarray.
    :param num_hashes: Number of hash functions used to build the filter.
    :return: Boolean indicating potential membership.
    """
    size = len(bloom_filter)
    for i in range(num_hashes):
        digest = hashlib.sha256(i.to_bytes(2, 'big') + candidate_key).digest()
        index = int.from_bytes(digest, byteorder='big') % size
        if not bloom_filter[index]:
            return False
    return True


def try_keys(
    bloom_filter: bitarray,
    num_hashes: int,
    attempts: int,
    satoshi_set: set[bytes],
    print_interval: int = 10_000
):
    """
    Continuously generates private keys using secp256k1, checks them against the Bloom filter,
    and then verifies membership in the known Satoshi keys set.
    Prints progress on the same line every 'print_interval' attempts (using carriage return).
    :param bloom_filter: The Bloom filter.
    :param num_hashes: Number of hash functions used.
    :param attempts: Starting attempt count.
    :param satoshi_set: A set of raw bytes for the known Satoshi keys.
    :param print_interval: Print progress every 'print_interval' attempts.
    :return: WIF string if found, None otherwise.
    """
    while True:
        # Generate a random private key using libsecp256k1
        priv_key_obj = secp256k1.PrivateKey()  # random
        priv_key_bytes = priv_key_obj.private_key  # 32 raw bytes

        # Get the compressed public key (33 bytes).
        pub_key_bytes = priv_key_obj.pubkey.serialize(compressed=True)

        # Hash the compressed public key with SHA-256 then RIPEMD-160.
        hashed_key = hash_key(pub_key_bytes)

        # Check Bloom filter first (fast).
        if is_key_match(hashed_key, bloom_filter, num_hashes):
            # Double-check in the actual set (no false positives).
            if hashed_key in satoshi_set:
                # Convert private key bytes to WIF.
                wif_key = private_key_to_wif(priv_key_bytes)
                print(f"\nWinning private key found: {wif_key}")
                return wif_key

        attempts += 1

        # Refresh progress on the same line every 'print_interval' attempts.
        if attempts % print_interval == 0:
            # '\r' returns cursor to the start of the line; end='' avoids new line.
            print(f"\r{attempts} attempts made so far...", end='', flush=True)


def main():
    # Starting attempt counter.
    attempts = 0

    # Convert known Satoshi keys (stored as hex in KeyDatabase) into raw bytes.
    satoshi_keys_bytes = [bytes.fromhex(k) for k in satoshi_keys]
    # Create a set for quick membership checks.
    satoshi_set = set(satoshi_keys_bytes)

    # Create a Bloom filter with default error_rate=0.1 (adjust as desired).
    bloom_filter, num_hashes = create_bloom_filter(satoshi_keys_bytes, error_rate=0.1)

    # Try keys forever (or until a match is found, which is astronomically unlikely).
    found_key = try_keys(bloom_filter, num_hashes, attempts, satoshi_set, print_interval=10_000)

    if found_key:
        print(f"\nScript finished — match found: {found_key}")
        sys.exit(0)
    else:
        print("\nNo matching private key found (almost certain this will never happen).")
        sys.exit(1)


if __name__ == "__main__":
    main()
