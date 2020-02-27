#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2013 Alejandro Pérez Méndez (alex@um.es)
# Copyright (C) 2013 Pedro Martinez-Julia (pedromj@um.es)
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
from recoll import recoll
from gi.repository import GLib

import time, threading, multiprocessing
from gi.repository import GLib


class _RecollCommon:
    def __init__(self, connection, result_limit, debug=True):
        # Connecto to the RECOLL session
        self._connection = connection
        self._result_limit = result_limit
        self._debug = debug

    def _exec_query (self, query, fts):
        if self._debug: print("Query:", query)

        recoll_result = []
        recoll_query = self._connection.query()
        recoll_query.sortby("fmtime", ascending=False)
        starttime = time.time()
        nres = recoll_query.execute(query, stemlang="english spanish") if fts else recoll_query.executesd(query)
        endtime = time.time()

        if self._debug: print("Query", endtime - starttime)

        starttime = time.time()
        for i in range(min(nres, self._result_limit)):
            doc = recoll_query.fetchone()
            recoll_result.append([doc.url, doc.filename, doc.pcbytes, time.localtime(int(doc.fmtime)), doc.mtype])
        endtime = time.time()

        if self._debug: print("Fetch", endtime - starttime)

        return recoll_result, nres

    def _build_filename_query (self, query_entry):
        # Split query text into words
        words = query_entry.split(' ')

        search_data = recoll.SearchData()
        # Add a clause for each word
        for word in words:
            if word != "":
                search_data.addclause(type="filename",  qstring=word.lower())

        # Return query
        return search_data

    def _build_fts_query (self, query_entry):
        # Get query text
        return query_entry


class SearchThread(threading.Thread, _RecollCommon):
    def __init__(self, query_text, fts, connection, result_limit, results_ready_cb, debug):
        _RecollCommon.__init__(self, connection, result_limit, debug)
        threading.Thread.__init__(self)
        self._query_text = query_text
        self._fts = fts
        self._results_ready_cb = results_ready_cb
        self._sem = threading.Semaphore(0)
        self._queue = multiprocessing.Queue()
        self._process = multiprocessing.Process(target=self._process, args=(self._queue,))

    def run(self):
        self._process.start()
        self._sem.release()
        result = self._queue.get()
        self._sem.release()

        if result is not None:
            self._results_ready_cb(result[0], result[1])
        elif self._debug:
            print("Search cancelled")

    def _process(self, queue):
        query = self._build_fts_query(self._query_text) if self._fts else self._build_filename_query(self._query_text)
        result = self._exec_query(query, self._fts)
        queue.put(result)

    def stop(self):
        self._sem.acquire()
        self._queue.put(None)
        self._sem.acquire()
        self._process.terminate()
        self._sem.release()

class RecollEngineMP():
    def __init__(self, result_limit, results_ready_cb=None, debug=True):
        # Connecto to the RECOLL session
        self._connection = recoll.connect()
        self._result_limit = result_limit
        self._debug = debug
        self._results_ready_cb = results_ready_cb
        self._thread = None
        self.name = 'Recoll Multiprocess'

    def do_search (self, query_text, fts):
        if self._thread:
            self._thread.stop()
            self._thread.join()

        self._thread = SearchThread(query_text, fts, self._connection, self._result_limit, self._results_ready_cb, self._debug)
        self._thread.start()


class RecollEngineSP(_RecollCommon):
    def __init__(self, result_limit, results_ready_cb=None, debug=True):
        _RecollCommon.__init__(self, recoll.connect(), result_limit, debug)
        self._query_timer = None
        self._results_ready_cb = results_ready_cb
        self.name = 'Recoll'

    def do_search (self, query_text, fts):
        if (self._query_timer):
            if self._debug: print("Timer cancelled")
            self._query_timer.cancel()

        query = self._build_fts_query(query_text) if fts else self._build_filename_query(query_text)

        self._query_timer = threading.Timer(0.2, self._do_query, [query, fts])
        self._query_timer.start()

    def _do_query(self, query, fts):
        result = self._exec_query(query, fts)
        self._results_ready_cb(result[0], result[1])

class RecollEngineNT(_RecollCommon):
    def __init__(self, result_limit, results_ready_cb=None, debug=True):
        _RecollCommon.__init__(self, recoll.connect(), result_limit, debug)
        self._results_ready_cb = results_ready_cb
        self.name = 'Recoll No Thread'
        self._tag = None

    def do_search (self, query_text, fts):
        if (self._tag):
            if self._debug: print("Timer cancelled (should be)")
            GLib.source_remove(self._tag)
            self._tag = None

        query = self._build_fts_query(query_text) if fts else self._build_filename_query(query_text)

        self._query = query
        self._fts = fts
        self._tag = GLib.timeout_add(200, self._do_query)

    def _do_query(self):
        result = self._exec_query(self._query, self._fts)
        self._results_ready_cb(result[0], result[1])
        self._tag = None
        return False
