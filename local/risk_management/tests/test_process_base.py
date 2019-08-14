from odoo.tests import common
from .common import TestProcessCases, TestProcessIOCases


class TestBusinessProcess(TestProcessCases):
    def Setup(self):
        super(TestBusinessProcess, self).setUp()


class TestBusinessProcessIO(TestProcessIOCases):
    def Setup(self):
        super(TestBusinessProcessIO, self).setUp()
