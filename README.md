# README #

### What is this repository for? ###

PyNeedle is a convenient tool created to allow you to quickly search for files in your computer, using one of the supported search engines (i.e. tracker and recoll). It is focused on searching by filename, and be used as one of the primary means to access your files in the daily work. Besides, it supports Full Text Search (FTS) mode for deeper searches.

* Version: 0.1

### How do I get set up? ###

* To install just execute: python2 setup.py install

### How do I use it? ###
First you have to select a search engine using the --engine command argument. You can select between:

* tracker: uses tracker asynchronous search (recommended)

* recoll: uses recoll. Searches are executed in a single thread (not recommended).

* recoll_mp: uses recoll. Searches are executed in independent processes (recommended)


To perform a filename search, just start writing, and the results will appear as soon as they are available. You don't need to include any wildchar, as each word you write will be interpreted as contains(word1) and contains(word2). Order does not matter, so <pdf hello> and <hello pdf> will produce the same results.

To perform a FTS search, you can use the button at the right of the entry input, or press Ctrl+T. In FTS mode, queries will be send "as is" to the search engine, meaning you can use the query language they implement.

Some shortcuts:

* Intro: open the selected file

* Alt+Intro: open a terminal wherever the selected file is

* Shift+Intro: open a file manager wherever the selected file is.

* Ctrl+1: switch to tracker engine

* Ctrl+2: switch to recoll_mp engine

* Ctrl+3: switch to recoll engine