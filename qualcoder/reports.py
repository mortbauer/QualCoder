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

from copy import copy
import csv
import logging
import os
from shutil import copyfile
import sys
import traceback

from PyQt5 import QtGui, QtWidgets, QtCore
from PyQt5.QtCore import Qt,QTextCodec
from PyQt5.QtGui import QBrush

from .GUI.ui_dialog_report_codings import Ui_Dialog_reportCodings
from .GUI.ui_dialog_report_comparisons import Ui_Dialog_reportComparisons
from .GUI.ui_dialog_report_code_frequencies import Ui_Dialog_reportCodeFrequencies
from .report_attributes import DialogSelectAttributeParameters
from .select_file import DialogSelectFile

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


class DialogReportCodeFrequencies(QtWidgets.QDialog):
    """ Show code and category frequencies, overall and for each coder.
    This is for text coding and image coding. """

    settings = None
    parent_textEdit = None
    coders = []
    categories = []
    codes = []
    coded_images_and_text = []

    def __init__(self, settings, parent_textEdit):

        sys.excepthook = exception_handler
        self.settings = settings
        self.parent_textEdit = parent_textEdit
        self.get_data()
        self.calculate_code_frequencies()
        QtWidgets.QDialog.__init__(self)
        self.ui = Ui_Dialog_reportCodeFrequencies()
        self.ui.setupUi(self)
        self.ui.pushButton_exporttext.pressed.connect(self.export_text_file)
        newfont = QtGui.QFont(settings['font'], settings['fontsize'], QtGui.QFont.Normal)
        self.setFont(newfont)
        treefont = QtGui.QFont(settings['font'], settings['treefontsize'], QtGui.QFont.Normal)
        self.ui.treeWidget.setFont(treefont)
        self.ui.treeWidget.setSelectionMode(QtWidgets.QTreeWidget.ExtendedSelection)
        self.fill_tree()

    def get_data(self):
        """ Called from init. gets coders, code_names and categories.
        Calls calculate_code_frequency - for each code.
        Adds a list item that is ready to be used by the treeWidget to display multiple
        columns with the coder frequencies.
        """

        cur = self.settings['conn'].cursor()
        self.coders = []
        cur.execute("select distinct owner from code_text union select distinct owner from code_image")
        result = cur.fetchall()
        self.coders = []
        for row in result:
            self.coders.append(row[0])
        self.categories = []
        cur.execute("select name, catid, owner, date, memo, supercatid from code_cat")
        result = cur.fetchall()
        for row in result:
            self.categories.append({'name': row[0], 'catid': row[1], 'owner': row[2],
            'date': row[3], 'memo': row[4], 'supercatid': row[5],
            'display_list': [row[0], 'catid:' + str(row[1])]})
        self.codes = []
        cur.execute("select name, memo, owner, date, cid, catid, color from code_name")
        result = cur.fetchall()
        for row in result:
            self.codes.append({'name': row[0], 'memo': row[1], 'owner': row[2], 'date': row[3],
            'cid': row[4], 'catid': row[5], 'color': row[6],
            'display_list': [row[0], 'cid:' + str(row[4])]})
        self.coded_images_and_text = []
        cur.execute("select cid, owner from code_text")
        result = cur.fetchall()
        for row in result:
            self.coded_images_and_text.append(row)
        cur.execute("select cid, owner from code_image")
        result = cur.fetchall()
        for row in result:
            self.coded_images_and_text.append(row)

    def calculate_code_frequencies(self):
        """ Calculate the frequency of each code for all coders and the total.
        Add a list item to each code that can be used to display in treeWidget.
        For codings in code_image, code_text.
        """

        for c in self.codes:
            total = 0
            for cn in self.coders:
                count = 0
                for cit in self.coded_images_and_text:
                    if cit[1] == cn and cit[0] == c['cid']:
                        count += 1
                        total += 1
                c['display_list'].append(count)
            c['display_list'].append(total)

        # add the number of codes directly under each category to the category
        for cat in self.categories:
            # magic 3 = cat name, cat id and total columns
            cat_list = [0] * (len(self.coders) + 3)
            for c in self.codes:
                if c['catid'] == cat['catid']:
                    for i in range(2, len(c['display_list'])):
                        cat_list[i] += c['display_list'][i]
            cat_list = cat_list[2:]
            for count in cat_list:
                cat['display_list'].append(count)

        # find leaf categories, add to above categories, and gradually remove leaves
        # until only top categories are left
        sub_cats = copy(self.categories)
        counter = 0
        while len(sub_cats) > 0 or counter < 10000:
            leaf_list = []
            branch_list = []
            for c in sub_cats:
                for c2 in sub_cats:
                    if c['catid'] == c2['supercatid']:
                        branch_list.append(c)
            for cat in sub_cats:
                if cat not in branch_list:
                    leaf_list.append(cat)
            # add totals for each coder and overall total to higher category
            for leaf_cat in leaf_list:
                for cat in self.categories:
                    if cat['catid'] == leaf_cat['supercatid']:
                        for i in range(2, len(cat['display_list'])):
                            cat['display_list'][i] += leaf_cat['display_list'][i]
                sub_cats.remove(leaf_cat)
            counter += 1

    def depthgauge(self, item):
        """ Get depth for treewidget item. """

        depth = 0
        while item.parent() is not None:
            item = item.parent()
            depth += 1
        return depth

    def export_text_file(self):
        """ Export coding frequencies to text file. """

        filename = "CODING FREQUENCIES.txt"
        options = QtWidgets.QFileDialog.DontResolveSymlinks | QtWidgets.QFileDialog.ShowDirsOnly
        directory = QtWidgets.QFileDialog.getExistingDirectory(None,
            _("Select directory to save file"), self.settings['directory'], options)
        if directory == "":
            return
        filename = directory + "/" + filename

        f = open(filename, 'w')
        text = _("CODING FREQUENCIES") + "\r\n"
        it = QtWidgets.QTreeWidgetItemIterator(self.ui.treeWidget)
        item = it.value()
        item_total_position = 1 + len(self.coders)
        while item:
            self.depthgauge(item)
            cat = False
            if item.text(1).split(':')[0] == "catid":
                cat = True
            prefix = ""
            for i in range(0, self.depthgauge(item)):
                prefix += "--"
            if cat:
                text += "\r\n" + prefix + _("Category: ") + item.text(0)  # + ", " + item.text(1)
                text += ", Frequency: " + item.text(item_total_position)
            else:
                text += "\r\n" + prefix + _("Code: ") + item.text(0)  # + ", " + item.text(1)
                text += _(", Frequency: ") + item.text(item_total_position)
            it += 1
            item = it.value()
        f.write(text)
        f.close()
        logger.info("Report exported to " + filename)
        QtWidgets.QMessageBox.information(None, _("Text file Export"), filename + _(" exported"))
        self.parent_textEdit.append(_("Coding frequencies text file exported to: ") + filename)

    def fill_tree(self):
        """ Fill tree widget, top level items are main categories and unlinked codes. """

        cats = copy(self.categories)
        codes = copy(self.codes)
        self.ui.treeWidget.clear()
        header = [_("Code Tree"), "Id"]
        for coder in self.coders:
            header.append(coder)
        header.append("Total")
        self.ui.treeWidget.setColumnCount(len(header))
        self.ui.treeWidget.setHeaderLabels(header)
        self.ui.treeWidget.header().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.ui.treeWidget.header().setStretchLastSection(False)
        # add top level categories
        remove_list = []
        for c in cats:
            if c['supercatid'] is None:
                display_list = []
                for i in c['display_list']:
                    display_list.append(str(i))
                top_item = QtWidgets.QTreeWidgetItem(display_list)
                top_item.setIcon(0, QtGui.QIcon("GUI/icon_cat.png"))
                self.ui.treeWidget.addTopLevelItem(top_item)
                remove_list.append(c)
        for item in remove_list:
            #try:
            cats.remove(item)
            #except Exception as e:
            #    logger.debug(str(e) + " item:" + str(item))

        ''' Add child categories. Look at each unmatched category, iterate through tree to
        add as child then remove matched categories from the list. '''
        count = 0
        while len(cats) > 0 or count < 10000:
            remove_list = []
            #logger.debug("cats:" + str(cats))
            for c in cats:
                it = QtWidgets.QTreeWidgetItemIterator(self.ui.treeWidget)
                item = it.value()
                while item:  # while there is an item in the list
                    #logger.debug("While: ", item.text(0), item.text(1), c['catid'], c['supercatid'])
                    if item.text(1) == 'catid:' + str(c['supercatid']):
                        display_list = []
                        for i in c['display_list']:
                            display_list.append(str(i))
                        child = QtWidgets.QTreeWidgetItem(display_list)
                        child.setIcon(0, QtGui.QIcon("GUI/icon_cat.png"))
                        item.addChild(child)
                        #logger.debug("Adding: " + c['name'])
                        remove_list.append(c)
                    it += 1
                    item = it.value()
            for item in remove_list:
                cats.remove(item)
            count += 1

        # add unlinked codes as top level items
        remove_items = []
        for c in codes:
            if c['catid'] is None:
                #logger.debug("c[catid] is None: new top item c[name]:" + c['name'])
                display_list = []
                for i in c['display_list']:
                    display_list.append(str(i))
                top_item = QtWidgets.QTreeWidgetItem(display_list)
                top_item.setIcon(0, QtGui.QIcon("GUI/icon_code.png"))
                top_item.setBackground(0, QBrush(QtGui.QColor(c['color']), Qt.SolidPattern))
                top_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                self.ui.treeWidget.addTopLevelItem(top_item)
                remove_items.append(c)
        for item in remove_items:
            codes.remove(item)

        # add codes as children
        for c in codes:
            it = QtWidgets.QTreeWidgetItemIterator(self.ui.treeWidget)
            item = it.value()
            while item:
                #logger.debug("for c in codes, item:" + item.text(0) +"|" + item.text(1) + ", c[cid]:" + str(c['cid']) +", c[catid]:" + str(c['catid']))
                if item.text(1) == 'catid:' + str(c['catid']):
                    display_list = []
                    for i in c['display_list']:
                        display_list.append(str(i))
                    child = QtWidgets.QTreeWidgetItem(display_list)
                    child.setBackground(0, QBrush(QtGui.QColor(c['color']), Qt.SolidPattern))
                    child.setIcon(0, QtGui.QIcon("GUI/icon_code.png"))
                    child.setFlags(Qt.ItemIsSelectable | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                    item.addChild(child)
                    c['catid'] = -1  # make unmatchable
                it += 1
                item = it.value()
        self.ui.treeWidget.expandAll()


class DialogReportCoderComparisons(QtWidgets.QDialog):
    """ Compare coded text sequences between coders using Cohen's Kappa. """

    settings = None
    parent_textEdit = None
    coders = []
    selected_coders = []
    categories = []
    code_names = []
    file_summaries = []
    comparisons = ""

    def __init__(self, settings, parent_textEdit):

        sys.excepthook = exception_handler
        self.settings = settings
        self.parent_textEdit = parent_textEdit
        self.comparisons = ""
        self.get_data()
        QtWidgets.QDialog.__init__(self)
        self.ui = Ui_Dialog_reportComparisons()
        self.ui.setupUi(self)
        self.ui.pushButton_run.setEnabled(False)
        self.ui.pushButton_run.pressed.connect(self.calculate_statistics)
        self.ui.pushButton_clear.pressed.connect(self.clear_selection)
        self.ui.pushButton_exporttext.pressed.connect(self.export_text_file)
        newfont = QtGui.QFont(settings['font'], settings['fontsize'], QtGui.QFont.Normal)
        self.setFont(newfont)
        treefont = QtGui.QFont(settings['font'], settings['treefontsize'], QtGui.QFont.Normal)
        self.ui.treeWidget.setFont(treefont)
        self.ui.treeWidget.setSelectionMode(QtWidgets.QTreeWidget.ExtendedSelection)
        self.ui.comboBox_coders.insertItems(0, self.coders)
        self.ui.comboBox_coders.currentTextChanged.connect(self.coder_selected)
        self.fill_tree()

    def get_data(self):
        """ Called from init. gets coders, code_names, categories, file_summaries.
        Images are not loaded. """

        self.categories = []
        cur = self.settings['conn'].cursor()
        cur.execute("select name, catid, owner, date, memo, supercatid from code_cat")
        result = cur.fetchall()
        for row in result:
            self.categories.append({'name': row[0], 'catid': row[1], 'owner': row[2],
            'date': row[3], 'memo': row[4], 'supercatid': row[5]})

        self.code_names = []
        cur.execute("select name, memo, owner, date, cid, catid, color from code_name")
        result = cur.fetchall()
        for row in result:
            self.code_names.append({'name': row[0], 'memo': row[1], 'owner': row[2], 'date': row[3],
            'cid': row[4], 'catid': row[5], 'color': row[6],
            'Agree%':'','A and B':'','Not A Not B':'','Disagree%':'','A not B':'','B not A':'','K':''
            })
        self.coders = []
        sql = "select owner from  code_image union select owner from code_text union select owner from code_av"
        cur.execute(sql)
        result = cur.fetchall()
        self.coders = [""]
        for row in result:
            self.coders.append(row[0])

        cur.execute("select id, length(fulltext) from source where mediapath is Null")
        self.file_summaries = cur.fetchall()

    def coder_selected(self):
        """ Select coders for comparison - only two coders can be selected. """

        coder = self.ui.comboBox_coders.currentText()
        if coder == "":
            return
        if len(self.selected_coders) == 0:
            self.selected_coders.append(coder)
        if len(self.selected_coders) == 1 and self.selected_coders[0] != coder:
            self.selected_coders.append(coder)

        self.ui.label_selections.setText("Coders: " + str(self.selected_coders))
        if len(self.selected_coders) == 2:
            self.ui.pushButton_run.setEnabled(True)

    def clear_selection(self):
        """ Clear the coder selection and tree widget statistics. """

        self.selected_coders = []
        self.ui.pushButton_run.setEnabled(False)
        self.ui.label_selections.setText(_("Coders: None selected"))
        it = QtWidgets.QTreeWidgetItemIterator(self.ui.treeWidget)
        item = it.value()
        while item:  # while there is an item in the list
            if item.text(1)[0:4] == 'cid:':
                item.setText(2, "")
                item.setText(3, "")
                item.setText(4, "")
                item.setText(5, "")
                item.setText(6, "")
            it += 1
            item = it.value()

    def export_text_file(self):
        """ Export coding comparison statistics to text file. """

        #TODO maybe use settings default directory here
        filename = QtWidgets.QFileDialog.getSaveFileName(None, _("Save text file"),
            os.path.expanduser('~'))
        if filename[0] == "":
            return
        filename = filename[0] + ".txt"
        f = open(filename, 'w')
        f.write(self.comparisons)
        f.close()
        logger.info(_("Coder comparisons report exported to ") + filename)
        QtWidgets.QMessageBox.information(None, _("Text file Export"), filename)
        self.parent_textEdit.append(_("Coder comparison text file exported to: ") + filename)

    def calculate_statistics(self):
        """ Iterate through tree widget, for all cids
        For each code_name calculate the two-coder comparison statistics. """

        self.comparisons = "====" + _("CODER COMPARISON") + "====\n" + _("Selected coders: ")
        self.comparisons += self.selected_coders[0] + ", " + self.selected_coders[1] + "\n"

        it = QtWidgets.QTreeWidgetItemIterator(self.ui.treeWidget)
        item = it.value()
        while item:  # while there is an item in the list
            #logger.debug("While: ", item.text(0), item.text(1), c['catid'], c['supercatid'])
            if item.text(1)[0:4] == 'cid:':
                #logger.debug(item.text(0), item.text(1))
                agreement = self.calculate_agreement_for_code_name(int(item.text(1)[4:]))
                item.setText(2, str(agreement['agreement']) + "%")
                item.setText(3, str(agreement['dual_percent']) + "%")
                item.setText(4, str(agreement['uncoded_percent']) + "%")
                item.setText(5, str(agreement['disagreement']) + "%")
                item.setText(6, str(agreement['kappa']))
                self.comparisons += "\n" + item.text(0) + " (" + item.text(1) + ")\n"
                self.comparisons += _("agreement: ") + str(agreement['agreement']) + "%"
                self.comparisons += _(", dual coded: ") + str(agreement['dual_percent']) + "%"
                self.comparisons += _(", uncoded: ") + str(agreement['uncoded_percent']) + "%"
                self.comparisons += _(", disagreement: ") + str(agreement['disagreement']) + "%"
                self.comparisons += ", Kappa: " + str(agreement['kappa'])
            it += 1
            item = it.value()

    def calculate_agreement_for_code_name(self, cid):
        """ Calculate the two-coder statistics for this cid
        Percentage agreement.
        Get the start and end positions in all files (source table) for this cid
        Look at each file separately to ge the commonly coded text.
        Each character that is coded by coder 1 or coder 2 is incremented, resulting in a list of 0, 1, 2
        where 0 is no codings at all, 1 is coded by only one coder and 2 is coded by both coders.
        'Disagree%':'','A not B':'','B not A':'','K':''
        """

        #logger.debug("Code id: " + str(cid))
        # coded0 and coded1 are the total characters coded by coder 0 and coder 1
        total = {'dual_coded': 0, 'single_coded': 0, 'uncoded': 0, 'characters': 0, 'coded0': 0, 'coded1': 0}
        # loop through each source file
        cur = self.settings['conn'].cursor()
        sql = "select pos0,pos1,fid from code_text where fid=? and cid=? and owner=?"
        for f in self.file_summaries:
            #logger.debug("file summary ", f)
            cur.execute(sql, [f[0], cid, self.selected_coders[0]])
            result0 = cur.fetchall()
            cur.execute(sql, [f[0], cid, self.selected_coders[1]])
            result1 = cur.fetchall()
            #logger.debug("result0: " + str(result0))
            #logger.debug("result1: " + str(result1))
            # determine the same characters coded by both coders, by adding 1 to each coded character
            char_list = [0] * f[1]
            for coded in result0:
                print(coded[0], coded[1])  # tmp
                for char in range(coded[0], coded[1]):
                    char_list[char] += 1
                    total['coded0'] += 1
            for coded in result1:
                for char in range(coded[0], coded[1]):
                    char_list[char] += 1
                    total['coded1'] += 1
            uncoded = 0
            single_coded = 0
            dual_coded = 0
            for char in char_list:
                if char == 0:
                    uncoded += 1
                if char == 1:
                    single_coded += 1
                if char == 2:
                    dual_coded += 1
            #logger.debug("file:" + f[0] + " dual:" + str(dual_coded) + " single:" + str(single_coded) + " uncoded:" + str(uncoded))
            total['dual_coded'] += dual_coded
            total['single_coded'] += single_coded
            total['uncoded'] += uncoded
            total['characters'] += f[1]
        total['agreement'] = round(100 * (total['dual_coded'] + total['uncoded']) / total['characters'], 2)
        total['dual_percent'] = round(100 * total['dual_coded'] / total['characters'], 2)
        total['uncoded_percent'] = round(100 * total['uncoded'] / total['characters'], 2)
        total['disagreement'] = round(100 - total['agreement'], 2)
        # Cohen's Kappa
        '''
        https://en.wikipedia.org/wiki/Cohen%27s_kappa

        k = Po - Pe     Po is proportionate agreement (both coders coded this text / all coded text))
            -------     Pe is probability of random agreement
            1  - Pe

            Pe = Pyes + Pno
            Pyes = proportion Yes by A multiplied by proportion Yes by B
                 = total['coded0']/total_coded * total['coded1]/total_coded

            Pno = proportion No by A multiplied by proportion No by B
                = (total_coded - total['coded0']) / total_coded * (total_coded - total['coded1]) / total_coded

        IMMEDIATE BELOW IS INCORRECT - RESULTS IN THE TOTAL AGREEMENT SCORE
        Po = total['agreement'] / 100
        Pyes = total['coded0'] / total['characters'] * total['coded1'] / total['characters']
        Pno = (total['characters'] - total['coded0']) / total['characters'] * (total['characters'] - total['coded1']) / total['characters']

        BELOW IS BETTER - ONLY LOOKS AT PROPORTIONS OF CODED CHARACTERS
        NEED TO CONFIRM THIS IS THE CORRECT APPROACH
        '''
        total['kappa'] = "zerodiv"
        try:
            unique_codings = total['coded0'] + total['coded1'] - total['dual_coded']
            Po = total['dual_coded'] / unique_codings
            Pyes = total['coded0'] / unique_codings * total['coded1'] / unique_codings
            Pno = (unique_codings - total['coded0']) / unique_codings * (unique_codings - total['coded1']) / unique_codings
            Pe = Pyes * Pno
            kappa = round((Po - Pe) / (1 - Pe), 4)
            total['kappa'] = kappa
        except ZeroDivisionError:
            msg = _("ZeroDivisionError. unique_codings:") + str(unique_codings)
            logger.debug(msg)
        return total

    def fill_tree(self):
        """ Fill tree widget, top level items are main categories and unlinked codes. """

        cats = copy(self.categories)
        codes = copy(self.code_names)
        self.ui.treeWidget.clear()
        self.ui.treeWidget.setColumnCount(7)
        self.ui.treeWidget.setHeaderLabels([_("Code Tree"), "Id","Agree %", "A and B %", "Not A Not B %", "Disagree %", "Kappa"])
        self.ui.treeWidget.header().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.ui.treeWidget.header().setStretchLastSection(False)
        # add top level categories
        remove_list = []
        for c in cats:
            if c['supercatid'] is None:
                top_item = QtWidgets.QTreeWidgetItem([c['name'], 'catid:' + str(c['catid']) ])
                top_item.setIcon(0, QtGui.QIcon("GUI/icon_cat.png"))
                self.ui.treeWidget.addTopLevelItem(top_item)
                remove_list.append(c)
        for item in remove_list:
            #try:
            cats.remove(item)
            #except Exception as e:
            #    logger.debug(str(e) + " item:" + str(item))

        ''' Add child categories. Look at each unmatched category, iterate through tree to
        add as child then remove matched categories from the list. '''
        count = 0
        while len(cats) > 0 or count < 10000:
            remove_list = []
            #logger.debug("cats:" + str(cats))
            for c in cats:
                it = QtWidgets.QTreeWidgetItemIterator(self.ui.treeWidget)
                item = it.value()
                while item:  # while there is an item in the list
                    #logger.debug("While: ", item.text(0), item.text(1), c['catid'], c['supercatid'])
                    if item.text(1) == 'catid:' + str(c['supercatid']):
                        child = QtWidgets.QTreeWidgetItem([c['name'], 'catid:' + str(c['catid']) ])
                        child.setIcon(0, QtGui.QIcon("GUI/icon_cat.png"))
                        item.addChild(child)
                        #logger.debug("Adding: " + c['name'])
                        remove_list.append(c)
                    it += 1
                    item = it.value()
            for item in remove_list:
                cats.remove(item)
            count += 1

        # add unlinked codes as top level items
        remove_items = []
        for c in codes:
            if c['catid'] is None:
                #logger.debug("c[catid] is None: new top item c[name]:" + c['name'])
                top_item = QtWidgets.QTreeWidgetItem([c['name'], 'cid:' + str(c['cid']) ])
                top_item.setIcon(0, QtGui.QIcon("GUI/icon_code.png"))
                top_item.setBackground(0, QBrush(QtGui.QColor(c['color']), Qt.SolidPattern))
                top_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                self.ui.treeWidget.addTopLevelItem(top_item)
                remove_items.append(c)
        for item in remove_items:
            codes.remove(item)

        # add codes as children
        for c in codes:
            it = QtWidgets.QTreeWidgetItemIterator(self.ui.treeWidget)
            item = it.value()
            while item:
                #logger.debug("for c in codes, item:" + item.text(0) +"|" + item.text(1) + ", c[cid]:" + str(c['cid']) +", c[catid]:" + str(c['catid']))
                if item.text(1) == 'catid:' + str(c['catid']):
                    child = QtWidgets.QTreeWidgetItem([c['name'], 'cid:' + str(c['cid']) ])
                    child.setBackground(0, QBrush(QtGui.QColor(c['color']), Qt.SolidPattern))
                    child.setIcon(0, QtGui.QIcon("GUI/icon_code.png"))
                    child.setFlags(Qt.ItemIsSelectable | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                    item.addChild(child)
                    c['catid'] = -1  # make unmatchable
                it += 1
                item = it.value()
        self.ui.treeWidget.expandAll()


class DialogReportCodes(QtWidgets.QDialog):
    """ Get reports on coded text/images/audio/video using a range of variables:
        Files, Cases, Coders, text limiters, Attribute limiters.
        Export reports as plain text, ODT, html or csv.
    """
    #TODO - export case matrix
    #TODO - export coded data as csv with codes as column headings

    settings = None
    parent_textEdit = None
    code_names = []
    coders = [""]
    categories = []
    html_links = []  # For html output with media link (images, av)
    text_results = []
    image_results = []
    av_results = []
    # variables for search restrictions
    file_ids = ""
    case_ids = ""
    attribute_selection = ""

    def __init__(self, settings, parent_textEdit):
        sys.excepthook = exception_handler
        self.settings = settings
        self.parent_textEdit = parent_textEdit
        self.get_data()
        QtWidgets.QDialog.__init__(self)
        self.ui = Ui_Dialog_reportCodings()
        self.ui.setupUi(self)
        newfont = QtGui.QFont(settings['font'], settings['fontsize'], QtGui.QFont.Normal)
        self.setFont(newfont)
        treefont = QtGui.QFont(settings['font'], settings['treefontsize'], QtGui.QFont.Normal)
        self.ui.treeWidget.setFont(treefont)
        self.ui.treeWidget.setSelectionMode(QtWidgets.QTreeWidget.ExtendedSelection)
        self.ui.comboBox_coders.insertItems(0, self.coders)
        self.fill_tree()
        self.ui.pushButton_search.clicked.connect(self.search)
        self.ui.pushButton_fileselect.clicked.connect(self.select_files)
        self.ui.pushButton_caseselect.clicked.connect(self.select_cases)
        self.ui.pushButton_attributeselect.clicked.connect(self.select_attributes)
        self.ui.pushButton_exporttext.clicked.connect(self.export_text_file)
        self.ui.pushButton_exporthtml.clicked.connect(self.export_html_file)
        self.ui.pushButton_exportodt.clicked.connect(self.export_odt_file)
        self.ui.pushButton_export_csv.clicked.connect(self.export_csv_file)
        self.ui.splitter.setSizes([100, 200, 0])

    def get_data(self):
        """ Called from init, delete category. Load codes, categories, and coders. """

        self.categories = []
        cur = self.settings['conn'].cursor()
        cur.execute("select name, catid, owner, date, memo, supercatid from code_cat")
        result = cur.fetchall()
        for row in result:
            self.categories.append({'name': row[0], 'catid': row[1], 'owner': row[2],
            'date': row[3], 'memo': row[4], 'supercatid': row[5]})
        self.code_names = []
        cur = self.settings['conn'].cursor()
        cur.execute("select name, memo, owner, date, cid, catid, color from code_name")
        result = cur.fetchall()
        for row in result:
            self.code_names.append({'name': row[0], 'memo': row[1], 'owner': row[2], 'date': row[3],
            'cid': row[4], 'catid': row[5], 'color': row[6]})
        self.coders = []
        cur.execute("select distinct owner from code_text")
        result = cur.fetchall()
        self.coders = [""]
        for row in result:
            self.coders.append(row[0])

    def fill_tree(self):
        """ Fill tree widget, top level items are main categories and unlinked codes. """

        cats = copy(self.categories)
        codes = copy(self.code_names)
        self.ui.treeWidget.clear()
        self.ui.treeWidget.setColumnCount(3)
        self.ui.treeWidget.setHeaderLabels([_("Name"), "Id", _("Memo")])
        self.ui.treeWidget.header().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.ui.treeWidget.header().setStretchLastSection(False)
        # add top level categories
        remove_list = []
        for c in cats:
            if c['supercatid'] is None:
                memo = ""
                if c['memo'] != "":
                    memo = _("Memo")
                top_item = QtWidgets.QTreeWidgetItem([c['name'], 'catid:' + str(c['catid']), memo])
                top_item.setIcon(0, QtGui.QIcon("GUI/icon_cat.png"))
                self.ui.treeWidget.addTopLevelItem(top_item)
                remove_list.append(c)
        for item in remove_list:
            #try:
            cats.remove(item)
            #except Exception as e:
            #    logger.debug("item:" + str(item) + ", e:" + str(e))

        ''' Add child categories. Look at each unmatched category, iterate through tree
        to add as child then remove matched categories from the list. '''
        count = 0
        while len(cats) > 0 or count < 10000:
            remove_list = []
            #logger.debug(cats)
            for c in cats:
                it = QtWidgets.QTreeWidgetItemIterator(self.ui.treeWidget)
                item = it.value()
                while item:  # while there is an item in the list
                    #logger.debug("While item in list: " + item.text(0) + "|" + item.text(1) + ", c[catid]:" + str(c['catid']) + ", supercatid:" + str(c['supercatid']))
                    if item.text(1) == 'catid:' + str(c['supercatid']):
                        memo = ""
                        if c['memo'] != "":
                            memo = "Memo"
                        child = QtWidgets.QTreeWidgetItem([c['name'], 'catid:' + str(c['catid']), memo])
                        child.setIcon(0, QtGui.QIcon("GUI/icon_cat.png"))
                        item.addChild(child)
                        #logger.debug("Adding item: " + c['name'])
                        remove_list.append(c)
                    it += 1
                    item = it.value()
            for item in remove_list:
                cats.remove(item)
            count += 1

        # add unlinked codes as top level items
        remove_items = []
        for c in codes:
            if c['catid'] is None:
                #logger.debug("add unlinked code:" + c['name'])
                memo = ""
                if c['memo'] != "":
                    memo = "Memo"
                top_item = QtWidgets.QTreeWidgetItem([c['name'], 'cid:' + str(c['cid']), memo])
                top_item.setIcon(0, QtGui.QIcon("GUI/icon_code.png"))
                top_item.setBackground(0, QBrush(QtGui.QColor(c['color']), Qt.SolidPattern))
                top_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled)
                self.ui.treeWidget.addTopLevelItem(top_item)
                remove_items.append(c)
        for item in remove_items:
            codes.remove(item)

        # add codes as children
        for c in codes:
            it = QtWidgets.QTreeWidgetItemIterator(self.ui.treeWidget)
            item = it.value()
            while item:
                #logger.debug("add codes as children, item:" + item.text(0) + "|" + item.text(1) + ", c[id]:" + str(c['cid']) + ", c[catid]:" + str(c['catid']))
                if item.text(1) == 'catid:' + str(c['catid']):
                    memo = ""
                    if c['memo'] != "":
                        memo = _("Memo")
                    child = QtWidgets.QTreeWidgetItem([c['name'], 'cid:' + str(c['cid']), memo])
                    child.setBackground(0, QBrush(QtGui.QColor(c['color']), Qt.SolidPattern))
                    child.setIcon(0, QtGui.QIcon("GUI/icon_code.png"))
                    child.setFlags(Qt.ItemIsSelectable | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled)
                    item.addChild(child)
                    c['catid'] = -1  # make unmatchable
                it += 1
                item = it.value()
        self.ui.treeWidget.expandAll()

    def export_text_file(self):
        """ Export report to a plain text file with .txt ending.
        QTextWriter supports plaintext, ODF and HTML.
        TODO? add default directory to export to
        """

        if len(self.ui.textEdit.document().toPlainText()) == 0:
            return
        filename = QtWidgets.QFileDialog.getSaveFileName(None, _("Save text file"),
            self.settings['directory'])
        if filename[0] == "":
            return
        filename = filename[0] + ".txt"
        tw = QtGui.QTextDocumentWriter()
        tw.setFileName(filename)
        tw.setFormat(b'plaintext')  # byte array needed for Windows 10
        tw.write(self.ui.textEdit.document())
        self.parent_textEdit.append(_("Report exported: ") + filename)
        QtWidgets.QMessageBox.information(None, _("Report exported"), filename)

    def export_odt_file(self):
        """ Export report to open document format with .odt ending.
        QTextWriter supports plaintext, ODF and HTML .
        """

        if len(self.ui.textEdit.document().toPlainText()) == 0:
            return
        filename = QtWidgets.QFileDialog.getSaveFileName(None, _("Save Open Document Text file"),
            self.settings['directory'])
        #    os.path.expanduser('~'))
        if filename[0] == "":
            return
        filename = filename[0] + ".odt"
        tw = QtGui.QTextDocumentWriter()
        tw.setFileName(filename)
        tw.setFormat(b'ODF')  # byte array needed for Windows 10
        tw.write(self.ui.textEdit.document())
        self.parent_textEdit.append(_("Report exported: ") + filename)
        QtWidgets.QMessageBox.information(None, _("Report exported"), filename)

    def export_csv_file(self):
        """ Export report to csv file.
        Export coded data as csv with codes as column headings.
        Draw data from self.text_results, self.image_results, self.av_results
        First need to determine number of columns based on the distinct number of codes in the results.
        Then the number of rows based on the most frequently assigned code.
        Each data cell contains coded text, or the memo if A/V or image and the file or case name.
        """

        if self.text_results == [] and self.image_results == [] and self.av_results == []:
            return

        codes_all = []
        codes_set = []
        codes_freq_list = []

        #print("TEXT")  # tmp
        for i in self.text_results:
            codes_all.append(i['codename'])
            #print(i)
        #print("IMAGES")  # tmp
        for i in self.image_results:
            codes_all.append(i['codename'])
            #print(i)
        #print("AUDIO/VIDEO")  # tmp
        for i in self.av_results:
            codes_all.append(i['codename'])
            #print(i)

        codes_set = list(set(codes_all))
        codes_set.sort()
        for x in codes_set:
            codes_freq_list.append(codes_all.count(x))

        #print(codes_all)
        #print(codes_set)
        #print(codes_freq_list)

        ncols = len(codes_set)
        nrows = sorted(codes_freq_list)[-1]
        #print("ncols:", ncols, "nrows:", nrows)

        # Prepare data rows for csv writer
        csv_data = []
        for r in range(0, nrows):
            row = []
            for c in range(0, ncols):
                row.append("")
            csv_data.append(row)

        # Look at each code and fill column with data
        for col, code in enumerate(codes_set):
            row = 0
            for i in self.text_results:
                if i['codename'] == code:
                    d = i['text'] + "\n" + i['file_or_casename']
                     # Add file id if results are based on attribute selection
                    if i['file_or_case'] == "":
                        d += " fid:" + str(i['fid'])
                    csv_data[row][col]  = d
                    row += 1
            for i in self.image_results:
                if i['codename'] == code:
                    d = i['memo']
                    if d == "":
                        d = "NO MENO"
                    d += "\n" + i['file_or_casename']
                    # Add filename if results are based on attribute selection
                    if i['file_or_case'] == "":
                        d += " " + i['mediapath'][8:]
                    csv_data[row][col] = d
                    row +=1
            for i in self.av_results:
                if i['codename'] == code:
                    d = i['memo']
                    if d == "":
                        d = "NO MEMO"
                    d += "\n"
                    # av 'text' contains video/filename, time slot and memo, so trim some out
                    trimmed = i['text'][6:]
                    pos = trimmed.find(']')
                    trimmed = trimmed[:pos + 1]
                    # Add case name as well as file name and time slot
                    if i['file_or_case'] != "File":
                        trimmed = i['file_or_casename'] + " " + trimmed
                    d += trimmed
                    csv_data[row][col] = d
                    row += 1

        filename = QtWidgets.QFileDialog.getSaveFileName(None, _("Save CSV file"),
            self.settings['directory'])
        if filename[0] == "":
            return
        filename = filename[0] + ".csv"
        with open(filename, 'w', newline='') as csvfile:
            filewriter = csv.writer(csvfile, delimiter=',',
                quotechar='"', quoting=csv.QUOTE_MINIMAL)
            filewriter.writerow(codes_set)  # header row
            for row in csv_data:
                filewriter.writerow(row)

    def export_html_file(self):
        """ Export report to a html file. Create folder of images and change refs to the
        folder.
        POSSIBLY TODO: an alternative is to have picture data in base64 so there is no
        need for a separate folder that the html file links to.
        TODO? add default directory to export to
        """

        if len(self.ui.textEdit.document().toPlainText()) == 0:
            return
        filename = QtWidgets.QFileDialog.getSaveFileName(None, _("Save html file"),
            self.settings['directory'])
        if filename[0] == "":
            return
        filename = filename[0] + ".html"
        tw = QtGui.QTextDocumentWriter()
        tw.setFileName(filename)
        tw.setFormat(b'HTML')  # byte array needed for Windows 10
        tw.setCodec(QTextCodec.codecForName('UTF-8'))  # for Windows 10
        tw.write(self.ui.textEdit.document())

        # Create folder of images and media and change html links
        foldername = filename[:-5]
        foldername_without_path = foldername.split('/')[-1]
        try:
            os.mkdir(foldername)
            os.mkdir(foldername + "/audio")
            os.mkdir(foldername + "/video")
        except Exception as e:
            logger.warning(_("html folder creation error ") + str(e))
            QtWidgets.QMessageBox.warning(None, _("Folder creation"), foldername + _(" error"))
            return
        html = ""
        try:
            with open(filename, 'r') as f:
                html = f.read()
        except Exception as e:
            logger.warning(_('html file reading error:') + str(e))
            return

        for item in self.html_links:
            if item['imagename'] is not None:
                # [-3] has a counter, e.g. 1_, 2_ for each image eto make it distinct
                imagename = item['imagename'].split('/')[-3] + item['imagename'].split('/')[-1]
                #print("IN: ", imagename)
                folder_link = filename[:-5] + "/" + imagename
                #print("FL:" ,folder_link)
                item['image'].save(folder_link)
                html_link = foldername_without_path + "/" + imagename
                ''' Replace html links, with fix for Windows 10, item[imagename] contains a lower case directory but
                this needs to be upper case for the replace method to work:  c:  =>  C:
                '''
                unreplaced_html = copy(html)  # for Windows 10 directory name upper/lower case issue
                html = html.replace(item['imagename'], html_link)
                if unreplaced_html == html:
                    html = html.replace(item['imagename'][0].upper() + item['imagename'][1:], html_link)
                #print("Windows 10 not replacing issue ", item['imagename'], html_link)
                #logger.debug("Windows 10 not replacing issue: item[imagename]: " + item['imagename'] + ", html_link: " + html_link)
            if item['avname'] is not None:
                try:
                    # add audio/video to folder
                    if not os.path.isfile(foldername + item['avname']):
                        copyfile(self.settings['path'] + item['avname'], foldername + item['avname'])
                    mediatype = item['avname'][1:6]
                    extension = item['avname'][item['avname'].rfind('.') + 1:]
                    extra = "</p><" + mediatype + " controls>"
                    extra += '<source src="' + foldername + item['avname']
                    extra += '#t=' + item['av0'] +',' + item['av1'] + '"'
                    extra += ' type="' + mediatype + '/' + extension + '">'
                    extra += '</' + mediatype + '><p>'
                    #print("EXTRA:", extra)
                    # hopefully only one location with video/link: [mins.secs - mins.secs]
                    location = html.find(item['avtext'])
                    location = location + len(['avtext'])- 1
                    tmp = html[:location] + extra + html[location:]
                    html = tmp
                except Exception as e:
                    print(e)
                    QtWidgets.QMessageBox.warning(None, _("HTML file creation exception"), str(e))

        with open(filename, 'w') as f:
            f.write(html)
        msg = _("Report exported to: ") + filename
        msg += "\n" + _("Image folder: ") + foldername
        self.parent_textEdit.append(msg)
        QtWidgets.QMessageBox.information(None, _("HTML file saved"), msg)

    def recursive_set_selected(self, item):
        """ Set all children of this item to be selected if the item is selected.
        Recurse through any child categories. """
        #logger.debug("recurse this item:" + item.text(0) + "|" item.text(1))
        child_count = item.childCount()
        for i in range(child_count):
            if item.isSelected():
                item.child(i).setSelected(True)
            self.recursive_set_selected(item.child(i))

    def search(self):
        """ Search for selected codings.
        There are three main search pathways.
        The default is based on file selection and can be restricted using the file
        selection dialog.
        The second pathway is based on case selection and can be restricted using the
        case selection dialog. If cases are selected this overrides file selections that
        the user has entered.
        The third pathway is based on attribute selection, which may include files or cases.

        The textEdit.document is filled with the search results.
        Results are drawn from the textEdit.document to fill reports in .txt and .odt formats.
        Results are drawn from the textEdit.document and html_links variable to fill reports in html format.
        Results are drawn from self.text_results, self.image_results and self.av_results to prepare a csv file.
        """

        coder = self.ui.comboBox_coders.currentText()
        #self.html_results = ""
        self.html_links = []  # For html file output with media
        search_text = self.ui.lineEdit.text()

        rows = self.ui.tableWidget.rowCount()
        for r in range(0, rows):
            self.ui.tableWidget.removeRow(0)

        # set all items under selected categories to be selected
        self.recursive_set_selected(self.ui.treeWidget.invisibleRootItem())
        items = self.ui.treeWidget.selectedItems()
        if len(items) == 0:
            QtWidgets.QMessageBox.warning(None, _("No codes"), _("No codes have been selected."))
            return
        if self.file_ids == "" and self.case_ids == "" and self.attribute_selection == []:
            QtWidgets.QMessageBox.warning(None, _("Nothing selected"),
                _("No files, cases or attributes have been selected."))
            return

        # Add search terms to textEdit
        self.ui.textEdit.clear()
        parameters = self.ui.label_selections.text()
        self.ui.textEdit.insertPlainText(_("Search parameters") + ":\n" + parameters + "\n")
        if coder == "":
            self.ui.textEdit.insertPlainText(_("Coding by: All coders"))
        else:
            self.ui.textEdit.insertPlainText(_("Coding by: ") + coder)
        if search_text != "":
            self.ui.textEdit.insertPlainText(_("Search text: ") + search_text)
        codes_string = "\n" + _("Codes: ")
        for i in items:
            codes_string += i.text(0) + ". "
        self.ui.textEdit.insertPlainText(codes_string)
        self.ui.textEdit.insertPlainText("\n==========\n")

        # get selected codes from selected items
        code_ids = ""
        for i in items:
            if i.text(1)[0:3] == 'cid':
                code_ids += "," + i.text(1)[4:]
        code_ids = code_ids[1:]
        #logger.debug("File ids\n",self.file_ids, type(self.file_ids))
        #logger.debug("Case ids\n",self.case_ids, type(self.case_ids))
        self.text_results = []
        self.image_results = []
        self.av_results = []
        cur = self.settings['conn'].cursor()

        # get coded text/images/av via selected files
        parameters = []
        if self.file_ids != "":
            # coded text
            sql = "select code_name.name, color, source.name, pos0, pos1, seltext, "
            sql += "code_text.owner, fid from code_text join code_name "
            sql += "on code_name.cid = code_text.cid join source on fid = source.id "
            sql += "where code_name.cid in (" + code_ids + ") "
            sql += "and source.id in (" + self.file_ids + ") "
            if coder != "":
                sql += " and code_text.owner=? "
                parameters.append(coder)
            if search_text != "":
                sql += " and seltext like ? "
                parameters.append("%" + str(search_text) + "%")
            if parameters == []:
                cur.execute(sql)
            else:
                #logger.info("SQL:" + sql)
                #logger.info("Parameters:" + str(parameters))
                cur.execute(sql, parameters)
            result = cur.fetchall()
            for row in result:
                self.text_results.append(row)

            # coded images
            parameters = []
            sql = "select code_name.name, color, source.name, x1, y1, width, height,"
            sql += "code_image.owner, source.mediapath, source.id, code_image.memo "
            sql += " from code_image join code_name "
            sql += "on code_name.cid = code_image.cid join source on code_image.id = source.id "
            sql += "where code_name.cid in (" + code_ids + ") "
            sql += "and source.id in (" + self.file_ids + ") "
            if coder != "":
                sql += " and code_image.owner=? "
                parameters.append(coder)
            if search_text != "":
                sql += " and code_image.memo like ? "
                parameters.append("%" + str(search_text) + "%")
            if parameters == []:
                cur.execute(sql)
            else:
                #logger.info("SQL:" + sql)
                #logger.info("Parameters:" + str(parameters))
                cur.execute(sql, parameters)
            result = cur.fetchall()
            for row in result:
                self.image_results.append(row)

            # coded audio and video, also looks for search_text in coded segment meno
            parameters = []
            sql = "select code_name.name, color, source.name, pos0, pos1, code_av.memo, "
            sql += "code_av.owner, source.mediapath, source.id from code_av join code_name "
            sql += "on code_name.cid = code_av.cid join source on code_av.id = source.id "
            sql += "where code_name.cid in (" + code_ids + ") "
            sql += "and source.id in (" + self.file_ids + ") "
            if coder != "":
                sql += " and code_av.owner=? "
                parameters.append(coder)
            if search_text != "":
                sql += " and code_av.memo like ? "
                parameters.append("%" + str(search_text) + "%")
            if parameters == []:
                cur.execute(sql)
            else:
                #logger.info("SQL:" + sql)
                #logger.info("Parameters:" + str(parameters))
                cur.execute(sql, parameters)
            result = cur.fetchall()
            for row in result:
                self.av_results.append(row)

        # get coded text/images/av via selected cases
        if self.case_ids != "":
            # coded text
            sql = "select code_name.name, color, cases.name, "
            sql += "code_text.pos0, code_text.pos1, seltext, code_text.owner, code_text.fid from "
            sql += "code_text join code_name on code_name.cid = code_text.cid "
            sql += "join (case_text join cases on cases.caseid = case_text.caseid) on "
            sql += "code_text.fid = case_text.fid "
            sql += "where code_name.cid in (" + code_ids + ") "
            sql += "and case_text.caseid in (" + self.case_ids + ") "
            sql += "and (code_text.pos0 >= case_text.pos0 and code_text.pos1 <= case_text.pos1)"
            if coder != "":
                sql += " and code_text.owner=? "
                parameters.append(coder)
            if search_text != "":
                sql += " and seltext like ? "
                parameters.append("%" + str(search_text) + "%")

            if parameters == []:
                cur.execute(sql)
            else:
                cur.execute(sql, parameters)
            result = cur.fetchall()
            for row in result:
                self.text_results.append(row)

            # coded images
            parameters = []
            sql = "select code_name.name, color, cases.name, "
            sql += "x1, y1, width, height, code_image.owner,source.mediapath, source.id, "
            sql += "code_image.memo from "
            sql += "code_image join code_name on code_name.cid = code_image.cid "
            sql += "join (case_text join cases on cases.caseid = case_text.caseid) on "
            sql += "code_image.id = case_text.fid "
            sql += " join source on case_text.fid = source.id "
            sql += "where code_name.cid in (" + code_ids + ") "
            sql += "and case_text.caseid in (" + self.case_ids + ") "
            if coder != "":
                sql += " and code_image.owner=? "
                parameters.append(coder)
            if search_text != "":
                sql += " and code_image.memo like ? "
                parameters.append("%" + str(search_text) + "%")
            if parameters == []:
                cur.execute(sql)
            else:
                #logger.info("SQL:" + sql)
                #logger.info("Parameters:" + str(parameters))
                cur.execute(sql, parameters)
            result = cur.fetchall()
            for row in result:
                self.image_results.append(row)

            # coded audio and video
            parameters = []
            sql = "select code_name.name, color, cases.name, "
            sql += "code_av.pos0, code_av.pos1, code_av.memo, code_av.owner,source.mediapath, "
            sql += "source.id from "
            sql += "code_av join code_name on code_name.cid = code_av.cid "
            sql += "join (case_text join cases on cases.caseid = case_text.caseid) on "
            sql += "code_av.id = case_text.fid "
            sql += " join source on case_text.fid = source.id "
            sql += "where code_name.cid in (" + code_ids + ") "
            sql += "and case_text.caseid in (" + self.case_ids + ") "
            if coder != "":
                sql += " and code_av.owner=? "
                parameters.append(coder)
            if search_text != "":
                sql += " and code_av.memo like ? "
                parameters.append("%" + str(search_text) + "%")
            if parameters == []:
                cur.execute(sql)
            else:
                #logger.info("SQL:" + sql)
                #logger.info("Parameters:" + str(parameters))
                cur.execute(sql, parameters)
            result = cur.fetchall()
            for row in result:
                self.av_results.append(row)

        # get coded text and images from attribute selection
        if self.attribute_selection != []:
            logger.debug("attributes:" + str(self.attribute_selection))
            # convert each row into sql and add to case or file lists
            file_sql = []
            case_sql = []
            for a in self.attribute_selection:
                #print(a)
                sql = " select id from attribute where attribute.name = '" + a[0] + "' "
                sql += " and attribute.value " + a[3] + " "
                if a[3] in ('in', 'not in', 'between'):
                    sql += "("
                sql += ','.join(a[4])
                if a[3] in ('in', 'not in', 'between'):
                    sql += ")"
                if a[2] == 'numeric':
                    sql = sql.replace(' attribute.value ', ' cast(attribute.value as real) ')
                if a[1] == "file":
                    sql += " and attribute.attr_type='file' "
                    file_sql.append(sql)
                else:
                    sql += " and attribute.attr_type='case' "
                    case_sql.append(sql)

            # find file_ids matching criteria, nested sqls for each parameter
            sql = ""
            if len(file_sql) > 0:
                sql = file_sql[0]
                del file_sql[0]
            while len(file_sql) > 0:
                    sql += " and id in ( " + file_sql[0] + ") "
                    del file_sql[0]
            logger.debug(sql)
            cur.execute(sql)
            result = cur.fetchall()
            file_ids = ""
            for i in result:
                file_ids += "," + str(i[0])
            if len(file_ids) > 0:
                file_ids = file_ids[1:]
            logger.debug("file_ids: " + file_ids)

            # find case_ids matching criteria, nested sqls for each parameter
            # can get multiple case ids
            sql = ""
            if len(case_sql) > 0:
                sql = case_sql[0]
                del case_sql[0]
            while len(case_sql) > 0:
                    sql += " and id in ( " + case_sql[0] + ") "
                    del case_sql[0]
            logger.debug(sql)
            cur.execute(sql)
            result = cur.fetchall()
            case_ids = ""
            for i in result:
                case_ids += "," + str(i[0])
            if len(case_ids) > 0:
                case_ids = case_ids[1:]
            logger.debug("case_ids: " + case_ids)

            # text from attribute selection
            sql = ""
            # first sql is for cases with/without file parameters
            if case_ids != "":
                sql = "select code_name.name, color, cases.name, "
                sql += "code_text.pos0, code_text.pos1, seltext, code_text.owner, code_text.fid from "
                sql += "code_text join code_name on code_name.cid = code_text.cid "
                sql += "join (case_text join cases on cases.caseid = case_text.caseid) on "
                sql += "code_text.fid = case_text.fid "
                sql += "where code_name.cid in (" + code_ids + ") "
                sql += "and case_text.caseid in (" + case_ids + ") "
                sql += "and (code_text.pos0 >= case_text.pos0 and code_text.pos1 <= case_text.pos1) "
                if file_ids != "":
                    sql += "and code_text.fid in (" + file_ids + ") "
            else:
                # second sql is for file parameters only
                sql = "select code_name.name, color, source.name, pos0, pos1, seltext, "
                sql += "code_text.owner, fid from code_text join code_name "
                sql += "on code_name.cid = code_text.cid join source on fid = source.id "
                sql += "where code_name.cid in (" + code_ids + ") "
                sql += "and source.id in (" + file_ids + ") "
            if coder != "":
                sql += " and code_text.owner=? "
                parameters.append(coder)
            if search_text != "":
                sql += " and seltext like ? "
                parameters.append("%" + str(search_text) + "%")
            if parameters == []:
                cur.execute(sql)
            else:
                cur.execute(sql, parameters)
            result = cur.fetchall()
            for row in result:
                self.text_results.append(row)

            # images from attribute selection
            sql = ""
            # first sql is for cases with/without file parameters
            if case_ids != "":
                sql = "select code_name.name, color, cases.name, "
                sql += "x1, y1, width, height, code_image.owner,source.mediapath, source.id, code_image.memo "
                sql += "from code_image join code_name on code_name.cid = code_image.cid "
                sql += "join (case_text join cases on cases.caseid = case_text.caseid) on "
                sql += "code_image.id = case_text.fid "
                sql += " join source on case_text.fid = source.id "
                sql += "where code_name.cid in (" + code_ids + ") "
                sql += "and case_text.caseid in (" + case_ids + ") "
                if file_ids != "":
                    sql += "and case_text.fid in (" + file_ids + ") "
            else:
                # second sql is for file parameters only
                sql = "select code_name.name, color, source.name, x1, y1, width, height,"
                sql += "code_image.owner, source.mediapath, source.id, code_image.memo "
                sql += " from code_image join code_name "
                sql += "on code_name.cid = code_image.cid join source on code_image.id = source.id "
                sql += "where code_name.cid in (" + code_ids + ") "
                sql += "and source.id in (" + file_ids + ") "
            if coder != "":
                sql += " and code_image.owner=? "
            if search_text != "":
                sql += " and code_image.memo like ? "
                parameters.append("%" + str(search_text) + "%")
                parameters.append(coder)
            if parameters == []:
                cur.execute(sql)
            else:
                #logger.info("SQL:" + sql)
                #logger.info("Parameters:" + str(parameters))
                cur.execute(sql, parameters)
            result = cur.fetchall()
            for row in result:
                self.image_results.append(row)

            # audio and video from attribute selection
            sql = ""
            # first sql is for cases with/without file parameters
            if case_ids != "":
                sql = "select code_name.name, color, cases.name, "
                sql += "code_av.pos0, code_av.pos1, code_av.memo, code_av.owner,"
                sql += "source.mediapath, source.id from "
                sql += "code_av join code_name on code_name.cid = code_av.cid "
                sql += "join (case_text join cases on cases.caseid = case_text.caseid) on "
                sql += "code_av.id = case_text.fid "
                sql += " join source on case_text.fid = source.id "
                sql += "where code_name.cid in (" + code_ids + ") "
                sql += "and case_text.caseid in (" + case_ids + ") "
                if file_ids != "":
                    sql += "and case_text.fid in (" + file_ids + ") "
            else:
                # second sql is for file parameters only
                sql = "select code_name.name, color, source.name, code_av.pos0, "
                sql += "code_av.pos1, code_av.memo,"
                sql += "code_av.owner, source.mediapath, source.id from code_av join code_name "
                sql += "on code_name.cid = code_av.cid join source on code_av.id = source.id "
                sql += "where code_name.cid in (" + code_ids + ") "
                sql += "and source.id in (" + file_ids + ") "
            if coder != "":
                sql += " and code_av.owner=? "
                parameters.append(coder)
            if search_text != "":
                sql += " and code_av.memo like ? "
                parameters.append("%" + str(search_text) + "%")
            if parameters == []:
                cur.execute(sql)
            else:
                #logger.info("SQL:" + sql)
                #logger.info("Parameters:" + str(parameters))
                cur.execute(sql, parameters)
            result = cur.fetchall()
            for row in result:
                self.av_results.append(row)

        fileOrCase = ""  # default for attributes selection
        if self.file_ids != "":
            fileOrCase = "File"
        if self.case_ids != "":
            fileOrCase = "Case"

        # convert results to dictionaries for ease of use
        tmp = []
        for i in self.text_results:
            tmp.append({'codename': i[0], 'color': i[1], 'file_or_casename': i[2], 'pos0': i[3],
                'pos1': i[4], 'text': i[5], 'coder': i[6], 'fid': i[7], 'file_or_case': fileOrCase})
        self.text_results = tmp
        tmp = []
        for i in self.image_results:
            tmp.append({'codename': i[0], 'color': i[1], 'file_or_casename': i[2], 'x1': i[3],
                'y1': i[4], 'width': i[5], 'height': i[6], 'coder': i[7], 'mediapath': i[8],
                'fid': i[9], 'memo': i[10], 'file_or_case': fileOrCase})
        self.image_results = tmp
        tmp = []
        for i in self.av_results:
            # prepare additional text describing coded segment
            text = ""
            if i[7] is None:
                msg = "Should not have a None value for a/v media name.\n"
                msg += str(i)
                msg += "\nFirst backup project then: delete from code_av where id=" + str(i[9])
                QtWidgets.QMessageBox.information(None, _("No media name in AV results"), msg)
                logger.error("None value for a/v media name in AV results\n" + str(i))
            if i[7] is not None:
                text = i[7][1:] + ": "
            secs0 = int(i[3] / 1000)
            mins = int(secs0 / 60)
            remainder_secs = str(secs0 - mins * 60)
            if len(remainder_secs) == 1:
                remainder_secs = "0" + remainder_secs
            text += " [" + str(mins) + "." + remainder_secs
            secs1 = int(i[4] / 1000)
            mins = int(secs1 / 60)
            remainder_secs = str(secs1 - mins * 60)
            if len(remainder_secs) == 1:
                remainder_secs = "0" + remainder_secs
            text += " - " + str(mins) + "." + remainder_secs + "]"
            self.html_links.append({'imagename': None, 'image': None,
                'avname': i[7], 'av0': str(secs0), 'av1': str(secs1), 'avtext': text})
            if len(i[5]) > 0:
                text += "\nMemo: " + i[5]
            tmp.append({'codename': i[0], 'color': i[1], 'file_or_casename': i[2],
            'pos0': i[3], 'pos1': i[4], 'memo': i[5], 'coder': i[6], 'mediapath': i[7],
                'fid': i[8], 'file_or_case': fileOrCase, 'text': text})
        self.av_results = tmp

        # Put results into the textEdit.document
        for row in self.text_results:
            self.ui.textEdit.insertHtml(self.html_heading(row))
            self.ui.textEdit.insertPlainText(row['text'] + "\n")
        for i, row in enumerate(self.image_results):
            self.ui.textEdit.insertHtml(self.html_heading(row))
            self.put_image_into_textedit(row, i, self.ui.textEdit)
        for i, row in enumerate(self.av_results):
            self.ui.textEdit.insertHtml(self.html_heading(row))
            self.ui.textEdit.insertPlainText(row['text'] + "\n")
        # Need to resize splitter as it automatically adjusts to 50%/50%
        self.ui.splitter.setSizes([100, 300])

        # Fill case matrix
        if self.case_ids != "":
            self.fill_matrix(self.text_results, self.image_results, self.av_results, self.case_ids)

    def put_image_into_textedit(self, img, counter, text_edit):
        """ Scale image, add resource to document, insert image.
        """

        path = self.settings['path'] + img['mediapath']
        document = text_edit.document()
        image = QtGui.QImageReader(path).read()
        image = image.copy(img['x1'], img['y1'], img['width'], img['height'])
        # scale to max 300 wide or high. perhaps add option to change maximum limit?
        scaler = 1.0
        scaler_w = 1.0
        scaler_h = 1.0
        if image.width() > 300:
            scaler_w = 300 / image.width()
        if image.height() > 300:
            scaler_h = 300 / image.height()
        if scaler_w < scaler_h:
            scaler = scaler_w
        else:
            scaler = scaler_h
        # need unique image names or the same image from the same path is reproduced
        imagename = self.settings['path'] + '/images/' + str(counter) + '-' + img['mediapath']
        url = QtCore.QUrl(imagename)
        document.addResource(QtGui.QTextDocument.ImageResource, url, QtCore.QVariant(image))
        cursor = text_edit.textCursor()
        image_format = QtGui.QTextImageFormat()
        image_format.setWidth(image.width() * scaler)
        image_format.setHeight(image.height() * scaler)
        image_format.setName(url.toString())
        cursor.insertImage(image_format)
        text_edit.insertHtml("<br />")
        self.html_links.append({'imagename': imagename, 'image': image,
            'avname': None, 'av0': None, 'av1': None, 'avtext': None})
        if img['memo'] != "":
            text_edit.insertPlainText(_("Memo: ") + img['memo'] + "\n")

    @staticmethod
    def html_heading(item):
        """ Takes a dictionary item and creates a heading for the coded text portion.
        """

        html = "<br /><em><span style=\"background-color:" + item['color'] + "\">" + item['codename'] + "</span>, "
        html += " "+ item['file_or_case'] + ": " + item['file_or_casename'] + ", " + item['coder'] + "</em><br />"
        return html

    def fill_matrix(self, text_results, image_results, av_results, case_ids):
        """ Fill a tableWidget with rows of cases and columns of categories.
        First identify top-lvel categories and codes. Then map all other codes to the
        top-level cataegories. Fill tableWidget with columns of top-level items and rows
        of cases. """

        self.ui.splitter.setSizes([0, 300, 300])

        # get top level categories and codes
        items = self.ui.treeWidget.selectedItems()
        top_level = []
        horizontal_labels = []
        sub_codes = []
        for item in items:
            root = self.ui.treeWidget.indexOfTopLevelItem(item)
            #print(item.text(0), item.text(1), "root", root)
            if root > -1:
                top_level.append({'name': item.text(0), 'cat_or_cid': item.text(1)})
                horizontal_labels.append(item.text(0))
            #find sub-code and traverse upwards to map to top-level category
            if root == -1 and item.text(1)[0:3] == 'cid':
                #print("sub", item.text(0), item.text(1))
                not_top = True
                sub_code = {'codename': item.text(0), 'cid': item.text(1)}
                while not_top:
                    item = item.parent()
                    if self.ui.treeWidget.indexOfTopLevelItem(item) > -1:
                        not_top = False
                        sub_code['top'] = item.text(0)
                        sub_codes.append(sub_code)

        # add the top-level name - which will match the tableWidget column name
        for i in text_results:
            # this assumes the code is already a top-level name (i.e. column in tableWidget)
            i['top'] = i['codename']
            # this replaces the top-level name by mapping to the correct top-level category (i.e. column)
            for s in sub_codes:
                if i['codename'] == s['codename']:
                    i['top'] = s['top']
        for i in image_results:
            # this assumes the code is already a top-level name (i.e. column in tableWidget)
            i['top'] = i['codename']
            # this replaces the top-level name by mapping to the correct top-level category (i.e. column)
            for s in sub_codes:
                if i['codename'] == s['codename']:
                    i['top'] = s['top']
        for i in av_results:
            # this assumes the code is already a top-level name (i.e. column in tableWidget)
            i['top'] = i['codename']
            # this replaces the top-level name by mapping to the correct top-level category (i.e. column)
            for s in sub_codes:
                if i['codename'] == s['codename']:
                    i['top'] = s['top']

        cur = self.settings['conn'].cursor()
        cur.execute("select caseid, name from cases where caseid in (" + case_ids + ")")
        cases = cur.fetchall()
        vertical_labels = []
        for c in cases:
            vertical_labels.append(c[1])
        self.ui.tableWidget.setColumnCount(len(horizontal_labels))
        self.ui.tableWidget.setHorizontalHeaderLabels(horizontal_labels)
        self.ui.tableWidget.setRowCount(len(cases))
        self.ui.tableWidget.setVerticalHeaderLabels(vertical_labels)
        for row, case in enumerate(cases):
            for col, colname in enumerate(horizontal_labels):
                txt_edit = QtWidgets.QTextEdit("")
                for t in text_results:
                    if t['file_or_casename'] == vertical_labels[row] and t['top'] == horizontal_labels[col]:
                        txt_edit.insertHtml(self.html_heading(t))
                        txt_edit.insertPlainText(t['text'] + "\n")
                for a in av_results:
                    if a['file_or_casename'] == vertical_labels[row] and a['top'] == horizontal_labels[col]:
                        txt_edit.insertHtml(self.html_heading(a))
                        txt_edit.insertPlainText(a['text'] + "\n")
                for counter, i in enumerate(image_results):
                    if i['file_or_casename'] == vertical_labels[row] and i['top'] == horizontal_labels[col]:
                        txt_edit.insertHtml(self.html_heading(i))
                        self.put_image_into_textedit(i, counter, txt_edit)
                self.ui.tableWidget.setCellWidget(row, col, txt_edit)
        self.ui.tableWidget.resizeColumnsToContents()
        self.ui.tableWidget.resizeRowsToContents()

    def select_attributes(self):
        """ Select attributes from case or file attributes for search method.
        Text values will be quoted.print("i[7]:  ", i[7])  # tmp
        """

        self.ui.splitter.setSizes([300, 300, 0])
        self.file_ids = ""
        self.case_ids = ""
        ui = DialogSelectAttributeParameters(self.settings)
        ok = ui.exec_()
        if not ok:
            self.attribute_selection = []
            return
        self.attribute_selection = ui.parameters
        label = _("Attributes: ")
        logger.debug("Attributes selected:" + str(self.attribute_selection))
        for att in self.attribute_selection:
            label += att[0] + " " + att[3] + " "
            label += ','.join(att[4])
            label += "; "
        self.ui.label_selections.setText(label)

    def select_files(self):
        """ When select file button is pressed a dialog of filenames is presented to the user.
        The selected files are then used when searching for codings
        If files are selected, then selected cases are cleared.
        The default is all file ids.
        To revert to default after files are selected,
        the user must press select files button then cancel the dialog.
        """

        self.ui.splitter.setSizes([300, 300, 0])
        self.ui.pushButton_fileselect.setToolTip("")
        self.ui.pushButton_caseselect.setToolTip("")
        filenames = []
        self.file_ids = ""
        self.case_ids = ""
        self.attribute_selection = []
        cur = self.settings['conn'].cursor()
        cur.execute("select id, name from source")
        result = cur.fetchall()
        for row in result:
            filenames.append({'id': row[0], 'name': row[1]})
            self.file_ids += "," + str(row[0])
        if len(self.file_ids) > 0:
            self.file_ids = self.file_ids[1:]

        ui = DialogSelectFile(filenames, _("Select files to view"), "many")
        ok = ui.exec_()
        tooltip = _("Files selected:")
        if ok:
            tmp_ids = ""
            selectedFiles = ui.get_selected()  # list of dictionaries
            for row in selectedFiles:
                tmp_ids += "," + str(row['id'])
                tooltip += " " + row['name']
            if len(tmp_ids) > 0:
                self.file_ids = tmp_ids[1:]
                self.ui.pushButton_fileselect.setToolTip(tooltip)
                self.ui.label_selections.setText(tooltip)
            else:
                self.ui.label_selections.setText(_("Files selected: All"))

    def select_cases(self):
        """ When select case button is pressed a dialog of case names is presented to the user.
        The selected cases are then used when searching for codings.
        If cases are selected, then selected files are cleared.
        If neither are selected the default is all files are selected.
        """

        self.ui.splitter.setSizes([300, 300, 0])
        self.ui.pushButton_fileselect.setToolTip("")
        self.ui.pushButton_caseselect.setToolTip("")
        casenames = []
        self.file_ids = ""
        self.case_ids = ""
        self.attribute_selection = []
        cur = self.settings['conn'].cursor()
        cur.execute("select caseid, name from cases")
        result = cur.fetchall()
        for row in result:
            casenames.append({'caseid': row[0], 'name': row[1]})
        ui = DialogSelectFile(casenames, _("Select cases to view"), "many")
        ok = ui.exec_()
        tooltip = _("Cases selected:")
        if ok:
            tmp_ids = ""
            selectedCases = ui.get_selected()  # list of dictionaries
            for row in selectedCases:
                tmp_ids += "," + str(row['caseid'])
                tooltip += " " + row['name']
            if len(tmp_ids) > 0:
                self.case_ids = tmp_ids[1:]
                self.ui.pushButton_caseselect.setToolTip(tooltip)
                self.ui.label_selections.setText(tooltip)




