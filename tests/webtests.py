# -*- coding: utf-8
from __future__ import unicode_literals
import unittest
import os
import ggapp
import re
import __main__

SPAN_REGEX = re.compile(r'</?span[^>]*>')

class WebTestCase(unittest.TestCase):
    def setUp(self):
        ggapp.app.config['TESTING'] = True
        mainpath = __main__.__file__
        ggapp.app.config['REPO_PATH'] = os.path.join(mainpath,'testdata','libgit2.git')
        self.app = ggapp.app.test_client()
