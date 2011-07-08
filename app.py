from flask import Flask, render_template, request, escape, Markup, json
from BeautifulSoup import UnicodeDammit
from werkzeug.routing import BaseConverter
from werkzeug import run_simple
from werkzeug.contrib.profiler import ProfilerMiddleware
import pygit2
from itertools import islice
from operator import itemgetter
import re
import types
import tree_diff
import settings

app = Flask(__name__)
repo = pygit2.Repository(settings.repo_path)

def new_edge(column, y, parent, extra_classes=[], override_color=None):
    if override_color:
        color = override_color
    else:
        color = column
    return {'order': y, 'class': 'col_{0} {1}'.format(color % 8, ' '.join(extra_classes)), 'd': [{'type': 'M', 'x': column, 'y': y}], 'parent': parent}

def new_node(column, y, sha, parents, extra_classes=[]):
    result = {'x': column, 'y': y, 'id': sha, 'parents': parents}
    if extra_classes:
        result['class'] = ' '.join(extra_classes)
    return result

def place_commit(commit, branches, y, graph = None, display_list = None):
    try:
        #Find which branch this commit should go on
        pos = branches.index(commit.sha)
    except ValueError:
        #this is the first commit - create a branch
        pos = len(branches)
        branches.append(commit.sha)
        if graph and display_list:
            if commit.parents:
                graph.append(new_edge(pos, y, commit.parents[0].sha))
            display_list['nodes'].append(new_node(pos, y, commit.sha, [x.sha for x in commit.parents]))
    return pos

def finish_edges(graph, display_list, sha, x, y):
    for line in list(graph):
        if line['parent'] == sha:
            #draw the closing line into this commit
            line['d'].append({'type': 'L', 'x': x, 'y': y})
            display_list['edges'].append(line)
            graph.remove(line)
        else:
            line['d'].append({'type': 'v', 'y': 1})

def process_parents(parents, branches, x, y, graph=None, display_list=None):
    append = False
    delete = True
    for parent in parents:
        if parent.sha not in branches:
            delete = False
            if not append:
                #place first parent on this branch
                branches[x] = parent.sha
                if graph != None:
                    graph.append(new_edge(x, y, parent.sha))
                append = True
            else:
                #here we would draw a line to new branch
                try:
                    insertat = branches.index('')
                    branches[insertat] = parent.sha
                except ValueError:
                    insertat = len(branches)
                    branches.append(parent.sha)
                if graph != None:
                    edge = new_edge(x, y, parent.sha, override_color=insertat)
                    edge['d'].append({'type': 'l', 'x': insertat-x, 'y': 0.5})
                    graph.append(edge)
        elif display_list != None:
            #here we draw lines to other branches.
            otherbranch = branches.index(parent.sha)
            edge = new_edge(x, y, parent.sha, override_color=otherbranch)
            edge['d'].append({'type': 'l', 'x': otherbranch-x, 'y': 0.5})
            display_list['edges'].append(edge)
    return delete

def draw_commits(walker, existing_branches=[], currentY=0):
    column = 0
    graph = []
    display_list = {'edges':[], 'nodes':[], 'labels':[]}
    branches = []
    for existing_branch in existing_branches:
        if existing_branch:
            graph.append(new_edge(column, currentY, existing_branch))
        column = column + 1
        branches.append(existing_branch)
    for commit in walker:
        pos = place_commit(commit, branches, currentY, graph, display_list)
        
        finish_edges(graph, display_list, commit.sha, pos, currentY)
        
        #The delete flag determines whether to mark this branch as deleted
        if commit.parents:
            delete = process_parents(commit.parents, branches, pos, currentY, graph, display_list)
        else:
            del branches[pos] #this branch has no parent, delete it
            delete = False
        
        display_list['nodes'].append(new_node(pos, currentY, commit.sha, [x.sha for x in commit.parents]))
        
        #TODO: make this more elegant?
        textX = len(branches)
        for branch in reversed(branches):
            if branch == '':
                textX -= 1
            else:
                break
        textX = max(textX,1)
        
        if delete:
            #clear out this branch for future use
            branches[pos] = ''
        label_text = UnicodeDammit(commit.message_short, smartQuotesTo=None).unicode
        display_list['labels'].append({'x': textX, 'y': currentY, 'content': label_text, 'sha': commit.sha})
        currentY += 1
    for incomplete in graph:
        incomplete['d'].append({'type': 'V', 'y': currentY})
        display_list['edges'].append(incomplete)
    display_list['edges'].sort(key=itemgetter('order'))
    return (display_list, branches)

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
def display_page():
    return display_graph('HEAD')

