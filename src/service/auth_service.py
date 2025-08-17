import base64
import hmac
import hashlib
from typing import Optional
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
from logger.logger import Logger
logger = Logger.getLogger()

from config.config import API_KEYS

class AuthService:
    _instance = None
    _initialized = False
    
    def __new__(cls, encryption_key: str = None, signing_key: str = None):
        if cls._instance is None:
            cls._instance = super(AuthService, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, encryption_key: str = None, signing_key: str = None):
        if not self._initialized:
            # 필수 값들이 없으면 오류 발생
            if encryption_key is None:
                logger.error("[AuthService] ENCRYPTION_KEY is missing.")
                raise ValueError("ENCRYPTION_KEY must be provided either as parameter or environment variable")
            if signing_key is None:
                logger.error("[AuthService] SIGNING_KEY is missing.")
                raise ValueError("SIGNING_KEY must be provided either as parameter or environment variable")
            if len(encryption_key) != 32:
                logger.error(f"[AuthService] ENCRYPTION_KEY length is {len(encryption_key)} (must be 32 bytes)")
                raise ValueError("Encryption key must be 32 bytes (AES-256)")
            self.encryption_key = encryption_key.encode() if isinstance(encryption_key, str) else encryption_key
            self.signing_key = signing_key.encode() if isinstance(signing_key, str) else signing_key
            AuthService._initialized = True

    def _encrypt_user_id(self, user_id: str) -> str:
        logger.debug(f"[AuthService] Encrypting user_id: {user_id}")
        iv = get_random_bytes(16)
        cipher = AES.new(self.encryption_key, AES.MODE_CBC, iv)
        ciphertext = cipher.encrypt(pad(user_id.encode(), AES.block_size))
        full = iv + ciphertext
        enc = base64.urlsafe_b64encode(full).decode()
        logger.debug(f"[AuthService] Encrypted user_id to: {enc}")
        return enc

    def _decrypt_user_id(self, encrypted_b64: str) -> str:
        logger.debug(f"[AuthService] Decrypting user_id: {encrypted_b64}")
        full = base64.urlsafe_b64decode(encrypted_b64.encode())
        iv, ciphertext = full[:16], full[16:]
        cipher = AES.new(self.encryption_key, AES.MODE_CBC, iv)
        decrypted = unpad(cipher.decrypt(ciphertext), AES.block_size)
        user_id = decrypted.decode()
        logger.debug(f"[AuthService] Decrypted user_id to: {user_id}")
        return user_id

    def _sign(self, enc_user_id: str) -> str:
        logger.debug(f"[AuthService] Signing encrypted user_id: {enc_user_id}")
        sig = hmac.new(self.signing_key, enc_user_id.encode(), hashlib.sha256).hexdigest()
        logger.debug(f"[AuthService] Signature: {sig}")
        return sig

    def generate(self, user_id: str) -> str:
        enc_user_id = self._encrypt_user_id(user_id)
        signature = self._sign(enc_user_id)
        token = f"{enc_user_id}:{signature}"
        logger.info(f"[AuthService] Token generated: {user_id}")
        return token

    def verify(self, token: str) -> Optional[str]:
        try:
            enc_user_id, sig = token.strip().split(":", 1)
            expected_sig = self._sign(enc_user_id)
            if not hmac.compare_digest(expected_sig, sig): 
                return False
            if token in API_KEYS:
                user_id = self._decrypt_user_id(enc_user_id)
                return user_id
            else:
                return False
        except Exception as e:
            return False
