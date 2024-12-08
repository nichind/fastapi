class NoID(Exception): ...


class Blacklisted(Exception): ...


class Duplicate(Exception): ...


class Invalid(Exception): ...


class NotFound(Exception): ...


class NotUnique(Exception): ...


class NoCryptKey(Exception):
    def __init__(self):
        super().__init__(
            "No crypt key found. Please set the CRYPT_KEY environment variable."
        )
