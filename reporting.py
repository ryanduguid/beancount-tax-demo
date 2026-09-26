"""Keep terminal reports readable without interpreting supplied text as controls."""

import sys


def safe_text(value):
    return "".join(char if char.isprintable() else char.encode("unicode_escape").decode("ascii")
                   for char in str(value))


def configure_output():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
