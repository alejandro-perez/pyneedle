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
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Pango, Gio, GdkPixbuf, Gdk, GLib, GObject
import sys, subprocess, time, os, argparse, html

# Needed for python2/3 compatibility
if sys.version_info.major == 2:
    import urlparse
    urlparse_generic = urlparse
else:
    import urllib.parse
    urlparse_generic = urllib.parse

class PyNeedle (Gtk.Window):

    # Define new signals for the window
    __gsignals__ = {
        'toggle-fts' : (GObject.SIGNAL_ACTION, GObject.TYPE_NONE, ()),
        'open-in-folder' : (GObject.SIGNAL_ACTION, GObject.TYPE_NONE, ()),
        'open-in-terminal' : (GObject.SIGNAL_ACTION, GObject.TYPE_NONE, ()),
        'select-tracker' : (GObject.SIGNAL_ACTION, GObject.TYPE_NONE, ()),
        'select-recoll' : (GObject.SIGNAL_ACTION, GObject.TYPE_NONE, ()),
        'select-recoll-mp' : (GObject.SIGNAL_ACTION, GObject.TYPE_NONE, ()),
        'exit' : (GObject.SIGNAL_ACTION, GObject.TYPE_NONE, ())
    }

    def __init__ (self, launcher='xdg-open', terminal='xfce4-terminal', engine='tracker', debug=False):
        self._launcher = launcher
        self._terminal = terminal
        self._debug = debug

        # Create main window
        Gtk.Window.__init__(self)
        self.set_size_request(600, 300)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_default_icon(self._get_icon('edit-find', size=256))
        self.connect('delete-event', Gtk.main_quit)
        self.connect('toggle-fts', self._on_toggle_fts)
        self.connect('open-in-folder', self._on_open_folder_kb)
        self.connect('open-in-terminal', self._on_open_terminal_kb)
        self.connect('select-tracker', self._select_tracker)
        self.connect('select-recoll', self._select_recoll)
        self.connect('select-recoll-mp', self._select_recoll_mp)
        self.connect('show', self._on_window_show)
        self.connect('exit', Gtk.main_quit)

        # Create main vertical box
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add(vbox)

        # Create query entry widget and add it to the vertical box
        self._query_entry = Gtk.Entry()
        self._query_entry.connect('activate', self._on_entry_activated)
        self._query_entry.connect('changed', self._on_entry_changed)

        # Horizontal box for the entry and the radio buttons
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        hbox.pack_start(self._query_entry, True, True, 0)

        # Toggle button
        self._fts_button = Gtk.ToggleButton('Full Text Search')
        self._fts_button.connect('toggled', self._on_fts_toggled)
        hbox.pack_start(self._fts_button, False, False, 0)

        vbox.pack_start(hbox, False, False, 0)

        # Create List store for the results
        self._store = Gtk.ListStore(str, str, str, str, GdkPixbuf.Pixbuf, str)

        # Create the treeview for the view
        self._tree = Gtk.TreeView(self._store)
        self._tree.set_property('rules-hint', True)
        self._tree.connect('row-activated', self._on_row_clicked)
        self._tree.connect('button-press-event', self._on_row_button)
        self._tree.enable_model_drag_source(Gdk.ModifierType.BUTTON1_MASK, [('text/uri-list', 0, 0)], Gdk.DragAction.DEFAULT | Gdk.DragAction.COPY)
        self._tree.connect('drag-data-get', self._on_drag_data_get)

        # Create first column of the view (file icon) as model[4]
        icon_renderer = Gtk.CellRendererPixbuf()
        icon_column = Gtk.TreeViewColumn('Icon', icon_renderer)
        icon_column.add_attribute(icon_renderer, 'pixbuf', 4)
        self._tree.append_column(icon_column)

        # Create second column of hte view (file name) as model[0]
        text_renderer_ellipsize = Gtk.CellRendererText(ellipsize=Pango.EllipsizeMode.MIDDLE)
        text_column = Gtk.TreeViewColumn('Name', text_renderer_ellipsize, text=0)
        text_column.set_property("resizable", True)
        text_column.set_expand(True)
        self._tree.append_column(text_column)

        # Create third column of the view (file size) as model[2]
        text_renderer = Gtk.CellRendererText()
        text_column = Gtk.TreeViewColumn('Size', text_renderer, text=2)
        text_column.set_property("resizable", True)
        self._tree.append_column(text_column)

        # Create forth column of the view (modification date) as model[3]
        text_column = Gtk.TreeViewColumn('Modification date', text_renderer, text=3)
        text_column.set_property("resizable", True)
        self._tree.append_column(text_column)

        # Create row tooltip (file URL) as model[5]. This value allows markup, hence it needs to be processed
        self._tree.set_tooltip_column(5)

        # Add treeview to the Vbox
        scrolled = Gtk.ScrolledWindow()
        scrolled.add(self._tree)
        vbox.pack_start(scrolled, True, True, 0)

        # Add the label to the Vbox
        self._label = Gtk.Label('')
        vbox.pack_start(self._label, False, False, 0)

        # Create action group for the popup menu
        action_group = Gtk.ActionGroup('my_actions')
        self._add_popup_menu_actions(action_group)

        # Create UI manager
        uimanager = Gtk.UIManager()
        uimanager.add_ui_from_string('''
            <ui>
              <popup name='PopupMenu'>
                <menuitem action='Open' />
                <menuitem action='OpenFolder' />
                <menuitem action='OpenTerminal' />
              </popup>
            </ui>
        ''')
        uimanager.insert_action_group(action_group)

        # Crete popup menu
        self._popup = uimanager.get_widget('/PopupMenu')

        # Set up accelerators
        my_accelerators = Gtk.AccelGroup()
        key, mod = Gtk.accelerator_parse('<Control>l')
        self._query_entry.add_accelerator('grab-focus', my_accelerators, key, mod, Gtk.AccelFlags.VISIBLE)
        key, mod = Gtk.accelerator_parse('<Control>w')
        self.add_accelerator('exit', my_accelerators, key, mod, Gtk.AccelFlags.VISIBLE)
        key, mod = Gtk.accelerator_parse('Escape')
        self.add_accelerator('exit', my_accelerators, key, mod, Gtk.AccelFlags.VISIBLE)
        key, mod = Gtk.accelerator_parse('<Control>t')
        self.add_accelerator('toggle-fts', my_accelerators, key, mod, Gtk.AccelFlags.VISIBLE)
        key, mod = Gtk.accelerator_parse('<Alt>Return')
        self.add_accelerator('open-in-terminal', my_accelerators, key, mod, Gtk.AccelFlags.VISIBLE)
        key, mod = Gtk.accelerator_parse('<Shift>Return')
        self.add_accelerator('open-in-folder', my_accelerators, key, mod, Gtk.AccelFlags.VISIBLE)
        key, mod = Gtk.accelerator_parse('<Control>1')
        self.add_accelerator('select-tracker', my_accelerators, key, mod, Gtk.AccelFlags.VISIBLE)
        key, mod = Gtk.accelerator_parse('<Control>2')
        self.add_accelerator('select-recoll-mp', my_accelerators, key, mod, Gtk.AccelFlags.VISIBLE)
        key, mod = Gtk.accelerator_parse('<Control>3')
        self.add_accelerator('select-recoll', my_accelerators, key, mod, Gtk.AccelFlags.VISIBLE)

        self.add_accel_group(my_accelerators)

        # Define default variable (to be changed to command line options)
        self._terminal_open_folder_opt = '--working-directory='

        # Define the search engine
        if engine == 'recoll':
            from . import recoll_engine
            self._engine = recoll_engine.RecollEngineSP(20, self._update_list_store_cb, debug)
        elif engine == 'recoll_mp':
            from . import recoll_engine
            self._engine = recoll_engine.RecollEngineMP(20, self._update_list_store_cb, debug)
        elif engine == 'recoll_nt':
            from . import recoll_engine
            self._engine = recoll_engine.RecollEngineNT(20, self._update_list_store_cb, debug)
        else:
            from . import tracker_engine
            self._engine = tracker_engine.TrackerEngine(20, self._update_list_store_cb, debug)

        self.set_title('PyNeedle (' + self._engine.name + ')')

    ##############################
    # Auxiliary methods
    ##############################

    def _sizeof_fmt (self, num):
        for x in ['bytes', 'KB', 'MB', 'GB', 'TB']:
            if num < 1024.0:
                return '%3.1f %s' % (num, x)
            num /= 1024.0

    def _add_popup_menu_actions (self, action_group):
        ifactory = Gtk.IconFactory()
        ifactory.add_default()
        ifactory.add('utilities-terminal', Gtk.IconSet.new_from_pixbuf(self._get_icon('utilities-terminal')))
        action_group.add_actions([
            ('Open', Gtk.STOCK_OPEN, 'Open document', None, None, self._on_open_document),
            ('OpenFolder', Gtk.STOCK_DIRECTORY, 'Open parent folder', None, None, self._on_open_folder),
            ('OpenTerminal', 'terminal', 'Open parent in terminal', None, None, self._on_open_terminal),
        ])

    def _get_icon (self, name, size=20, flags=0):
        try:
            pixbuf = Gtk.IconTheme.get_default().load_icon(name, size, flags)
            pixbuf = pixbuf.scale_simple(size, size, GdkPixbuf.InterpType.HYPER)
            return pixbuf
        except Exception as ex:
            print("Exception loading icon:", ex)
            return None

    ##############################
    # Signal processing methods
    ##############################

    def _select_tracker(self, widget):
        import tracker_engine
        self._engine = tracker_engine.TrackerEngine(20, self._update_list_store_cb, self._debug)
        widget.set_title('PyNeedle (' + self._engine.name + ')')
        self._on_entry_changed(widget)

    def _select_recoll(self, widget):
        import recoll_engine
        self._engine = recoll_engine.RecollEngineSP(20, self._update_list_store_cb, self._debug)
        widget.set_title('PyNeedle (' + self._engine.name + ')')
        self._on_entry_changed(widget)

    def _select_recoll_mp(self, widget):
        import recoll_engine
        self._engine = recoll_engine.RecollEngineMP(20, self._update_list_store_cb, self._debug)
        widget.set_title('PyNeedle (' + self._engine.name + ')')
        self._on_entry_changed(widget)

    def _on_drag_data_get (self, treeview, context, selection, info, timestamp):
        tree_selection = self._tree.get_selection()
        (model, treeiter) = tree_selection.get_selected()
        uri = model[treeiter][1]
        selection.set_uris([uri])

    def _on_toggle_fts (self, widget):
        self._fts_button.set_active(not self._fts_button.get_active())

    def _on_open_document (self, widget):
        tree_selection = self._tree.get_selection()
        (model, treeiter) = tree_selection.get_selected()
        subprocess.Popen([self._launcher, model[treeiter][1]])

    def _on_open_folder_kb(self, widget):
        self._on_open_folder(widget)
        Gtk.main_quit()

    def _on_open_folder (self, widget):
        tree_selection = self._tree.get_selection()
        (model, treeiter) = tree_selection.get_selected()
        p = urlparse_generic.urlparse(model[treeiter][1])[2]
        parent = urlparse_generic.unquote(os.path.dirname(p))
        subprocess.Popen([self._launcher, parent])

    def _on_open_terminal_kb(self, widget):
        self._on_open_terminal(widget)
        Gtk.main_quit()

    def _on_open_terminal (self, widget):
        tree_selection = self._tree.get_selection()
        (model, treeiter) = tree_selection.get_selected()
        p = urlparse_generic.urlparse(model[treeiter][1])[2]
        parent = urlparse_generic.unquote(os.path.dirname(p))
        subprocess.Popen([self._terminal, self._terminal_open_folder_opt + parent])

    def _on_fts_toggled (self, widget):
        self._on_entry_changed(widget)
        #self._query_entry.grab_focus()

    def _on_entry_activated (self, widget):
        self._tree.grab_focus()

    def _on_entry_changed (self, widget):
        if len(self._query_entry.get_text()) > 1:
            self._engine.do_search(self._query_entry.get_text(), self._fts_button.get_active())
        else:
            self._store.clear()
            self._label.set_text('')

    def _on_row_clicked (self, treeview, path, column):
        self._on_open_document(treeview)
        Gtk.main_quit()

    def _on_row_button (self, widget, event):
        # Check whether right mouse button was preseed
        if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 3:
            self._popup.popup(None, None, None, None, event.button, event.time)

        # Check whether right mouse button was preseed
        elif event.type == Gdk.EventType._2BUTTON_PRESS and event.button == 2:
            self._on_open_document(widget)

    def _on_window_show (self, widget):
        self._query_entry.grab_focus()

    ##############################
    # Search result methods
    ##############################

    def _update_list_store_cb(self, result, nres):
        GLib.idle_add(self._update_list_store, result, nres)

    def _update_list_store (self, result, nres):
        # Clean ListStore
        self._store.clear()

        # For each element in the search results
        for item in result:
            # Get icon name based on MIME type
            iconName = Gio.content_type_get_icon(item[4])

            pixbuf = (self._get_icon(iconName.get_names()[0]) or self._get_icon(iconName.get_names()[1]) or
                      self._get_icon('text-x-generic'))

            # Pare URL and get parent folder (for the quote)
            p = urlparse_generic.urlparse(item[0])[2]
            parent = urlparse_generic.unquote(p)

            # Add current result into the model
            self._store.append([item[1], item[0], self._sizeof_fmt(float(item[2])), time.strftime('%d/%m/%y', item[3]), pixbuf, html.escape(parent, quote=True)])

        # Update label
        self._label.set_text('Showing ' + str(len(result)) + ' results of a total of ' + str(nres))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--launcher', dest='launcher', metavar='NAME', default='xdg-open', help='application launcher')
    parser.add_argument('--terminal', dest='terminal', metavar='NAME', default='xfce4-terminal', help='terminal')
    parser.add_argument('--engine', dest='engine', metavar='NAME', default='recoll', help='engine (tracker, recoll)')
    parser.add_argument('--debug', dest='debug', action="store_const", const=True, help='enable debugging ()')
    args = parser.parse_args()

    win = PyNeedle(launcher=args.launcher, terminal=args.terminal, engine=args.engine, debug=(args.debug is not None))
    win.show_all()
    GLib.threads_init()
    Gtk.main()


if __name__ == '__main__':
    main()
