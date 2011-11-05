# -*- coding: utf-8
from __future__ import unicode_literals
import unittest
import tempfile
import subprocess
import os
import shutil
import pygit2
import pprint

import tree_diff

lorem1 = """Lorem ipsum dolor sit amet, consectetur adipisicing elit,
sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi
ut aliquip ex ea commodo consequat.

Duis aute irure dolor in reprehenderit in voluptate velit esse cillum
dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non
proident, sunt in culpa qui officia deserunt mollit anim id est laborum."""

lorem2 = """Etiam non magna id ligula scelerisque consectetur.
Aenean ac erat dictum quam sollicitudin commodo sed eget velit.
Integer vehicula, risus ultrices lobortis volutpat, risus lectus sagittis felis,
non pulvinar purus lacus vulputate nisl. Etiam sit amet hendrerit urna.
Vivamus tristique, massa ac cursus venenatis, lorem purus vulputate quam,
sit amet semper leo risus nec eros. Proin egestas, velit ut aliquam porttitor,
purus purus viverra mauris, quis pretium nunc nunc sit amet lacus.
Integer nec erat tortor. Vivamus massa tellus, vulputate at sagittis et,
ultricies id ipsum. Nullam rhoncus, odio nec aliquam lacinia,
diam dui tincidunt urna, eu bibendum leo nisi sed eros.
Vestibulum ante ipsum primis in faucibus orci luctus et ultrices
posuere cubilia Curae; Duis aliquam, tellus non cursus aliquam,
dolor lacus ornare risus, eget facilisis sapien dolor ut mi.
Duis volutpat dolor id mi tristique scelerisque.
In hac habitasse platea dictumst. Vivamus et dui tellus. Ut diam dolor,
commodo eu laoreet vel, hendrerit at nisi.
Etiam cursus tellus eget purus rhoncus sagittis feugiat eros adipiscing.
Sed varius dapibus enim non sollicitudin.
Nulla accumsan sem quis turpis consequat in accumsan dui ultrices."""

