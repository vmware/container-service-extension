import base64
import os
import sys

from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

import container_service_extension.common.constants.server_constants as constants  # noqa: E501


def encrypt_file(input_file, passwd, output_file):
    """Encrypt the given input file.

    Encryption uses the given password to derive encryption key.
    Encrypted data are written to given output file, if provided, else
    outputs to stdout.

    :param str input_file: path to plain-text file
    :param str passwd: password to make encryption key
    :param str output_file: path to cipher-text file
    """
    with open(input_file, 'rb') as infile:
        out_file = None
        try:
            data = infile.read()
            salt = os.urandom(constants.SALT_SIZE)
            encryptor = Fernet(_derive_pbkdf2_key(passwd, salt))
            encrypted_content = encryptor.encrypt(data)
            output_data = salt + encrypted_content

            out_file = open(output_file, 'wb') \
                if output_file else sys.stdout.buffer
            out_file.write(output_data)
        finally:
            if out_file and out_file is not sys.stdout.buffer:
                out_file.close()


def decrypt_file(input_file, passwd, output_file):
    """Decrypt the given input file.

    Decryption uses the given password to derive encryption key.
    Decrypted data data written to given output file, if provided, else
    outputs to stdout.

    :param str input_file: path to encrypted file
    :param str passwd: password to make decryption key
    :param str output_file: path to plain-text file

    :raises cryptography.fernet.InvalidToken: wrong password for decryption
    raises this error.
    """
    out_file = None
    try:
        decrypted_data = get_decrypted_file_contents(input_file, passwd)
        out_file = open(output_file, 'wb') \
            if output_file else sys.stdout.buffer
        out_file.write(decrypted_data)
    finally:
        if out_file and out_file is not sys.stdout.buffer:
            out_file.close()


def get_decrypted_file_contents(input_file, passwd):
    """Decrypt the given input file.

    Decryption uses the given password to derive encryption key.

    :param str input_file: path to encrypted file
    :param str passwd: password to make decryption key

    :return: decrypted data

    :rtype: bytes

    :raises cryptography.fernet.InvalidToken: wrong password for decryption
    raises this error.
    """
    with open(input_file, 'rb') as infile:
        data = infile.read()
        salt = data[:constants.SALT_SIZE]
        encrypted_content = data[constants.SALT_SIZE:]
        decryptor = Fernet(_derive_pbkdf2_key(passwd, salt))
        try:
            decrypted_content = decryptor.decrypt(encrypted_content)
        except InvalidToken:
            sha256_decryptor = Fernet(_derive_sha256_key(passwd))
            decrypted_content = sha256_decryptor.decrypt(data)
            sys.stdout.write("Configuration file encrypted with CSE 2.6 "
                             "found. Please consider decrypting this file "
                             "and re-encrypting it with CSE 3.0 for enhanced "
                             "security. \n")
        return decrypted_content


def _derive_pbkdf2_key(passwd, salt):
    """Derive a base64 encoded urlsafe PBKDF2 key.

    :param str passwd: password to make the key
    :param bytes salt: random bytes used for the key

    :return: key
    :rtype: bytes
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256,
        length=constants.PBKDF2_OUTPUT_SIZE,
        salt=salt,
        iterations=constants.PBKDF2_ITERATIONS,
        backend=default_backend())
    key = kdf.derive(passwd.encode())

    return base64.urlsafe_b64encode(key)


def _derive_sha256_key(passwd):
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
