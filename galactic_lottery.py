import hashlib
from ecdsa import SigningKey, SECP256k1
from ecdsa.util import number_to_string
import base58
from KeyDatabase import satoshi_keys  # Import keys from KeyDatabase.py

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

def try_keys(attempts):
    for _ in range(100):  # Checking 100 keys
        sk = SigningKey.generate(curve=SECP256k1)
        vk = sk.verifying_key
        compressed_public_key = vk.to_string("compressed").hex()
        hashed_key = hash_key(compressed_public_key)
        if hashed_key in satoshi_keys:
            wif_key = private_key_to_wif(sk.privkey.secret_multiplier)
            print(f"\rWinning private key found: {wif_key}", end='', flush=True)
            return wif_key
        print(f"\r{attempts + _ + 1} attempts made so far. Current key: {sk.to_string().hex()}", end='', flush=True)
    return None

def main():
    attempts = 0
    found_key = None
    while found_key is None:
        found_key = try_keys(attempts)
        attempts += 100

if __name__ == "__main__":
    main()
