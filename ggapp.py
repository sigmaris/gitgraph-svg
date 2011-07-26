from flask import Flask, render_template, request, escape, Markup, json, abort
from werkzeug.routing import BaseConverter
from werkzeug import run_simple
from werkzeug.contrib.profiler import ProfilerMiddleware
import pygit2
from itertools import islice
import time
import imghdr
import re
import mimetypes
import types
import tree_diff
import graph
import settings
import ggutils

app = Flask(__name__)
repo = pygit2.Repository(settings.repo_path)

class SHAConverter(BaseConverter):
    def __init__(self, url_map, *items):
        super(SHAConverter, self).__init__(url_map)
        self.regex = '[a-fA-F0-9]{40}'

app.url_map.converters['sha'] = SHAConverter

class RefConverter(BaseConverter):
    def __init__(self, url_map, *items):
        super(RefConverter, self).__init__(url_map)
        self.regex = r'refs/(?:heads|remotes|tags)/.+'

app.url_map.converters['ref'] = RefConverter

@app.route('/')
@app.route('/HEAD')
def display_page():
    return display_graph('HEAD')

@app.route('/<ref:ref>')
def display_graph(ref):
    """Displays the main graph view, starting at a certain ref (a branch, tag or remote branch)"""
    offset = request.args.get('offset',0,type=int)
    headref = repo.lookup_reference(ref)
    grapher = graph.Grapher()
    
    #Resolve symbolic refs
    if headref.type == pygit2.GIT_REF_SYMBOLIC:
        headref = headref.resolve()
    head_obj = repo[headref.sha]
    
    #Fully resolve tags..
    while head_obj.type == pygit2.GIT_OBJ_TAG:
        head_obj = head_obj.target
    
    walker = islice(repo.walk(head_obj.sha, pygit2.GIT_SORT_TIME), offset, offset+100)
    branches = request.args.getlist('branches')
    (display_list, existing_branches) = grapher.draw_commits(walker, branches, offset)
    if request.is_xhr:
        return render_template('graphonly.html', existing_branches=existing_branches, current_ref=ref, **display_list)
    else:
        (tags, branches, remotes) = get_all_refs(repo)
        extra_template_data = dict(display_list.items() + get_commit_templatedata(repo, head_obj).items())
        return render_template('base.html', tags=tags, branches=branches, remotes=remotes, current_ref=ref, existing_branches=existing_branches, **extra_template_data)

def get_blob(obj):
    """Displays the contents of a blob, either in an HTML table with numbered lines, or as binary/plaintext"""
    is_binary = '\0' in obj.data
    if is_binary:
        # It may be an image file so we try to detect the file type.
        imgtype = imghdr.what(None, obj.data)

    if request.accept_mimetypes.best == 'text/html':
        #TODO: only return a snippet, as here, if this is an AJAX request. Otherwise return a full page?
        if is_binary:
            if imgtype:
                resp = app.make_response(render_template('simple_image.html', sha=obj.sha))
            else:
                resp = app.make_response(Markup('<pre>(Binary file)</pre>'))
        else:
            # We need to pass unicode to Jinja2, so convert using UnicodeDammit:
            resp = app.make_response(render_template('simple_file.html', sha=obj.sha, content=ggutils.force_unicode(obj.data).splitlines()))
    else:
        resp = app.make_response(obj.data)
        # At this point, we have some data, but no idea what mimetype it should be.
        if is_binary:
            resp.mimetype = {'gif':'image/gif', 'jpeg':'image/jpeg', 'png':'image/png'}.get(imgtype, 'application/octet-stream')
        else:
            resp.mimetype = 'text/plain'
    return resp

def get_blob_diff(repo, old_obj, obj):
    """Displays the differences between two versions of a blob, as HTML in a table."""
    if '\0' in obj.data or '\0' in old_obj.data:
        resp = app.make_response(Markup('<pre>(Binary file)</pre>'))
    else:
        td = tree_diff.TreeDiffer(repo)
        resp = app.make_response(render_template('changed_file.html', file={'name': '', 'sha':obj.sha, 'content': td.compare_data(old_obj.data, obj.data)}))
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
    
    jsontree = json.dumps(tree, cls=tree_diff.DiffEntryEncoder)
    message = ggutils.force_unicode(obj.message)
    title = ggutils.force_unicode(obj.message_short)
    author = (ggutils.force_unicode(obj.author[0]), ggutils.force_unicode(obj.author[1]))
    committer = (ggutils.force_unicode(obj.committer[0]), ggutils.force_unicode(obj.committer[1]))
    author_time = ggutils.format_commit_time(obj.author[2])
    commit_time = ggutils.format_commit_time(obj.committer[2])
    return dict(commit=obj, message=message, title=title, author=author, committer=committer, author_time=author_time, commit_time=commit_time, initial_tree=jsontree, changed_files=changed_files)
    
def get_commit(repo, obj):
    """Displays a single commit as HTML (used to load a commit's information into the bottom pane)."""
    desired_mimetype = request.accept_mimetypes.best_match(['application/json','text/html'],'text/html')
    templatedata = get_commit_templatedata(repo, obj)
    if desired_mimetype == 'application/json':
        resp = app.make_response(templatedata['initial_tree'])
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
        obj = repo[sha]
        if obj.type == pygit2.GIT_OBJ_BLOB:
            try:
                compare_to = request.args['compare_to']
            except KeyError:
                return get_blob(obj)
            old_obj = repo[compare_to]
            if old_obj.type == pygit2.GIT_OBJ_BLOB:
                return get_blob_diff(repo, old_obj, obj)
            else:
                abort(400) #can't compare a blob against something else.
        elif obj.type == pygit2.GIT_OBJ_COMMIT:
            return get_commit(repo, obj)
        abort(400)
    except KeyError:
        #SHA not found in repo
        abort(404)

if __name__ == '__main__':
    app.run(debug=True)
