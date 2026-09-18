import re

STORAGE_KEY_PATTERN = re.compile(r'[0-9a-f]{32}\.blob')


def validate_storage_key(storage_key: str) -> None:
    if STORAGE_KEY_PATTERN.fullmatch(storage_key) is None:
        raise ValueError('storage key is not valid')
