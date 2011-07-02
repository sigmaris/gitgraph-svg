import pygit2
import difflib
import os
from cgi import escape
from flask import json, render_template
from BeautifulSoup import UnicodeDammit
import settings

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
        self.sha = git_entry.sha
        self.kind = kind
        self.reference = False
        try:
            git_obj = git_entry.to_object()
            if git_obj.type == pygit2.GIT_OBJ_TREE:
                for i in range(0, len(git_obj)):
                    self.children.append(DiffEntry(kind, git_obj[i], parent_name=self.name))
        except KeyError:
            #Probably a reference to other project
            self.reference = True

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
        self.sha = new_entry.sha
        self.old_sha = old_entry.sha
        self.kind = DiffEntry.MODIFIED
        self.reference = False

def _open_tag(char):
    return {
        '^': '<span class="replaced">',
        '+': '<ins>',
        '-': '<del>'
    }.get(char,'')

def _close_tag(char):
    return {
        '^': '</span>',
        '+': '</ins>',
        '-': '</del>'
    }.get(char,'')

def _kind(char):
    return {
        '^': DiffEntry.MODIFIED,
        '+': DiffEntry.CREATED,
        '-': DiffEntry.DELETED
    }.get(char,DiffEntry.UNMODIFIED)

def _htmlize_line(line, tags):
    lastchar = None
    n = 0
    for i in range(len(tags)):
        char = tags[i]
        if char != lastchar:
            yield escape(line[n:i]) + _close_tag(lastchar) + _open_tag(char)
            n = i
            lastchar = char
    yield escape(line[n:i+1]) + _close_tag(lastchar) + escape(line[i+1:])

def _increment(line_numbers, char):
    return {
        '?': (line_numbers, line_numbers),
        '+': ((line_numbers[0], line_numbers[1] + 1), (None, line_numbers[1] + 1)),
        '-': ((line_numbers[0] + 1, line_numbers[1]), (line_numbers[0] + 1, None))
    }.get(char,((line_numbers[0] + 1, line_numbers[1] + 1),(line_numbers[0] + 1, line_numbers[1] + 1)))

def _htmlize_diff(lines):
    """Takes the output of difflib.Differ.compare, a sequence of lines with +/-/? prefixes,
    and uses the ? ... lines to tag previous lines with <ins>, <del>, and
    <span class="replaced"> tags to indicate changed character ranges within the lines."""
    i = iter(lines)
    prev = i.next()
    line_numbers = (0,0)
    for line in i:
        if line[:2] == '? ':
            (line_numbers, display) = _increment(line_numbers, prev[0])
            yield (_kind(prev[0]), display[0], display[1], _open_tag(prev[0]) + ''.join(_htmlize_line(prev[2:].rstrip(), line[2:].rstrip())) + _close_tag(prev[0]))
            prev = None
            continue
        elif prev != None:
            (line_numbers, display) = _increment(line_numbers, prev[0])
            yield (_kind(prev[0]), display[0], display[1], _open_tag(prev[0]) + escape(prev[2:].rstrip()) + _close_tag(prev[0]))
        prev = line
    if prev != None:
        (line_numbers, display) = _increment(line_numbers, prev[0])
        yield (_kind(prev[0]), display[0], display[1], _open_tag(prev[0]) + escape(prev[2:].rstrip()) + _close_tag(prev[0]))

def _all_inserted(lines):
    line_number = 1
    for line in lines:
        yield (DiffEntry.CREATED, None, line_number, _open_tag('+') + escape(line.rstrip()) + _close_tag('+'))
        line_number = line_number + 1

def _all_deleted(lines):
    line_number = 1
    for line in lines:
        yield (DiffEntry.DELETED, line_number, None, _open_tag('-') + escape(line.rstrip()) + _close_tag('-'))
        line_number = line_number + 1

