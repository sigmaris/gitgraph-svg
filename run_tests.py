# -*- coding: utf-8
from __future__ import unicode_literals
import unittest
import sys

names = ['tree_diff', 'get_objs']
def test_suite():
    modules = ['tests.test_{0}'.format(n) for n in names]
    return unittest.defaultTestLoader.loadTestsFromNames(modules)

if __name__ == '__main__':
    unittest.main(module=__name__, defaultTest='test_suite', argv=sys.argv[:1])
