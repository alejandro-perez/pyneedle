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
from gi.repository import Gio, Tracker
import time

class TrackerEngine:
    def __init__(self, result_limit=20, results_ready_cb=None, debug=True):
        self._connection = Tracker.SparqlConnection.get_direct(None)
        self._result_limit = result_limit
        self._debug = debug
        self._cancellable = Gio.Cancellable()
        self._results_ready_cb = results_ready_cb
        self.name = 'Tracker async'

    def do_search (self, query_text, fts):
        self._cancellable.cancel()
        self._cancellable = Gio.Cancellable()
        query = self._build_fts_query(query_text) if fts else self._build_filename_query(query_text)
        self._count_query = self._build_fts_count_query(query_text) if fts else self._build_filename_count_query(query_text)
        self._starttime = time.time()
        self._exec_query_async(query)

    def _connection_ready (self, connection, result, user_data):
        tracker_result = []
        cursor = connection.query_finish (result)
        cursor.next_async(self._cancellable, self._cursor_ready, tracker_result)

    def _cursor_ready (self, cursor, result, tracker_result):
        try:
            if cursor.next_finish(result):
                tracker_result.append([cursor.get_string(0)[0], cursor.get_string(1)[0], cursor.get_string(2)[0], time.strptime(cursor.get_string(3)[0], '%Y-%m-%dT%H:%M:%SZ'), cursor.get_string(4)[0]])
                cursor.next_async(self._cancellable, self._cursor_ready, tracker_result)
            else:
                self._tracker_result = tracker_result
                self._exec_query_count_async(self._count_query)
        except Exception as e:
            if self._debug:
                print(e)

    def _exec_query_async (self, query):
        if self._debug:
            print(query)
        self._connection.query_async(query, self._cancellable, self._connection_ready, None)

    def _connection_ready_count (self, connection, result, user_data):
        cursor = connection.query_finish (result)
        cursor.next_async(self._cancellable, self._cursor_ready_count, None)

    def _cursor_ready_count (self, cursor, result, user_data):
        try:
            if (cursor.next_finish(result)):
                self._results_ready_cb(self._tracker_result, int(cursor.get_string(0)[0]))
                endtime = time.time()

                if self._debug:
                    print("Query", endtime - self._starttime)
                    starttime = time.time()

        except Exception as e:
            if self._debug:
                print(e)

    def _exec_query_count_async (self, query):
        if self._debug:
            print(query)
        self._connection.query_async(query, self._cancellable, self._connection_ready_count, None)

    def _build_filename_count_query (self, query_entry):
        # Split query text into words
        words = query_entry.split(' ')

        # Create filter for every one of those words
        queryfilter = 'FILTER (fn:contains (fn:lower-case(?name), \'' + words[0].lower() + '\')'

        for word in words[1:]:
            queryfilter += ' && fn:contains(fn:lower-case(?name), \'' + word.lower() + '\')'
        queryfilter += ' )'

        # Create query
        query = ('SELECT count(?f) ' +
                 'WHERE { ?f nfo:fileName ?name ; tracker:available true . ' + queryfilter + '  } ')

        # Return query
        return query

    def _build_fts_count_query (self, query_entry):
        # Get query text
        querytext = query_entry

        # Create query
        query = ('SELECT count(?f)' +
                 'WHERE { {?f fts:match \'' + querytext + '\' ; tracker:available true } }')

        # Return query
        return query

    def _build_filename_query (self, query_entry):
        # Split query text into words
        words = query_entry.split(' ')

        # Create filter for every one of those words
        queryfilter = 'FILTER (fn:contains (fn:lower-case(?name), \'' + words[0].lower() + '\')'
        for word in words[1:]:
            queryfilter += ' && fn:contains(fn:lower-case(?name), \'' + word.lower() + '\')'
        queryfilter += ' )'

        # Create query
        query = ('SELECT DISTINCT nie:url(?f) nfo:fileName(?f) nfo:fileSize(?f) nfo:fileLastModified(?f) nie:mimeType(?f) ' +
                 'WHERE { ?f nfo:fileName ?name ; tracker:available true . ' + queryfilter + '  } ' +
                 'ORDER BY DESC nfo:fileLastModified(?f) LIMIT ' + str(self._result_limit))

        # Return query
        return query

    def _build_fts_query (self, query_entry):
        # Get query text
        querytext = query_entry

        # Create query
        query = ('SELECT DISTINCT nie:url(?f) nfo:fileName(?f) nfo:fileSize(?f) nfo:fileLastModified(?f) nie:mimeType(?f) ' +
                 'WHERE { {?f fts:match \'' + querytext + '\' ; tracker:available true } }' +
                 'ORDER BY DESC nfo:fileLastModified(?f) LIMIT ' + str(self._result_limit))

        # Return query
        return query
