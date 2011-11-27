# -*- coding: utf-8
from __future__ import unicode_literals
import ggutils
from operator import itemgetter

class Grapher(object):
    def new_edge(self, column, y, parent, extra_classes=[], override_color=None):
        if override_color != None:
            color = override_color
        else:
            color = column
        return {'order': y, 'class': 'col_{0} {1}'.format(color % 8, ' '.join(extra_classes)), 'd': [{'type': 'M', 'x': column, 'y': y}], 'parent': parent}

    def new_node(self, column, y, sha, parents, extra_classes=[]):
        result = {'x': column, 'y': y, 'id': sha, 'parents': parents}
        if extra_classes:
            result['class'] = ' '.join(extra_classes)
        return result

    def place_commit(self, commit, y):
        try:
            #Find which branch this commit should go on
            pos = self.branches.index(commit.hex)
        except ValueError:
            #this is the first commit - create a branch
            pos = len(self.branches)
            self.branches.append(commit.hex)
            if self.graph and self.display_list:
                if commit.parents:
                    self.graph.append(self.new_edge(pos, y, commit.parents[0].hex))
                self.display_list['nodes'].append(self.new_node(pos, y, commit.hex, [x.hex for x in commit.parents]))
        return pos

    def finish_edges(self, sha, x, y):
        for line in list(self.graph):
            if line['parent'] == sha:
                #draw the closing line into this commit
                line['d'].append({'type': 'L', 'x': x, 'y': y})
                self.display_list['edges'].append(line)
                self.graph.remove(line)
            else:
                line['d'].append({'type': 'v', 'y': 1})

    def process_parents(self, parents, x, y):
        """ This function creates edges in the graph for each of a node's parents.
        It places the first parent in the same 'lane' as the current commit,
        then inserts the remaining parents in whatever blank spaces are available."""
        append = False
        delete = True
        for parent in parents:
            if parent.hex not in self.branches:
                delete = False
                if not append:
                    #place first parent on this branch
                    self.branches[x] = parent.hex
                    if self.graph != None:
                        self.graph.append(self.new_edge(x, y, parent.hex))
                    append = True
                else:
                    #here we would draw a line to new branch
                    try:
                        insertat = self.branches.index('')
                        self.branches[insertat] = parent.hex
                    except ValueError:
                        insertat = len(self.branches)
                        self.branches.append(parent.hex)
                    if self.graph != None:
                        edge = self.new_edge(x, y, parent.hex, override_color=insertat)
                        edge['d'].append({'type': 'l', 'x': insertat-x, 'y': 0.5})
                        self.graph.append(edge)
            elif self.display_list != None:
                #here we draw lines to other existing branches.
                otherbranch = self.branches.index(parent.hex)
                edge = self.new_edge(x, y, parent.hex, override_color=otherbranch)
                edge['d'].append({'type': 'l', 'x': otherbranch-x, 'y': 0.5})
                self.display_list['edges'].append(edge)
        return delete

    def draw_commits(self, walker, existing_branches=[], currentY=0):
        """ This is the main function that draws the commits taken from a walk of the repository
        (the walker object). It can optionally start with a number of existing branches and at a
        given y-position. It returns a tuple with the first member being a dictionary of the nodes,
        edges, and labels to be drawn, and the second member being a list of branches at the bottom
        of the graph (used for continuing the graph later)"""
        column = 0
        self.graph = [] #stores a list of edges which aren't finished being drawn.
        # display_list is a structure holding what should actually be drawn on the screen.
        self.display_list = {'edges':[], 'nodes':[], 'labels':[], 'authors':[], 'dates':[]}
        # branches is an array of strings used to track where branches should go.
        # A SHA hash in some position indicates that commit should be the next one in that position.
        # An empty string indicates the position is blank and can be filled with a new branch if one appears.
        self.branches = []
        for existing_branch in existing_branches:
            if existing_branch:
                # start drawing these existing branches
                self.graph.append(self.new_edge(column, currentY, existing_branch))
            column = column + 1
            # Keep track of existing branches
            self.branches.append(existing_branch)
        for commit in walker:
            pos = self.place_commit(commit, currentY)
            
            # Do any edges need finishing off?
            self.finish_edges(commit.hex, pos, currentY)
            
            #The delete flag determines whether to mark this branch as deleted
            if commit.parents:
                delete = self.process_parents(commit.parents, pos, currentY)
            else:
                del self.branches[pos] #this branch has no parent, delete it
                delete = False
            
            #TODO: make this more elegant?
            textX = len(self.branches)
            for branch in reversed(self.branches):
                if branch == '':
                    textX -= 1
                else:
                    break
            textX = max(textX,1)
            
            if delete:
                #clear out this branch for future use
                self.branches[pos] = ''
            
            # Create a node representing this commit and the message, author and time labels
            self.display_list['nodes'].append(self.new_node(pos, currentY, commit.hex, [x.hex for x in commit.parents]))
            label_text = ggutils.force_unicode(ggutils.short_message(commit.message))
            self.display_list['labels'].append({'x': textX, 'y': currentY, 'content': label_text, 'sha': commit.hex})
            self.display_list['authors'].append({'x': 0, 'y': currentY, 'content': ggutils.force_unicode(commit.author.name), 'sha': commit.hex})
            self.display_list['dates'].append({'x': 0, 'y': currentY, 'content': ggutils.format_commit_time(commit.commit_time), 'sha': commit.hex})
            currentY += 1
        for incomplete in self.graph:
            incomplete['d'].append({'type': 'V', 'y': currentY})
            self.display_list['edges'].append(incomplete)
        self.display_list['edges'].sort(key=itemgetter('order'))
        return (self.display_list, self.branches)
