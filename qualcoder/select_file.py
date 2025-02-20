# -*- coding: utf-8 -*-

'''
Copyright (c) 2019 Colin Curtain

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

Author: Colin Curtain (ccbogel)
https://github.com/ccbogel/QualCoder
https://qualcoder.wordpress.com/
'''

from PyQt5 import QtCore, QtWidgets
import os
import sys
import logging
import traceback

from .GUI.ui_dialog_select_file import Ui_Dialog_selectfile

path = os.path.abspath(os.path.dirname(__file__))
logger = logging.getLogger(__name__)

def exception_handler(exception_type, value, tb_obj):
    """ Global exception handler useful in GUIs.
    tb_obj: exception.__traceback__ """
    tb = '\n'.join(traceback.format_tb(tb_obj))
    text = 'Traceback (most recent call last):\n' + tb + '\n' + exception_type.__name__ + ': ' + str(value)
    print(text)
    logger.error(_("Uncaught exception: ") + text)
    QtWidgets.QMessageBox.critical(None, _('Uncaught Exception'), text)


class DialogSelectFile(QtWidgets.QDialog):
    """
    Requires a list of dictionaries. This list must have a dictionary item called 'name'
    which is displayed to the user.
    The setupui method requires a title string for the dialog title and a selection mode:
    "single" or any other text which equates to many.

    User selects one or more names from the list depending on selection mode.
    getSelected method returns the selected dictionary object(s).
    """

    dict_list = None
    selectedname = None
    title = None

    def __init__(self, data, title, selectionmode):
        ''' present list of name to user for selection.
        data is a list of dictionaries containing the key 'name' '''

        sys.excepthook = exception_handler
        QtWidgets.QDialog.__init__(self)
        self.ui = Ui_Dialog_selectfile()
        self.ui.setupUi(self)
        self.setWindowTitle(title)
        self.selection_mode = selectionmode
        self.dict_list = data
        self.model = list_model(self.dict_list)
        self.ui.listView.setModel(self.model)
        if self.selection_mode == "single":
            self.ui.listView.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        else:
            self.ui.listView.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.ui.listView.doubleClicked.connect(self.accept)

    def get_selected(self):
        """ Get a selected dictionary  or a list of dictionaries depending on the
        selection mode. """

        if self.selection_mode == "single":
            current = self.ui.listView.currentIndex().row()
            return self.dict_list[int(current)]
        else:
            selected = []
            for item in self.ui.listView.selectedIndexes():
                selected.append(self.dict_list[item.row()])
            return selected


class list_model(QtCore.QAbstractListModel):
    def __init__(self, dict_list, parent=None):
        super(list_model, self).__init__(parent)
        sys.excepthook = exception_handler
        self.list = dict_list

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self.list)

    def data(self, index, role):
        if role == QtCore.Qt.DisplayRole:  # show just the name
            rowitem = self.list[index.row()]
            return QtCore.QVariant(rowitem['name'])
        elif role == QtCore.Qt.UserRole:  # return the whole python object
            rowitem = self.list[index.row()]
            return rowitem
        return QtCore.QVariant()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    ui = DialogSelectFile([{"name":"fff"}, {"name":"jjj"}], "title", "single")
    ui.show()
    sys.exit(app.exec_())