class TreeDiffTest(unittest.TestCase):
    def _get_last_commit(self):
        git = subprocess.Popen(['git', 'log', '-n', '1', '--format=format:%H'],stdout=subprocess.PIPE)
        (output,_) = git.communicate()
        return output.strip()
    
    def _content_equal(self, entry_content, content_str, kind=None):
        entry_list = list(entry_content)
        content_list = content_str.splitlines()
        self.assertEqual(len(entry_list),len(content_list))
        for i in range(len(content_list)):
            entry_line = entry_list[i]
            if kind:
                self.assertEqual(entry_line[0],kind)
            self.assertIn(content_list[i],entry_line[3])
    
    def _content_contains_lines(self, entry_lines, content_lines, kind=None, any_line=False):
        for line in content_lines:
            line_found = False
            for entry_line in entry_lines:
                if kind and entry_line[0] == kind and line in entry_line[3]:
                    line_found = True
                    break
                elif not kind and line in entry_line[3]:
                    line_found = True
                    break
            if not line_found:
                return False
            elif any_line:
                return True
        return True
    
    def _diff_contains(self, diff, kind, name):
        for entry in diff:
            if entry.kind == kind and entry.basename == name:
                return True
        return False;
    
    def _diff_entry_named(self, diff, name):
        for entry in diff:
            if entry.basename == name:
                return entry
        raise KeyError;
        
    def setUp(self):
        self.repo_path = tempfile.mkdtemp()
        self.old_path = os.getcwd()
        os.chdir(self.repo_path)
        subprocess.call(['git','init'])
        subprocess.call(['touch','emptyfile'])
        subprocess.call(['git','add','emptyfile'])
        subprocess.call(['git','commit','-m', 'initial_commit'])
        self.initial_commit_sha = self._get_last_commit()
    
    def tearDown(self):
        os.chdir(self.old_path)
        shutil.rmtree(self.repo_path)
    
    def test_add_file(self):
        """Add an entire file and test that its entire content shows up as added in the diff"""
        prev_sha = self._get_last_commit()
        with open('lorem1.txt','w') as f:
            f.write(lorem1)
        subprocess.call(['git','add','lorem1.txt'])
        subprocess.call(['git','commit','-m', 'lorem1'])
        commit_sha = self._get_last_commit()
        repo = pygit2.Repository(os.path.join(self.repo_path,'.git'))
        td = tree_diff.TreeDiffer(repo)
        old = repo[unicode(prev_sha)]
        new = repo[unicode(commit_sha)]
        diff = td.tree_diff(old.tree, new.tree)
        self.assertTrue(self._diff_contains(diff,tree_diff.DiffEntry.CREATED,'lorem1.txt'))
        diff_entry = self._diff_entry_named(diff, 'lorem1.txt')
        self.assertEqual(diff_entry.basename, 'lorem1.txt')
        self.assertEqual(diff_entry.kind, tree_diff.DiffEntry.CREATED)
        commit_diff = list(td.commitdiff(diff_entry))
        self.assertEqual(len(commit_diff),1)
        commit_diff_entry = commit_diff[0]
        self.assertEqual(commit_diff_entry['name'], 'lorem1.txt')
        self._content_equal(commit_diff_entry['content'],lorem1,tree_diff.DiffEntry.CREATED)

    def test_rem_file(self):
        """Remove an entire file and test that its entire content shows up as deleted in the diff"""
        with open('lorem2.txt','w') as f:
            f.write(lorem2)
        subprocess.call(['git','add','lorem2.txt'])
        subprocess.call(['git','commit','-m', 'lorem2'])
        prev_sha = self._get_last_commit()
        os.remove('lorem2.txt')
        subprocess.call(['git','commit','-a','-m','remove lorem2'])
        commit_sha = self._get_last_commit()
        repo = pygit2.Repository(os.path.join(self.repo_path,'.git'))
        td = tree_diff.TreeDiffer(repo)
        old = repo[unicode(prev_sha)]
        new = repo[unicode(commit_sha)]
        diff = td.tree_diff(old.tree, new.tree)
        self.assertTrue(self._diff_contains(diff,tree_diff.DiffEntry.DELETED,'lorem2.txt'))
        diff_entry = self._diff_entry_named(diff, 'lorem2.txt')
        self.assertEqual(diff_entry.basename, 'lorem2.txt')
        self.assertEqual(diff_entry.kind, tree_diff.DiffEntry.DELETED)
        commit_diff = list(td.commitdiff(diff_entry))
        self.assertEqual(len(commit_diff),1)
        commit_diff_entry = commit_diff[0]
        self.assertEqual(commit_diff_entry['name'], 'lorem2.txt')
        self._content_equal(commit_diff_entry['content'],lorem2,tree_diff.DiffEntry.DELETED)
    
    def test_delete_lines(self):
        """Delete certain lines in a file and test that they show up in the commit diff"""
        with open('lorem2.txt','w') as f:
            f.write(lorem2)
        subprocess.call(['git','add','lorem2.txt'])
        subprocess.call(['git','commit','-m', 'lorem2'])
        #record sha before modification
        prev_sha = self._get_last_commit()
        lorem2_lines = lorem2.splitlines()
        removed_lines = []
        indexes_to_delete = [0,5,8,11,14]
        for n in indexes_to_delete:
            removed_lines.append(lorem2_lines[n])
            del lorem2_lines[n]
        #Write the content again, with certain lines deleted
        with open('lorem2.txt','w') as f:
            f.write('\n'.join(lorem2_lines))
        subprocess.call(['git','add','lorem2.txt'])
        subprocess.call(['git','commit','-m', 'lorem2 modified'])
        #Record the SHA after modification
        commit_sha = self._get_last_commit()
        repo = pygit2.Repository(os.path.join(self.repo_path,'.git'))
        td = tree_diff.TreeDiffer(repo)
        old = repo[unicode(prev_sha)]
        new = repo[unicode(commit_sha)]
        diff = td.tree_diff(old.tree, new.tree)
        self.assertTrue(self._diff_contains(diff,tree_diff.DiffEntry.MODIFIED,'lorem2.txt'))
        diff_entry = self._diff_entry_named(diff, 'lorem2.txt')
        self.assertEqual(diff_entry.basename, 'lorem2.txt')
        self.assertEqual(diff_entry.kind, tree_diff.DiffEntry.MODIFIED)
        commit_diff = list(td.commitdiff(diff_entry))
        self.assertEqual(len(commit_diff),1)
        commit_diff_entry = commit_diff[0]
        self.assertEqual(commit_diff_entry['name'], 'lorem2.txt')
        # we need to get a list from the generator output:
        content_list = list(commit_diff_entry['content'])
        # Assert that the deleted lines show up in the diff
        self.assertTrue(self._content_contains_lines(content_list,removed_lines,tree_diff.DiffEntry.DELETED))
        # Assert that none of the unmodified lines show up as deleted
        self.assertFalse(self._content_contains_lines(content_list,lorem2_lines,tree_diff.DiffEntry.DELETED,True))

    def test_add_lines(self):
        """Add some lines in a file and test that they show up in the commit diff"""
        with open('lorem2.txt','w') as f:
            f.write(lorem2)
        subprocess.call(['git','add','lorem2.txt'])
        subprocess.call(['git','commit','-m', 'lorem2'])
        #record sha before modification
        prev_sha = self._get_last_commit()
        lorem1_lines = lorem1.splitlines()
        lorem2_lines = lorem2.splitlines()
        inserted_lines = []
        indexes_to_insert = [0,3,5,8,10,11]
        for n in indexes_to_insert:
            line = lorem1_lines[n % len(lorem1_lines)]
            inserted_lines.append(line)
            lorem2_lines.insert(n, line)
        #Write the content again, with certain lines inserted
        with open('lorem2.txt','w') as f:
            f.write('\n'.join(lorem2_lines))
        subprocess.call(['git','add','lorem2.txt'])
        subprocess.call(['git','commit','-m', 'lorem2 modified'])
        #Record the SHA after modification
        commit_sha = self._get_last_commit()
        repo = pygit2.Repository(os.path.join(self.repo_path,'.git'))
        td = tree_diff.TreeDiffer(repo)
        old = repo[unicode(prev_sha)]
        new = repo[unicode(commit_sha)]
        diff = td.tree_diff(old.tree, new.tree)
        self.assertTrue(self._diff_contains(diff,tree_diff.DiffEntry.MODIFIED,'lorem2.txt'))
        diff_entry = self._diff_entry_named(diff, 'lorem2.txt')
        self.assertEqual(diff_entry.basename, 'lorem2.txt')
        self.assertEqual(diff_entry.kind, tree_diff.DiffEntry.MODIFIED)
        commit_diff = list(td.commitdiff(diff_entry))
        self.assertEqual(len(commit_diff),1)
        commit_diff_entry = commit_diff[0]
        self.assertEqual(commit_diff_entry['name'], 'lorem2.txt')
        # we need to get a list from the generator output:
        content_list = list(commit_diff_entry['content'])
        # Assert that the inserted lines show up in the diff
        self.assertTrue(self._content_contains_lines(content_list,inserted_lines,tree_diff.DiffEntry.CREATED))
        # Assert that none of the unmodified lines show up as inserted
        self.assertFalse(self._content_contains_lines(content_list,lorem2.splitlines(),tree_diff.DiffEntry.CREATED,True))

if __name__ == '__main__':
    unittest.main()
