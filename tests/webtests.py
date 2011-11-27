# -*- coding: utf-8
from __future__ import unicode_literals
import unittest
import os
import ggapp
import __main__

class WebTestCase(unittest.TestCase):
    def setUp(self):
        ggapp.app.config['TESTING'] = True
        mainpath = __main__.__file__
        ggapp.app.config['REPO_PATH'] = os.path.join(mainpath,'testdata','libgit2.git')
        self.app = ggapp.app.test_client()
