# -*- coding: utf-8
from __future__ import unicode_literals
from webtests import WebTestCase
import json

README_BLOB = 'ed2bcb304be4a6f532f59a832b00199d989d140c'
COMMIT_HEX = '2869f404fd1fb345bfe86471dbcfba85abaa9f10'
TREE_HEX = 'bbf1a98f3ab299ac8e00a041b481a7bf08c5317a'

class GetObjectsTestCase(WebTestCase):
    def test_get_blob(self):
        resp = self.app.get('/sha/{0}'.format(README_BLOB))
        self.assertIn('libgit2 - the Git linkable library',resp.data)
    
    def test_get_commit(self):
        resp = self.app.get('/sha/{0}'.format(COMMIT_HEX))
        self.assertIn('transport: Add `git_transport_valid_url`', resp.data)
        self.assertIn('Vicent Marti', resp.data)
        self.assertIn('tanoku@gmail.com', resp.data)
        self.assertIn('parent_6616e207506d2c3ac287a3c5e631b3d442464bed', resp.data)
        self.assertIn('include/git2/transport.h', resp.data)
        self.assertIn('src/transport.c', resp.data)
        self.assertIn(' * Return whether a string is a valid transport URL', resp.data)
        self.assertIn('/* TODO: Parse "example.com:project.git" as an SSH URL */', resp.data)
    
    def test_get_tree(self):
        resp = self.app.get('/sha/{0}'.format(TREE_HEX))
        tree_data = json.loads(resp.data)
        self.assertEqual(len(tree_data), 18)
        self.assertIn('data', tree_data[0])
        self.assertEqual(tree_data[0]['data']['title'], '.HEADER')
        self.assertEqual(tree_data[0]['data']['attr']['id'], 'tree_fd8430bc864cfcd5f10e5590f8a447e01b942bfe')
