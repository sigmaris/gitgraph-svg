# -*- coding: utf-8
from __future__ import unicode_literals
from flask import Flask, render_template, request, escape, Markup, json, abort, g
from werkzeug.routing import BaseConverter
from werkzeug import run_simple
from werkzeug.contrib.profiler import ProfilerMiddleware
import pygit2
from pygments import highlight
from pygments.lexers import guess_lexer, guess_lexer_for_filename
from pygments.util import ClassNotFound
from pygments.formatters import HtmlFormatter
from itertools import islice
import imghdr
import re
import tree_diff
import graph
import settings
import ggutils

app = Flask(__name__)
app.config.from_object('settings')

@app.before_request
def open_repo():
    if not hasattr(g, 'repo'):
        g.repo = pygit2.Repository(app.config['REPO_PATH'])

class SHAConverter(BaseConverter):
    def __init__(self, url_map, *items):
        super(SHAConverter, self).__init__(url_map)
        self.regex = '[a-fA-F0-9]{40}'

app.url_map.converters['sha'] = SHAConverter

class RefConverter(BaseConverter):
    def __init__(self, url_map, *items):
        super(RefConverter, self).__init__(url_map)
        self.regex = r'(?:HEAD|refs/(?:heads|remotes|tags)/.+)'

app.url_map.converters['ref'] = RefConverter

@app.route('/')
@app.route('/<ref:ref>')
def display_graph_from_ref(ref=None):
    """Displays the main graph view, starting at a certain ref (a branch, tag or remote branch)."""
    if not ref:
        ref ='HEAD'
    headref = g.repo.lookup_reference(ref)
    
    #Resolve symbolic refs
    if headref.type == pygit2.GIT_REF_SYMBOLIC:
        headref = headref.resolve()
    head_obj = g.repo[headref.oid]
    
    #Fully resolve tags..
    while head_obj.type == pygit2.GIT_OBJ_TAG:
        head_obj = head_obj.target
    
    return display_graph(head_obj, ref)

@app.route('/graph/')
@app.route('/graph/<sha:head>')
def display_graph_from_commit(head=None):
    """Displays the main graph view starting from a certain commit."""
    try:
        if not head:
            head = request.args['head']
        head_obj = g.repo[head]
        return display_graph(head_obj)
    except KeyError:
        abort(404)

def display_graph(head_obj, ref=None):
    """Displays the main graph view, starting at a certain commit object. ref is an optional head or tag to label as 'current'.
    Optionally searches for a certain commit and displays graph from head up to that commit + 10 previous."""
    offset = request.args.get('offset',0,type=int)
    branches = request.args.getlist('branches')
    search_commit = request.args.get('search_commit',None)
    switch_branch = False
    grapher = graph.Grapher()
    
    if search_commit:
        # Try to find commit in current branch
        stop = -1
        for (index, commit) in enumerate(islice(g.repo.walk(head_obj.oid, pygit2.GIT_SORT_TIME), offset, None)):
            if commit.hex == search_commit:
                stop = index + offset + 11
                break
        if stop == -1:
            #at this point, it was not found in the current branch..
            try:
                # try switching to display the graph starting at the searched-for commit
                head_obj = g.repo[search_commit]
                if head_obj.type != pygit2.GIT_OBJ_COMMIT:
                    abort(400)
                else:
                    # Switch branch to start from found commit, reset other things
                    switch_branch = True
                    ref = None
                    branches = []
                    offset = 0
                    stop = 100
            except KeyError:
                # Commit is not even in the repo, return 404.
                abort(404)
    else:
        stop = offset + 100
    
    walker = islice(g.repo.walk(head_obj.oid, pygit2.GIT_SORT_TIME), offset, stop)
    (display_list, existing_branches) = grapher.draw_commits(walker, branches, offset)

    if request.is_xhr:
        if search_commit:
            # Need to load data for the searched/found commit as well
            extra_template_data = dict(display_list.items() + get_commit_templatedata(g.repo, g.repo[search_commit]).items())
        else:
            extra_template_data = display_list
        return render_template('graphonly.html', existing_branches=existing_branches, current_ref=ref, refresh=switch_branch, found_commit=search_commit, **extra_template_data)
    else:
        (tags, branches, remotes) = get_all_refs(g.repo)
        extra_template_data = dict(display_list.items() + get_commit_templatedata(g.repo, head_obj).items())
        return render_template('base.html', tags=tags, branches=branches, remotes=remotes, current_ref=ref, existing_branches=existing_branches, **extra_template_data)

