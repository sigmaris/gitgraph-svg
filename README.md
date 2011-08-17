What it is
----------
A Git repository browser that displays a graph of branches using inline SVG and HTML5. Written in Python using the [Flask](http://flask.pocoo.org/) microframework.

Dependencies required
---------------------
 * [libgit2](http://libgit2.github.com/) and the [pygit2](https://github.com/libgit2/pygit2) Python-bindings - version 0.13+.
 * [BeautifulSoup](http://www.crummy.com/software/BeautifulSoup/) for encoding detection and Unicode conversion.
 * [Flask](http://flask.pocoo.org/)

To run
------
Edit settings.py.example to set the path of your repository and run:

    python ggapp.py

(or deploy on a web server using one of [these options](http://flask.pocoo.org/docs/deploying/))