def _filter_context(lines, context):
    i = iter(lines)
    context_q = []
    divider = False
    while True:
        try:
            (kind,num_old,num_new,line) = i.next()
            if kind == DiffEntry.CREATED or kind == DiffEntry.DELETED:
                #flush context lines
                if divider:
                    yield (DiffEntry.UNMODIFIED,0,0,'<hr />')
                divider = True
                for ctx_line in context_q:
                    yield ctx_line
                
                #write this line
                yield (kind,num_old,num_new,line)
                
                #write n lines of context
                n = 0
                while n < context:
                    (kind,num_old,num_new,line) = i.next()
                    yield (kind,num_old,num_new,line)
                    if kind != DiffEntry.CREATED and kind != DiffEntry.DELETED:
                        n = n + 1
                context_q = []
            else:
                context_q.append((kind,num_old,num_new,line))
                if len(context_q) > context:
                    del context_q[0]
        except StopIteration:
            break

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
            
            if o.children:
                json_dict['children'] = o.children
                typeclass = 'directory'
                if cls != 'unmodified':
                    json_dict['state'] = 'open'
            else:
                json_dict['data']['icon'] = '/static/img/blankpage.png'
                typeclass = 'file'
            
            if o.kind == DiffEntry.MODIFIED:
                json_dict['metadata']['old_name'] = o.old_name
                json_dict['metadata']['old_sha'] = o.old_sha
            
            if o.reference:
                typeclass = 'reference'
            
            json_dict['data']['attr']['class'] = '{0} {1}'.format(cls, typeclass)
            
            return json_dict
        else:
            return json.JSONEncoder.default(self, o)

class TreeDiffer(object):
    def __init__(self, repo, compare_content=False):
        self.repo = repo
        self.content = compare_content
        self.differ = difflib.Differ()
    
    def commitdiff(self, entry):
        if entry.children:
            for child in entry.children:
                for result in self.commitdiff(child):
                    yield result
        elif not entry.reference:
            if entry.kind == DiffEntry.CREATED:
                entry_content = self.repo[entry.sha].read_raw()
                if '\0' in entry_content:
                    #Binary file
                    yield {'name': entry.name, 'sha': entry.sha, 'content': [(DiffEntry.CREATED,0,0,'(Binary file, created)')]}
                else:
                    yield {'name': entry.name, 'sha': entry.sha, 'content': _all_inserted(UnicodeDammit(entry_content, smartQuotesTo=None).unicode.splitlines(True))}
            elif entry.kind == DiffEntry.DELETED:
                entry_content = self.repo[entry.sha].read_raw()
                if '\0' in entry_content:
                    #Binary file
                    yield {'name': entry.name, 'sha': entry.sha, 'content': [(DiffEntry.DELETED,0,0,'(Binary file, deleted)')]}
                else:
                    yield {'name': entry.name, 'sha': entry.sha, 'content': _all_deleted(UnicodeDammit(entry_content, smartQuotesTo=None).unicode.splitlines(True))}
            elif entry.kind == DiffEntry.MODIFIED:
                #Use the already calculated diff in content?
                if hasattr(entry, 'content'):
                    yield {'name': entry.name, 'sha': entry.sha, 'content': _filter_context(entry.content, 3)}
                else:
                    new_content = self.repo[entry.sha].read_raw()
                    old_content = self.repo[entry.old_sha].read_raw()
                    if '\0' in new_content or '\0' in old_content:
                        #Binary file
                        yield {'name': entry.name, 'sha': entry.sha, 'content': [(DiffEntry.MODIFIED,0,0,'(Binary file, modified)')]}
                    else:
                        new_unicode = UnicodeDammit(new_content, smartQuotesTo=None).unicode.splitlines(True)
                        old_unicode = UnicodeDammit(old_content, smartQuotesTo=None).unicode.splitlines(True)
                        yield {'name': entry.name, 'sha': entry.sha, 'content': _filter_context(_htmlize_diff(self.differ.compare(old_unicode,new_unicode)), 3)}
        return
    
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
                if old_entry.sha != new[i].sha:
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
        if '\0' in old_data:
            result.content = None
            return result
        result.content = list(self.compare_data(old_data, new_obj.read_raw()))
        return result
    
    def compare_data(self, old_data, new_data):
        old_data = UnicodeDammit(old_data, smartQuotesTo=None).unicode
        new_data = UnicodeDammit(new_data, smartQuotesTo=None).unicode
        compared = self.differ.compare(old_data.splitlines(True), new_data.splitlines(True))
        return _htmlize_diff(compared)
        
def test():
    repo = pygit2.Repository(settings.repo_path)
    head = repo[repo.lookup_reference('HEAD').resolve().sha]
    oneback = head.parents[0]
    td = TreeDiffer(True)
    return json.dumps(td.tree_diff(oneback.tree, head.tree), cls=DiffEntryEncoder)