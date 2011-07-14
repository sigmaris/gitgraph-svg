from BeautifulSoup import UnicodeDammit
import time

def format_commit_time(timestamp):
    return time.strftime('%d %B %Y %H:%M', time.localtime(timestamp))

def force_unicode(text):
    return UnicodeDammit(text, smartQuotesTo=None).unicode