def get_blob(obj, filename_hint=None):
    """Displays the contents of a blob, either in an HTML table with numbered lines, or as binary/plaintext"""
    is_binary = b'\0' in obj.data
    if is_binary:
        # It may be an image file so we try to detect the file type.
        imgtype = imghdr.what(None, obj.data)

    if request.accept_mimetypes.best == 'text/html':
        #TODO: only return a snippet, as here, if this is an AJAX request. Otherwise return a full page?
        if is_binary:
            if imgtype:
                resp = app.make_response(render_template('simple_image.html', filename=filename_hint, sha=obj.hex))
            else:
                resp = app.make_response(Markup('<pre>(Binary file)</pre>'))
        else:
            try:
                if filename_hint:
                    lexer = guess_lexer_for_filename(filename_hint, obj.data, stripnl=False, encoding='chardet')
                else:
                    lexer = guess_lexer(obj.data, stripnl=False, encoding='chardet')
            except ClassNotFound:
                highlighted = escape(ggutils.force_unicode(obj.data))
            else:
                highlighted = highlight(obj.data, lexer, HtmlFormatter(nowrap=True))
            if highlighted:
                resp = app.make_response(render_template(
                    'simple_file.html', sha=obj.hex, filename=filename_hint,
                    content=highlighted.splitlines()))
            else:
                resp = app.make_response(Markup('<pre>(Binary file)</pre>'))
    else:
        resp = app.make_response(obj.data)
        # At this point, we have some data, but no idea what mimetype it should be.
        if is_binary:
            resp.mimetype = {'gif':'image/gif', 'jpeg':'image/jpeg', 'png':'image/png'}.get(imgtype, 'application/octet-stream')
        else:
            resp.mimetype = 'text/plain'
    return resp

def get_blob_diff(repo, old_obj, obj, filename_hint=None):
    """Displays the differences between two versions of a blob, as HTML in a table."""
    if b'\0' in obj.data or b'\0' in old_obj.data:
        # It may be an image file so we try to detect the file type.
        imgtype = imghdr.what(None, obj.data)
        old_imgtype = imghdr.what(None, obj.data)
        if imgtype and old_imgtype:
            #They are presumably both images...
            resp = app.make_response(render_template('simple_image.html', filename=filename_hint, 
                sha=obj.hex, old_sha=old_obj.hex))
        else:
            resp = app.make_response(Markup('<pre>(Binary file)</pre>'))
    else:
        td = tree_diff.TreeDiffer(repo)
        resp = app.make_response(render_template('changed_file.html', file={
            'name': filename_hint,
            'sha': obj.hex,
            'content': td.compare_data(old_obj.data, obj.data, filename_hint)
        }))
    return resp

def get_tree_diff(repo, commit):
    td = tree_diff.TreeDiffer(repo)
    if len(commit.parents) != 1:
        #This appears to be a merge (or the initial commit)
        #TODO: three+ way diff? For now, just show the state after the merge
        to_compare = commit
    else:
        to_compare = commit.parents[0]
    return td.tree_diff(to_compare.tree, commit.tree)

def get_tree(repo, tree):
    """Gets a git (sub)tree in the JSON format required by jsTree"""
    parent_name = request.args.get('parent_name',None)
    td = tree_diff.TreeDiffer(repo)
    tree = td.tree_diff(tree, tree, parent_name)
    resp = app.make_response(json.dumps(tree, cls=tree_diff.DiffEntryEncoder))
    resp.mimetype = 'application/json'
    return resp

