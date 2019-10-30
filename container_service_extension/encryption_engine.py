import base64
import sys

from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes


def encrypt_file(input_file, passwd, output_file):
    """Encrypt the given input file.

    Encryption uses the given password to derive encryption key.
    Encrypted data is written to given output file, if provided else
    outputs to stdout.

    :param str input_file: path to plain-text file
    :param str passwd: password to make encryption key
    :param str output_file: path to cipher-text file
    """
    with open(input_file, 'rb') as infile:
        out_file = None
        try:
            encryptor = Fernet(_derive_key(passwd))
            out_file = open(output_file, 'wb') \
                if output_file else sys.stdout.buffer
            data = infile.read()
            out_file.write(encryptor.encrypt(data))
        finally:
            if out_file and out_file is not sys.stdout.buffer:
                out_file.close()


def decrypt_file(input_file, passwd, output_file):
    """Decrypt the given input file.

    Decryption uses the given password to derive encryption key.
    Decrypted data is written to given output file, if provided, else
    outputs to stdout.

    :param str input_file: path to encrypted file
    :param str passwd: password to make decryption key
    :param str output_file: path to plain-text file
    """
    with open(input_file, 'rb') as infile:
        out_file = None
        try:
            decryptor = Fernet(_derive_key(passwd))
            out_file = open(output_file, 'wb') \
                if output_file else sys.stdout.buffer
            data = infile.read()
            out_file.write(decryptor.decrypt(data))
        finally:
            if out_file and out_file is not sys.stdout.buffer:
                out_file.close()


def decrypt_file_in_memory(input_file, passwd):
    """Decrypt the given input file.

    Decryption uses the given password to derive encryption key.

    :param str input_file: path to encrypted file
    :param str passwd: password to make decryption key

    :return: decrypted data

    :rtype: bytes
    """
    with open(input_file, 'rb') as infile:
        decryptor = Fernet(_derive_key(passwd))
        data = infile.read()
        return decryptor.decrypt(data)


def _derive_key(passwd):
    """Derive a base64 encoded urlsafe digest from password.

    Using the given password, an irreversible hash is derived using
    cryptography algorithm. To make use of this for Fernet encryption,
    it is transformed to base64 encoded urlsafe digest.

    :param str passwd: password to make encryption/decryption key
    :return: hashed password
    :rtype: bytes
    """
    digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
    digest.update(passwd.encode())
    return base64.urlsafe_b64encode(digest.finalize())
