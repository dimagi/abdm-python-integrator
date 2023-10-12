import hashlib
from base64 import b64encode
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

from fidelius import CryptoController, DecryptionRequest, EncryptionRequest, KeyMaterial

CRYPTO_ALGORITHM = 'ECDH'
CURVE = 'Curve25519'
KEY_MATERIAL_EXPIRY = 60 * 60  # in seconds


class ABDMCrypto:
    """
    Wrapper class to perform cryptography operations as per ABDM policy.
    """

    def __init__(self, key_material_dict=None, use_x509_for_transfer=False):
        self.key_material = (ABDMKeyMaterial.from_dict(key_material_dict) if key_material_dict
                             else self._generate_key_material())
        self.transfer_material = self._get_transfer_material(use_x509_for_transfer)

    @staticmethod
    def _generate_key_material():
        key_material = KeyMaterial.generate()
        return ABDMKeyMaterial(
            public_key=key_material.public_key,
            private_key=key_material.private_key,
            nonce=key_material.nonce,
            x509_public_key=key_material.x509_public_key,
        )

    def _get_transfer_material(self, use_x509_for_transfer=False):
        """
        Generates a format to be transferred as per ABDM policy.
        """
        return {
            'cryptoAlg': CRYPTO_ALGORITHM,
            'curve': CURVE,
            'dhPublicKey': {
                'expiry': (datetime.utcnow() + timedelta(seconds=KEY_MATERIAL_EXPIRY)).isoformat(),
                'parameters': CURVE,
                'keyValue': (self.key_material.x509_public_key if use_x509_for_transfer
                             else self.key_material.public_key)
            },
            'nonce': self.key_material.nonce
        }

    def encrypt(self, data, peer_transfer_material):
        encryption_request = EncryptionRequest(
            string_to_encrypt=data,
            sender_nonce=self.key_material.nonce,
            requester_nonce=peer_transfer_material['nonce'],
            sender_private_key=self.key_material.private_key,
            requester_public_key=peer_transfer_material['dhPublicKey']['keyValue']
        )
        return CryptoController.encrypt(encryption_request)

    def decrypt(self, data, peer_transfer_material):
        decryption_request = DecryptionRequest(
            encrypted_data=data,
            requester_nonce=self.key_material.nonce,
            sender_nonce=peer_transfer_material['nonce'],
            requester_private_key=self.key_material.private_key,
            sender_public_key=peer_transfer_material['dhPublicKey']['keyValue']
        )
        return CryptoController.decrypt(decryption_request)

    @staticmethod
    def generate_checksum(data):
        return b64encode(hashlib.md5(data.encode('utf-8')).digest()).decode()


@dataclass(frozen=True)
class ABDMKeyMaterial:
    public_key: str
    private_key: str
    nonce: str
    x509_public_key: str

    @staticmethod
    def from_dict(data):
        return KeyMaterial(
            public_key=data['public_key'],
            private_key=data['private_key'],
            nonce=data['nonce'],
            x509_public_key=data['x509_public_key'],
        )

    def as_dict(self):
        return asdict(self)
