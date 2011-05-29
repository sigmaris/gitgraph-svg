from flask import Flask, render_template
import pygit2
from itertools import islice
from operator import itemgetter

app = Flask(__name__)

@app.route('/')
def hello_world():
    repo = pygit2.Repository('/Users/hugh/Source/gitx/.git')
    headref = repo.lookup_reference('HEAD')
    if headref.type == pygit2.GIT_REF_SYMBOLIC:
        headref = headref.resolve()
    walker = islice(repo.walk(headref.sha, pygit2.GIT_SORT_TIME), 100)
    branches = []
    graph = []
    commits = []
    currentY = 0
    for commit in walker:
        try:
            #Find which branch this commit should go on
            pos = branches.index(commit.sha)
        except ValueError:
            #this is the first commit - create a branch
            pos = len(branches)
            branches.append(commit.sha)
            if commit.parents:
                graph.append({'class': 'col_{0}'.format(pos % 8), 'd': [{'type': 'M', 'x': pos, 'y': currentY}], 'parent': commit.parents[0].sha})
            commits.append({'type': 'circle', 'x': pos, 'y': currentY, 'id': commit.sha, 'parents':[x.sha for x in commit.parents]})
        
        for line in list(graph):
            if line['parent'] == commit.sha:
                #draw the closing line into this commit
                #last = line['d'].pop()
                #if last['type'] == 'v' or last['type'] == 'M':
                #    line['d'].append(last)
                line['d'].append({'type': 'L', 'x': pos, 'y': currentY})
                commits.append(dict(line, type='path'))
                graph.remove(line)
            else:
                line['d'].append({'type': 'v', 'y': 1})
        
        delete = True
        if commit.parents:
            append = False
            for parent in commit.parents:
                if parent.sha not in branches:
                    delete = False
                    if not append:
                        #place first parent on this branch
                        branches[pos] = parent.sha
                        graph.append({'class': 'col_{0}'.format(pos % 8), 'd': [{'type': 'M', 'x': pos, 'y': currentY}], 'parent': parent.sha})
                        append = True
                    else:
                        #here we would draw a line to new branch
                        try:
                            insertat = branches.index('')
                            branches[insertat] = parent.sha
                        except ValueError:
                            insertat = len(branches)
                            branches.append(parent.sha)
                        graph.append({'class': 'col_{0}'.format(insertat % 8), 'd': [{'type': 'M', 'x': pos, 'y': currentY}, {'type': 'l', 'x': insertat-pos, 'y': 0.5}], 'parent': parent.sha})
                else:
                    #here we would draw lines to other branches.
                    otherbranch = branches.index(parent.sha)
                    commits.append({'class': 'col_{0}'.format(otherbranch % 8), 'type': 'path', 'd': [{'type': 'M', 'x': pos, 'y': currentY}, {'type': 'l', 'x': otherbranch-pos, 'y': 0.5}], 'parent': parent.sha})
        else:
            del branches[pos] #this branch has no parent, delete it
        commits.append({'type': 'circle', 'x': pos, 'y': currentY, 'id': commit.sha, 'parents':[x.sha for x in commit.parents]})
        textX = len(branches)
        for branch in reversed(branches):
            if branch == '':
                textX -= 1
            else:
                break
        if delete:
            #clear out this branch for future use
            branches[pos] = ''
        commits.append({'type': 'text', 'x': textX, 'y': currentY, 'content': "{msg}".format(msg=commit.message_short)})
        #response += "<br />"
        currentY += 1
    for incomplete in graph:
        incomplete['d'].append({'type': 'V', 'y': currentY})
        commits.append(dict(incomplete, type='path'))
    
    return render_template('base.html', commits=sorted(commits, key=itemgetter('type'), reverse=True))

if __name__ == '__main__':
    app.run(debug=True)
