# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 GNS3 Technologies Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
from ..qt import QtCore, QtGui, QtWidgets
from ..ui.project_dialog_ui import Ui_ProjectDialog
from ..controller import Controller
from ..topology import Topology


import logging
log = logging.getLogger(__name__)


class ProjectDialog(QtWidgets.QDialog, Ui_ProjectDialog):

    """
    New project dialog.
    """

    def __init__(self, parent, default_project_name="untitled", show_open_options=True):
        """
        :param parent: parent widget.
        :param default_project_name: Project name by default
        :param show_open_options: If true allow to open a project from the dialog
        otherwise it's just for create a project
        """
        super().__init__(parent)
        self.setupUi(self)

        self._main_window = parent
        self._projects = []
        self._project_settings = {}
        self.uiNameLineEdit.setText(default_project_name)
        self.uiLocationLineEdit.setText(os.path.join(Topology.instance().projectsDirPath(), default_project_name))

        self.uiNameLineEdit.textEdited.connect(self._projectNameSlot)
        self.uiLocationBrowserToolButton.clicked.connect(self._projectPathSlot)
        self.uiSettingsPushButton.clicked.connect(self._settingsClickedSlot)

        if show_open_options:
            self.uiOpenProjectPushButton.clicked.connect(self._openProjectActionSlot)
            self.uiRecentProjectsPushButton.clicked.connect(self._showRecentProjectsSlot)
        else:
            self.uiOpenProjectGroupBox.hide()
            self.uiProjectTabWidget.removeTab(1)

        # If the controller is remote we hide option for local file system
        if Controller.instance().isRemote():
            self.uiLocationLabel.setVisible(False)
            self.uiLocationLineEdit.setVisible(False)
            self.uiLocationBrowserToolButton.setVisible(False)
            self.uiOpenProjectPushButton.setVisible(False)
        Controller.instance().connected_signal.connect(self._refreshProjects)

        self.uiProjectsTreeWidget.itemDoubleClicked.connect(self._projectsTreeWidgetDoubleClickedSlot)
        self.uiDeleteProjectButton.clicked.connect(self._deleteProjectSlot)
        self.uiRefreshProjectsPushButton.clicked.connect(self._refreshProjects)
        self._refreshProjects()

    def _refreshProjects(self):
        Controller.instance().get("/projects", self._projectListCallback)

    def _settingsClickedSlot(self):
        """
        When the user click on the settings button
        """
        self.reject()
        self._main_window.preferencesActionSlot()

    def _projectsTreeWidgetDoubleClickedSlot(self, item, column):
        self.done(True)

    def _deleteProjectSlot(self):
        current = self.uiProjectsTreeWidget.currentItem()
        if current is None:
            QtWidgets.QMessageBox.critical(self, "Delete project", "No project selected")
            return

        projects_to_delete = set()
        for project in self.uiProjectsTreeWidget.selectedItems():
            project_id = project.data(0, QtCore.Qt.UserRole)
            project_name = project.data(1, QtCore.Qt.UserRole)

            reply = QtWidgets.QMessageBox.warning(self,
                                                  "Delete project",
                                                  'Delete project "{}"?\nThis cannot be reverted.'.format(project_name),
                                                  QtWidgets.QMessageBox.Yes,
                                                  QtWidgets.QMessageBox.No)
            if reply == QtWidgets.QMessageBox.Yes:
                projects_to_delete.add(project_id)

        for project_id in projects_to_delete:
            Controller.instance().delete("/projects/{}".format(project_id), self._deleteProjectCallback)

    def _deleteProjectCallback(self, result, error=False, **kwargs):
        if error:
            log.error("Error while deleting project: {}".format(result["message"]))
            return
        Controller.instance().get("/projects", self._projectListCallback)

    def _projectListCallback(self, result, error=False, **kwargs):
        self.uiProjectsTreeWidget.clear()
        self.uiDeleteProjectButton.setEnabled(False)
        if not error:
            self._projects = result
            self.uiProjectsTreeWidget.setUpdatesEnabled(False)
            items = []
            for project in result:
                path = os.path.join(project["path"], project["filename"])
                item = QtWidgets.QTreeWidgetItem([project["name"], project["status"], path])
                item.setData(0, QtCore.Qt.UserRole, project["project_id"])
                item.setData(1, QtCore.Qt.UserRole, project["name"])
                item.setData(2, QtCore.Qt.UserRole, path)
                items.append(item)
            self.uiProjectsTreeWidget.addTopLevelItems(items)

            if len(result):
                self.uiDeleteProjectButton.setEnabled(True)

            self.uiProjectsTreeWidget.header().setResizeContentsPrecision(100)  # How many row is checked for the resize for performance reason
            self.uiProjectsTreeWidget.resizeColumnToContents(0)
            self.uiProjectsTreeWidget.resizeColumnToContents(1)
            self.uiProjectsTreeWidget.resizeColumnToContents(2)
            self.uiProjectsTreeWidget.sortItems(0, QtCore.Qt.AscendingOrder)
            self.uiProjectsTreeWidget.setUpdatesEnabled(True)

    def keyPressEvent(self, e):
        """
        Event handler in order to properly handle escape.
        """

        if e.key() == QtCore.Qt.Key_Escape:
            self.close()

    def _projectNameSlot(self, text):

        project_dir = Topology.instance().projectsDirPath()
        if os.path.dirname(self.uiLocationLineEdit.text()) == project_dir:
            self.uiLocationLineEdit.setText(os.path.join(project_dir, text))

    def _projectPathSlot(self):
        """
        Slot to select the a new project location.
        """

        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Project location", os.path.join(Topology.instance().projectsDirPath(),
                                                                                               self.uiNameLineEdit.text()))

        if path:
            self.uiNameLineEdit.setText(os.path.basename(path))
            self.uiLocationLineEdit.setText(path)

    def getProjectSettings(self):

        return self._project_settings

    def _menuTriggeredSlot(self, action):
        """
        Closes this dialog when a recent project
        has been opened.

        :param action: ignored.
        """

        self.reject()

    def _openProjectActionSlot(self):
        """
        Opens a project and closes this dialog.
        """

        self._main_window.openProjectActionSlot()
        self.reject()

    def _showRecentProjectsSlot(self):
        """
        lot to show all the recent projects in a menu.
        """

        menu = QtWidgets.QMenu()
        menu.triggered.connect(self._menuTriggeredSlot)
        for action in self._main_window._recent_project_actions:
            menu.addAction(action)
        menu.exec_(QtGui.QCursor.pos())

    def _overwriteProjectCallback(self, result, error=False, **kwargs):
        if error:
            if "message" in result:
                log.error("Error while overwrite project: {}".format(result["message"]))
            return
        self._projects = []
        self._refreshProjects()
        self.done(True)

    def _newProject(self):
        project_name = self.uiNameLineEdit.text()

        if not project_name:
            QtWidgets.QMessageBox.critical(self, "New project", "Project name is empty")
            return False

        for existing_project in self._projects:
            if project_name == existing_project["name"]:
                reply = QtWidgets.QMessageBox.warning(self,
                                                      "New project",
                                                      "Project {} already exists, overwrite it?".format(project_name),
                                                      QtWidgets.QMessageBox.Yes,
                                                      QtWidgets.QMessageBox.No)

                if reply == QtWidgets.QMessageBox.Yes:
                    Controller.instance().delete("/projects/{}".format(existing_project["project_id"]), self._overwriteProjectCallback)

                # In all cases we cancel the new project and if project success to delete
                # we will call done again
                return False

        self._project_settings["project_name"] = project_name

        if not Controller.instance().isRemote():
            project_location = self.uiLocationLineEdit.text()
            if not project_location:
                QtWidgets.QMessageBox.critical(self, "New project", "Project location is empty")
                return False

            self._project_settings["project_path"] = os.path.join(project_location, project_name + ".gns3")
            self._project_settings["project_files_dir"] = project_location
        return True

    def done(self, result):

        if result:
            if self.uiProjectTabWidget.currentIndex() == 0:
                if not self._newProject():
                    return
            else:
                current = self.uiProjectsTreeWidget.currentItem()
                if current is None:
                    QtWidgets.QMessageBox.critical(self, "Open project", "No project selected")
                    return

                self._project_settings["project_id"] = current.data(0, QtCore.Qt.UserRole)
                self._project_settings["project_name"] = current.data(1, QtCore.Qt.UserRole)
                self._project_settings["project_path"] = current.data(2, QtCore.Qt.UserRole)
        super().done(result)