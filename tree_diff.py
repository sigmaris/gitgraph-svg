# -*- coding: utf-8
from __future__ import unicode_literals
from pygments import highlight
from pygments.lexers import guess_lexer, guess_lexer_for_filename
from pygments.formatters import HtmlFormatter
import pygit2
import difflib
import itertools
import string
import os
from cgi import escape
from flask import json, render_template
import ggutils

DIR_SEP = os.sep

class DiffEntry(object):
    UNMODIFIED = 'unmodified'
    CREATED = 'created'
    DELETED = 'deleted'
    MODIFIED = 'modified'

    @classmethod
    def unmodified(cls, git_entry, parent_name=None):
        return DiffEntry(cls.UNMODIFIED, git_entry, parent_name)

    @classmethod
    def created(cls, git_entry, parent_name=None):
        return DiffEntry(cls.CREATED, git_entry, parent_name)

    @classmethod
    def deleted(cls, git_entry, parent_name=None):
        return DiffEntry(cls.DELETED, git_entry, parent_name)

    def __init__(self, kind, git_entry, parent_name=None):
        self.children = []
        if parent_name:
            self.name = DIR_SEP.join([parent_name,git_entry.name])
        else:
            self.name = git_entry.name
        self.basename = git_entry.name
        self.sha = git_entry.hex
        self.kind = kind
        try:
            git_obj = git_entry.to_object()
            self.type = git_obj.type
        #        for i in range(0, len(git_obj)):
        #            self.children.append(DiffEntry(kind, git_obj[i], parent_name=self.name))
        except KeyError:
            #Probably a reference to other project
            self.type = 'submodule'

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.children[key]
        else:
            raise TypeError

    def __str__(self):
        return "<tree_diff.DiffEntry: {0} {1} sha:{2}>".format(self.basename, self.kind, self.sha)

class Modified(DiffEntry):
    def __init__(self, old_entry, new_entry, children=[], parent_name=None):
        self.children = children
        if parent_name:
            self.name = DIR_SEP.join([parent_name,new_entry.name])
            self.old_name = DIR_SEP.join([parent_name,old_entry.name])
        else:
            self.name = new_entry.name
            self.old_name = old_entry.name
        self.basename = new_entry.name
        self.old_basename = old_entry.name
        self.sha = new_entry.hex
        self.old_sha = old_entry.hex
        self.kind = DiffEntry.MODIFIED
        try:
            git_obj = new_entry.to_object()
            self.type = git_obj.type
        except KeyError:
            #Probably a reference to other project
            self.type = 'submodule'

    def __str__(self):
        return "<tree_diff.DiffEntry: {0} {1} sha:{2} old_sha:{3}>".format(self.basename, self.kind, self.sha, self.old_sha)

def _all_inserted(lines):
    line_number = 1
    for line in lines:
        yield (DiffEntry.CREATED, None, line_number, escape(line.rstrip()))
        line_number = line_number + 1

def _all_deleted(lines):
    line_number = 1
    for line in lines:
        yield (DiffEntry.DELETED, line_number, None, escape(line.rstrip()))
        line_number = line_number + 1

class DiffEntryEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, DiffEntry):
            cls = o.kind

            json_dict = {
                'data': {
                    'title': o.basename,
                    'attr': {
                        'id': 'tree_{0}'.format(o.sha),
                        'href': '#{0}'.format(o.sha)
                    }
                },
                'metadata': {
                    'full_name': o.name
                }
            }

            if hasattr(o, 'content') and o.content:
                json_dict['metadata']['content'] = render_template('changed_file.html', file={'name': o.name, 'content': o.content})

            if hasattr(o, 'old_sha') and o.old_sha:
                json_dict['metadata']['old_sha'] = o.old_sha

            if o.type == pygit2.GIT_OBJ_TREE:
                if o.children:
                    json_dict['children'] = o.children
                typeclass = 'directory'
                if cls == 'modified':
                    json_dict['state'] = 'open'
                else:
                    json_dict['state'] = 'closed'
            elif o.type == pygit2.GIT_OBJ_BLOB:
                json_dict['data']['icon'] = '/static/img/blankpage.png'
                typeclass = 'file'
            else:
                typeclass = 'reference'

            if o.kind == DiffEntry.MODIFIED:
                json_dict['metadata']['old_name'] = o.old_name
                json_dict['metadata']['old_sha'] = o.old_sha

            json_dict['data']['attr']['class'] = '{0} {1}'.format(cls, typeclass)

            return json_dict
        else:
            return json.JSONEncoder.default(self, o)

