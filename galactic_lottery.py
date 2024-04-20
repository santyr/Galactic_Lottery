import hashlib
from ecdsa import SigningKey, SECP256k1
from ecdsa.util import number_to_string
import base58
from KeyDatabase import satoshi_keys  # Import keys from KeyDatabase.py
from bitarray import bitarray
from math import log, ceil
import sys

def hash_key(key):
    sha = hashlib.sha256()
    sha.update(key.encode())
    sha_result = sha.hexdigest()
    ripe = hashlib.new('ripemd160')
    ripe.update(sha_result.encode())
    return ripe.hexdigest()

def private_key_to_wif(private_key, compressed=True):
    # Convert the private key from integer to a 32-byte big-endian binary
    pk_bytes = number_to_string(private_key, SECP256k1.order)
    # Add a prefix byte (0x80 for mainnet private key)
    prefix = b'\x80' + pk_bytes
    # If the private key will correspond to a compressed public key, append 0x01
    if compressed:
        prefix += b'\x01'
    # Calculate checksum: first 4 bytes of SHA256(SHA256(prefix))
    checksum = hashlib.sha256(hashlib.sha256(prefix).digest()).digest()[:4]
    # Create WIF by Base58 encoding the prefix + checksum
    return base58.b58encode(prefix + checksum).decode('utf-8')

def create_bloom_filter(keys, error_rate=0.1):
    num_keys = len(keys)
    # Calculate the optimal size of the bloom filter based on the number of keys and desired error rate
    bit_size = ceil(-num_keys * log(error_rate) / (log(2) ** 2))
    # Calculate the optimal number of hash functions based on the size of the bloom filter and number of keys
    num_hashes = ceil(bit_size / num_keys * log(2))
    bloom_filter = bitarray(bit_size)
    bloom_filter.setall(0)
    for key in keys:
        for i in range(num_hashes):
            digest = hashlib.sha256((str(i) + key).encode()).digest()
            index = int.from_bytes(digest, byteorder='big') % bit_size
            bloom_filter[index] = 1
    return bloom_filter, num_hashes

def is_key_match(key, bloom_filter, num_hashes):
    for i in range(num_hashes):
        digest = hashlib.sha256((str(i) + key).encode()).digest()
        index = int.from_bytes(digest, byteorder='big') % len(bloom_filter)
        if not bloom_filter[index]:
            return False
    return True

def try_keys(bloom_filter, num_hashes, attempts):
    while True:
        sk = SigningKey.generate(curve=SECP256k1)
        vk = sk.verifying_key
        compressed_public_key = vk.to_string("compressed").hex()
        hashed_key = hash_key(compressed_public_key)
        if is_key_match(hashed_key, bloom_filter, num_hashes):
            if hashed_key in satoshi_keys:
                wif_key = private_key_to_wif(sk.privkey.secret_multiplier)
                print(f"\rWinning private key found: {wif_key}", end='', flush=True)
                return wif_key
        attempts += 1
        print(f"\r{attempts} attempts made so far. Current key: {sk.to_string().hex()}", end='', flush=True)

def main():
    attempts = 0
    bloom_filter, num_hashes = create_bloom_filter(satoshi_keys)
    found_key = try_keys(bloom_filter, num_hashes, attempts)
    if found_key:
        print(f"\nWinning private key found: {found_key}")
        sys.exit(0)
    else:
        print("\nNo matching private key found.")

if __name__ == "__main__":
    main()