@app.route('/<ref:ref>')
def display_graph(ref):
    offset = request.args.get('offset',0,type=int)
    headref = repo.lookup_reference(ref)
    
    #Resolve symbolic refs
    if headref.type == pygit2.GIT_REF_SYMBOLIC:
        headref = headref.resolve()
    head_obj = repo[headref.sha]
    
    #Fully resolve tags..
    while head_obj.type == pygit2.GIT_OBJ_TAG:
        head_obj = head_obj.target
    
    walker = islice(repo.walk(head_obj.sha, pygit2.GIT_SORT_TIME), offset, offset+100)
    branches = request.args.getlist('branches')
    (display_list, existing_branches) = draw_commits(walker, branches, offset)
    if request.is_xhr:
        if offset == 0:
            return render_template('graphonly.html', replace=True, initial_tree=tree_diff.get_tree_diff(head_obj.sha), existing_branches=existing_branches, current_ref=ref, **display_list)
        else:
            return render_template('graphonly.html', replace=False, existing_branches=existing_branches, current_ref=ref, **display_list)
    else:
        (tags, branches, remotes) = get_all_refs(repo)    
        return render_template('base.html', tags=tags, branches=branches, remotes=remotes, current_ref=ref, initial_tree=tree_diff.get_tree_diff(head_obj.sha), existing_branches=existing_branches, **display_list)

def get_blob(obj):
    desired_mimetype = request.accept_mimetypes.best_match(['text/plain','text/html'],'text/html')
    if desired_mimetype == 'text/html':
        #TODO: only return a snippet, as here, if this is an AJAX request. Otherwise return a full page?
        if '\0' in obj.data:
            resp = app.make_response(Markup('<pre>(Binary file)</pre>'))
        else:
            # We need to pass unicode to Jinja2, so convert using UnicodeDammit:
            resp = app.make_response(render_template('simple_file.html', sha=obj.sha, content=UnicodeDammit(obj.data, smartQuotesTo=None).unicode.splitlines()))
    else:
        if '\0' in obj.data:
            resp = app.make_response('(Binary file)')
        else:
            resp = app.make_response(obj.data)
        resp.mimetype = 'text/plain'
    return resp

def get_blob_diff(repo, old_obj, obj):
    desired_mimetype = request.accept_mimetypes.best_match(['text/plain','text/html'],'text/html')
    if desired_mimetype == 'text/html':
        if '\0' in obj.data or '\0' in old_obj.data:
            resp = app.make_response(Markup('<pre>(Binary file)</pre>'))
        else:
            td = tree_diff.TreeDiffer(repo)
            resp = app.make_response(render_template('changed_file.html', sha=obj.sha, file={'name': '', 'content': td.compare_data(old_obj.data, obj.data)}))
    else:
        resp = app.make_response("Plain text diff not supported yet")
        resp.mimetype = 'text/plain'
    return resp


def get_commit(repo, obj):
    #TODO: handle merges with > 1 parent
    oneback = obj.parents[0]
    td = tree_diff.TreeDiffer(repo)
    tree = list(td.tree_diff(oneback.tree, obj.tree))
    
    changed_files = []
    for entry in tree:
        if entry.kind != tree_diff.DiffEntry.UNMODIFIED:
            changed_files.extend(td.commitdiff(entry))
    
    jsontree = json.dumps(tree, cls=tree_diff.DiffEntryEncoder)
    desired_mimetype = request.accept_mimetypes.best_match(['application/json','text/html'],'text/html')
    if desired_mimetype == 'application/json':
        resp = app.make_response(jsontree)
        resp.mimetype = 'application/json'
        return resp
    else:
        #handle HTML view of commits with diffs on each file
        return render_template('commit.html', initial_tree=jsontree, changed_files=changed_files)

REMOTE_REGEX = re.compile(r'^refs/remotes/(?P<remote>[^/]+)/(?P<branch>.+)')
def get_all_refs(repo):
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
        flask.abort(404)

if __name__ == '__main__':
    #app = ProfilerMiddleware(app, sort_by=('calls','time'))
    app.run(debug=True)
    #run_simple('localhost', 5000, app, use_reloader=True, use_debugger=True)
