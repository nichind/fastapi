class NoID(Exception):
    def __init__(self):
        super().__init__("No ID kwarg found and item has no id attribute.")


class Blacklisted(Exception):
    def __init__(self, key: str, value: str):
        super().__init__(
            f"Value {value} for {key} is blacklisted.",
            "Ignore by setting ignore_blacklist=True",
            sep="\n",
        )


class Duplicate(Exception): ...


class Invalid(Exception): ...


class NotFound(Exception): ...


class NotUnique(Exception): ...


class NoCryptKey(Exception):
    def __init__(self, key: str = "CRYPT_KEY"):
        super().__init__(
            f"No crypt key found. Please set the {key} environment variable."
        )


class NotIknowWhatImDoing(Exception):
    def __init__(self):
        super().__init__("Are you sure you know what you're doing?")
