# -*- coding: utf-8
from __future__ import unicode_literals
from BeautifulSoup import UnicodeDammit
import time

# Convention states that commit messages should begin with a 50 char title
GIT_SHORT_MESSAGE = 50

def format_commit_time(timestamp):
    return time.strftime('%d %B %Y %H:%M', time.localtime(timestamp))

def force_unicode(text):
    return UnicodeDammit(text, smartQuotesTo=None).unicode

def short_message(message):
    first_line = message.strip().splitlines()[0]
    if len(first_line) <= GIT_SHORT_MESSAGE:
        return first_line
    else:
        return first_line[:GIT_SHORT_MESSAGE].rsplit(' ', 1)[0]+'...'
