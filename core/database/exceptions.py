class NoID(Exception): ...


class Blacklisted(Exception): ...


class Duplicate(Exception): ...


class Invalid(Exception): ...


class NotFound(Exception): ...


class NotUnique(Exception): ...


class NoCryptKey(Exception):
    """CRYPT_KEY env is not set and no crypt key was provided"""
