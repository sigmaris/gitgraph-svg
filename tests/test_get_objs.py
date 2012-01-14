# -*- coding: utf-8
from __future__ import unicode_literals
from webtests import WebTestCase, SPAN_REGEX
import json

README_BLOB = 'ed2bcb304be4a6f532f59a832b00199d989d140c'
COMMIT_HEX = '2869f404fd1fb345bfe86471dbcfba85abaa9f10'
TREE_HEX = 'bbf1a98f3ab299ac8e00a041b481a7bf08c5317a'

class GetObjectsTestCase(WebTestCase):
    def test_get_blob(self):
        resp = self.app.get('/sha/{0}'.format(README_BLOB))
        highlight_stripped = SPAN_REGEX.sub('', resp.data)
        self.assertIn('libgit2 - the Git linkable library',highlight_stripped)
    
    def test_get_commit(self):
        resp = self.app.get('/sha/{0}'.format(COMMIT_HEX))
        highlight_stripped = SPAN_REGEX.sub('', resp.data)
        self.assertIn('transport: Add `git_transport_valid_url`', highlight_stripped)
        self.assertIn('Vicent Marti', highlight_stripped)
        self.assertIn('tanoku@gmail.com', highlight_stripped)
        self.assertIn('parent_6616e207506d2c3ac287a3c5e631b3d442464bed', highlight_stripped)
        self.assertIn('include/git2/transport.h', highlight_stripped)
        self.assertIn('src/transport.c', highlight_stripped)
        self.assertIn(' * Return whether a string is a valid transport URL', highlight_stripped)
        self.assertIn('/* TODO: Parse &quot;example.com:project.git&quot; as an SSH URL */', highlight_stripped)
    
    def test_get_tree(self):
        resp = self.app.get('/sha/{0}'.format(TREE_HEX))
        tree_data = json.loads(resp.data)
        self.assertEqual(len(tree_data), 18)
        self.assertIn('data', tree_data[0])
        self.assertEqual(tree_data[0]['data']['title'], '.HEADER')
        self.assertEqual(tree_data[0]['data']['attr']['id'], 'tree_fd8430bc864cfcd5f10e5590f8a447e01b942bfe')
