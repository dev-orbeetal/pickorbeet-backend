"""Work around Django 5.0 template copying on Python 3.14.

Python 3.14 super() proxies cannot gain attributes. Django 5.0's
BaseContext.__copy__ does copy(super()) and then sets .dicts, which crashes
every Jazzmin admin page.
"""
import sys


def apply():
    if sys.version_info < (3, 14):
        return

    from django.template.context import BaseContext

    def __copy__(self):
        duplicate = self.__class__.__new__(self.__class__)
        duplicate.__dict__ = self.__dict__.copy()
        duplicate.dicts = self.dicts[:]
        return duplicate

    BaseContext.__copy__ = __copy__