def get_commit_templatedata(repo, obj):
    """Gets the required data to feed into the templates which display a single commit, including the tree changes
    in the commit, author and committer info, time and commit messages, and list of changed files. Returns a dict
    with appropriate key names for the templates to use."""
    tree = list(get_tree_diff(repo, obj))
    td = tree_diff.TreeDiffer(repo)
    
    changed_files = []
    for entry in tree:
        if entry.kind != tree_diff.DiffEntry.UNMODIFIED:
            changed_files.extend(td.commitdiff(entry))
    
    message = ggutils.force_unicode(obj.message)
    short_message = ggutils.short_message(message)
    author = (ggutils.force_unicode(obj.author[0]), ggutils.force_unicode(obj.author[1]))
    committer = (ggutils.force_unicode(obj.committer[0]), ggutils.force_unicode(obj.committer[1]))
    author_time = ggutils.format_commit_time(obj.author[2])
    commit_time = ggutils.format_commit_time(obj.committer[2])
    return dict(
        commit=obj,
        message=message,
        title=short_message,
        author=author,
        committer=committer,
        author_time=author_time,
        commit_time=commit_time,
        initial_tree=tree,
        td_encoder=tree_diff.DiffEntryEncoder,
        changed_files=changed_files
    )
    
def get_commit(repo, obj):
    """Displays a single commit as HTML or JSON (used to load a commit's information into the bottom pane)."""
    desired_mimetype = request.accept_mimetypes.best_match(['application/json','text/html'],'text/html')
    templatedata = get_commit_templatedata(repo, obj)
    if desired_mimetype == 'application/json':
        resp = app.make_response(json.dumps(templatedata['initial_tree'], cls=tree_diff.DiffEntryEncoder))
        resp.mimetype = 'application/json'
        return resp
    else:
        #handle HTML view of commits with diffs on each file
        return render_template('commit.html', **templatedata)

REMOTE_REGEX = re.compile(r'^refs/remotes/(?P<remote>[^/]+)/(?P<branch>.+)')
def get_all_refs(repo):
    """Returns a tuple (tags, branches, remotes) where tags and branches are lists
    of tags and local branches, respectively, and remotes is a dict where the keys
    are remote names and the values are lists of branches in that remote."""
    allrefs = repo.listall_references()
    tags = []
    branches = []
    remotes = {}
    for ref in allrefs:
        if ref[:10] == 'refs/tags/':
            tags.append(ref[10:])
        elif ref[:11] == 'refs/heads/':
            branches.append(ref[11:])
        else:
            m = REMOTE_REGEX.match(ref)
            if m:
                remote_name = m.group('remote')
                if remote_name in remotes:
                    remotes[remote_name].append(m.group('branch'))
                else:
                    remotes[remote_name] = [m.group('branch')]
    return (tags, branches, remotes)

@app.route('/sha/<sha:sha>')
def get_sha(sha):
    """Displays either a blob (optionally comparing it to another blob) or
    a single commit."""
    try:
        obj = g.repo[sha]
        if obj.type == pygit2.GIT_OBJ_BLOB:
            filename_hint = request.args.get('filename_hint', None)
            try:
                compare_to = request.args['compare_to']
            except KeyError:
                return get_blob(obj, filename_hint)
            old_obj = g.repo[compare_to]
            if old_obj.type == pygit2.GIT_OBJ_BLOB:
                return get_blob_diff(g.repo, old_obj, obj, filename_hint)
            else:
                abort(400) #can't compare a blob against something else.
        elif obj.type == pygit2.GIT_OBJ_COMMIT:
            return get_commit(g.repo, obj)
        elif obj.type == pygit2.GIT_OBJ_TREE:
            return get_tree(g.repo, obj)
        abort(400)
    except KeyError:
        #SHA not found in repo
        abort(404)

@app.route('/autocomplete')
def autocomplete():
    result = ''
    try:
        prefix = request.args['q']
        obj = g.repo[prefix]
        if obj.type == pygit2.GIT_OBJ_COMMIT:
            result = obj.hex
    except:
        # Exceptions could be raised for nonunique prefixes, nonexistent prefixes,
        # all kinds of things. We don't really care at this point.
        pass
    resp = app.make_response(result)
    resp.mimetype = 'text/plain'
    return resp

if __name__ == '__main__':
    app.run(debug=True)