class TreeDiffer(object):
    def __init__(self, repo, compare_content=False):
        self.repo = repo
        self.content = compare_content
        self.context = 3
        self.ignore_whitespace = True
        self.sm = difflib.SequenceMatcher(lambda line: len(line.strip()) == 0)
        self.formatter = HtmlFormatter(nowrap=True)

    def _markup_diff(self, old, new, opcodes, name=None):
        # Join the lines to make a full document
        old_joined = '\n'.join(old)
        new_joined = '\n'.join(new)
        # Pick the new content to guess the lexer, if necessary
        if name:
            lexer = guess_lexer_for_filename(name, new_joined, stripnl=False)
        else:
            lexer = guess_lexer(new_joined, stripnl=False)
        old_split = highlight(old_joined, lexer, self.formatter).splitlines()
        new_split = highlight(new_joined, lexer, self.formatter).splitlines()
        for tag, i1, i2, j1, j2 in opcodes:
            if tag == 'equal':
                for i in range(i2-i1):
                    yield (DiffEntry.UNMODIFIED, i1 + i + 1, j1 + i + 1, old_split[i1+i].rstrip())
            elif tag == 'delete':
                for i in range(i2-i1):
                    yield (DiffEntry.DELETED, i1 + i + 1, None, old_split[i1+i].rstrip())
            elif tag == 'insert':
                for j in range(j2-j1):
                    yield (DiffEntry.CREATED, None, j1 + j + 1, new_split[j1+j].rstrip())
            elif tag == 'replace':
                for i in range(i2-i1):
                    yield (DiffEntry.DELETED, i1 + i + 1, None, old_split[i1+i].rstrip())
                for j in range(j2-j1):
                    yield (DiffEntry.CREATED, None, j1 + j + 1, new_split[j1+j].rstrip())

    def _set_sm_seqs(self, old, new):
        # Strip all whitespace from lines
        if self.ignore_whitespace:
            self.sm.set_seqs([''.join(s.split()) for s in old],[''.join(s.split()) for s in new])
        else:
            self.sm.set_seqs(old,new)

    def _full_diff(self, old, new, name=None):
        self._set_sm_seqs(old,new)
        changes = self.sm.get_opcodes()
        for change in self._markup_diff(old, new, changes, name):
            yield change

    def _context_diff(self, old, new, name=None):
        self._set_sm_seqs(old,new)
        groups = self.sm.get_grouped_opcodes(self.context)
        separator = False
        for group in groups:
            if separator:
                yield (DiffEntry.UNMODIFIED, None, None, '<hr />')
            for change in self._markup_diff(old, new, group, name):
                yield change
            separator = True

    def commitdiff(self, entry):
        if entry.children:
            for child in entry.children:
                for result in self.commitdiff(child):
                    yield result
        elif entry.type == pygit2.GIT_OBJ_BLOB:
            if entry.kind == DiffEntry.CREATED:
                entry_content = self.repo[entry.sha].read_raw()
                if b'\0' in entry_content:
                    #Binary file
                    if entry.name.endswith(('.png','.jpg','.jpeg','.gif')):
                        yield {'name': entry.name, 'kind':entry.kind, 'sha': entry.sha, 'binary': 'image', 'content': DiffEntry.CREATED}
                    else:
                        yield {'name': entry.name, 'kind':entry.kind, 'sha': entry.sha, 'binary': True, 'content': [(DiffEntry.CREATED,0,0,'(Binary file, created)')]}
                else:
                    yield {'name': entry.name, 'kind':entry.kind, 'sha': entry.sha, 'binary': False, 'content': _all_inserted(ggutils.force_unicode(entry_content).splitlines())}
            elif entry.kind == DiffEntry.DELETED:
                entry_content = self.repo[entry.sha].read_raw()
                if b'\0' in entry_content:
                    #Binary file
                    if entry.name.endswith(('.png','.jpg','.jpeg','.gif')):
                        yield {'name': entry.name, 'kind':entry.kind, 'sha': entry.sha, 'binary': 'image', 'content': DiffEntry.CREATED}
                    else:
                        yield {'name': entry.name, 'kind':entry.kind, 'sha': entry.sha, 'binary': True, 'content': [(DiffEntry.DELETED,0,0,'(Binary file, deleted)')]}
                else:
                    yield {'name': entry.name, 'kind':entry.kind, 'sha': entry.sha, 'binary': False, 'content': _all_deleted(ggutils.force_unicode(entry_content).splitlines())}
            elif entry.kind == DiffEntry.MODIFIED:
                new_content = self.repo[entry.sha].read_raw()
                old_content = self.repo[entry.old_sha].read_raw()
                if b'\0' in new_content or b'\0' in old_content:
                    #Binary file
                    if entry.name.endswith(('.png','.jpg','.jpeg','.gif')):
                        yield {'name': entry.name, 'kind':entry.kind, 'sha': entry.sha, 'binary': 'image', 'content': DiffEntry.MODIFIED, 'old_sha': entry.old_sha }
                    else:
                        yield {'name': entry.name, 'kind':entry.kind, 'sha': entry.sha, 'binary': True, 'content': [(DiffEntry.MODIFIED,0,0,'(Binary file, modified)')]}
                else:
                    new_unicode = ggutils.force_unicode(new_content).splitlines()
                    old_unicode = ggutils.force_unicode(old_content).splitlines()
                    yield {'name': entry.name, 'kind':entry.kind, 'sha': entry.sha, 'binary': False, 'content': self._context_diff(old_unicode,new_unicode,entry.name)}

    def diff(self, old, new, parent_name=None):
        try:
            old_obj = old.to_object()
            old_is_bad = False
        except KeyError:
            old_is_bad = True
        try:
            new_obj = new.to_object()
            new_is_bad = False
        except KeyError:
            new_is_bad = True

        if old_is_bad and new_is_bad:
            return Modified(old, new, [DiffEntry.unmodified(new, parent_name)])
        elif old_is_bad or new_is_bad:
            return Modified(old, new, [DiffEntry.deleted(old, parent_name), DiffEntry.created(new, parent_name)])

        if old_obj.type != new_obj.type:
            return Modified(old, new, [DiffEntry.deleted(old, parent_name), DiffEntry.created(new, parent_name)])

        if parent_name:
            joined_name = DIR_SEP.join([parent_name, new.name])
        else:
            joined_name = new.name

        if old_obj.type == pygit2.GIT_OBJ_TREE:
            return Modified(old, new, self.tree_diff(old_obj,new_obj, joined_name), parent_name)
        else:
            if self.content:
                return self.blob_diff(old,new)
            else:
                return Modified(old, new, [], parent_name)

    def tree_diff(self, old, new, parent_name=None):
        entries = []
        for i in range(0, len(new)):
            #does entry exist in old tree?
            if new[i].name in old:
                old_entry = old[new[i].name]
                if old_entry.oid != new[i].oid:
                    #they have changed.
                    entries.append(self.diff(old_entry, new[i], parent_name))
                else:
                    entries.append(DiffEntry.unmodified(new[i], parent_name))
            else:
                #new subtree is new
                entries.append(DiffEntry.created(new[i], parent_name))
        #now find old entries that are not in new tree
        for i in range(0, len(old)):
            if old[i].name not in new:
                entries.append(DiffEntry.deleted(old[i],parent_name))
        return entries

    def blob_diff(self, old, new):
        old_obj = old.to_object()
        new_obj = new.to_object()
        result = Modified(old, new)
        old_data = old_obj.read_raw()
        if b'\0' in old_data:
            result.content = None
            return result
        result.content = list(self.compare_data(old_data, new_obj.read_raw()))
        return result

    def compare_data(self, old_data, new_data, name=None):
        old_data = ggutils.force_unicode(old_data).splitlines()
        new_data = ggutils.force_unicode(new_data).splitlines()
        return self._full_diff(old_data, new_data, name)
