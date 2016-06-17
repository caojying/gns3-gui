# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 GNS3 Technologies Inc.
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

"""
IOU device implementation.
"""

import os
import re
from gns3.node import Node
from gns3.ports.ethernet_port import EthernetPort
from gns3.ports.serial_port import SerialPort
from gns3.utils.normalize_filename import normalize_filename
from gns3.image_manager import ImageManager
from .settings import IOU_DEVICE_SETTINGS

import logging
log = logging.getLogger(__name__)


class IOUDevice(Node):

    """
    IOU device.

    :param module: parent module for this node
    :param server: GNS3 server instance
    :param project: Project instance
    """

    URL_PREFIX = "iou"

    def __init__(self, module, server, project):
        super().__init__(module, server, project)

        log.info("IOU instance is being created")
        self._node_id = None

        iou_device_settings = {"path": "",
                               "md5sum": "",
                               "startup_config": "",
                               "private_config": "",
                               "l1_keepalives": False,
                               "use_default_iou_values": IOU_DEVICE_SETTINGS["use_default_iou_values"],
                               "ram": IOU_DEVICE_SETTINGS["ram"],
                               "nvram": IOU_DEVICE_SETTINGS["nvram"],
                               "ethernet_adapters": IOU_DEVICE_SETTINGS["ethernet_adapters"],
                               "serial_adapters": IOU_DEVICE_SETTINGS["serial_adapters"],
                               "console": None,
                               "console_host": None,
                               "iourc_content": None}

        self.settings().update(iou_device_settings)

    def _addAdapters(self, nb_ethernet_adapters, nb_serial_adapters):
        """
        Adds ports based on what adapter is inserted in which slot.

        :param nb_ethernet_adapters: number of Ethernet adapters
        :param nb_serial_adapters: number of Serial adapters
        """

        nb_adapters = nb_ethernet_adapters + nb_serial_adapters
        for slot_number in range(0, nb_adapters):
            for port_number in range(0, 4):
                if slot_number < nb_ethernet_adapters:
                    port = EthernetPort
                else:
                    port = SerialPort
                port_name = port.longNameType() + str(slot_number) + "/" + str(port_number)
                short_name = port.shortNameType() + str(slot_number) + "/" + str(port_number)
                new_port = port(port_name)
                new_port.setShortName(short_name)
                new_port.setPortNumber(port_number)
                new_port.setAdapterNumber(slot_number)
                self._ports.append(new_port)
                log.debug("port {} has been added".format(port_name))

    def _removeAdapters(self, nb_ethernet_adapters, nb_serial_adapters):
        """
        Removes ports when an adapter is removed from a slot.

        :param slot_number: slot number (integer)
        """

        for port in self._ports.copy():
            if (port.adapterNumber() >= nb_ethernet_adapters and port.linkType() == "Ethernet") or \
                    (port.adapterNumber() >= nb_serial_adapters and port.linkType() == "Serial"):
                self._ports.remove(port)
                log.info("port {} has been removed".format(port.name()))

    def create(self, iou_path, name=None, node_id=None, additional_settings={}, default_name_format="IOU{0}"):
        """
        Creates this IOU device.

        :param iou_path: path to an IOU image
        :param name: optional name
        :param console: optional TCP console port
        """


        params = {"path": iou_path}
        # push the startup-config
        if "startup_config" in additional_settings:
            base_config_content = self._readBaseConfig(additional_settings["startup_config"])
            if base_config_content is not None:
                params["startup_config_content"] = base_config_content
            del additional_settings["startup_config"]

        # push the startup-config
        if "private_config" in additional_settings:
            base_config_content = self._readBaseConfig(additional_settings["private_config"])
            if base_config_content is not None:
                params["private_config_content"] = base_config_content
            del additional_settings["private_config"]

        params = self._addIourcContentToParams(params)
        params.update(additional_settings)
        self._create(name, node_id, params, default_name_format)

    def _createCallback(self, result):
        """
        Callback for create.

        :param result: server response
        """

        # create the ports on the client side
        self._addAdapters(self._settings.get("ethernet_adapters", 0), self._settings.get("serial_adapters", 0))

    def start(self):
        """
        Starts this VM instance.
        """

        if self.status() == Node.started:
            log.debug("{} is already running".format(self.name()))
            return

        params = {}
        params = self._addIourcContentToParams(params)

        log.debug("{} is starting".format(self.name()))
        self.controllerHttpPost("/nodes/{node_id}/start".format(node_id=self._node_id), self._startCallback, progressText="{} is starting".format(self.name()))

    def _addIourcContentToParams(self, params):
        """
        If an IOURC file exist push it when starting the IOU device
        """
        # push the iourc file
        module_settings = self._module.settings()
        if module_settings["iourc_path"] and os.path.isfile(module_settings["iourc_path"]):
            try:
                with open(module_settings["iourc_path"], "rb") as f:
                    params["iourc_content"] = f.read().decode("utf-8")
            except OSError as e:
                log.error("Can't open iourc file {}: {}".format(module_settings["iourc_path"], e))
            except UnicodeDecodeError as e:
                log.error("Invalid IOURC file {}: {}".format(module_settings["iourc_path"], e))
        return params

    def update(self, new_settings):
        """
        Updates the settings for this IOU device.

        :param new_settings: settings dictionary
        """

        params = {}
        if "startup_config" in new_settings:
            base_config_content = self._readBaseConfig(new_settings["startup_config"])
            if base_config_content is not None:
                params["startup_config_content"] = base_config_content
            del new_settings["startup_config"]

        if "private_config" in new_settings:
            base_config_content = self._readBaseConfig(new_settings["private_config"])
            if base_config_content is not None:
                params["private_config_content"] = base_config_content
            del new_settings["private_config"]

        for name, value in new_settings.items():
            if name in self._settings and self._settings[name] != value:
                params[name] = value

        if params:
            self._update(params)

    def _updateCallback(self, result):
        """
        Callback for update.

        :param result: server response
        """

        nb_adapters_changed = False
        for name, value in result.items():
            if name in self._settings and self._settings[name] != value:
                log.info("{}: updating {} from '{}' to '{}'".format(self.name(), name, self._settings[name], value))
                if name == "ethernet_adapters" or name == "serial_adapters":
                    nb_adapters_changed = True
                self._settings[name] = value

        if nb_adapters_changed:
            log.debug("number of adapters has changed: Ethernet={} Serial={}".format(self._settings["ethernet_adapters"], self._settings["serial_adapters"]))
            # TODO: dynamically add/remove adapters
            self._ports.clear()
            self._addAdapters(self._settings["ethernet_adapters"], self._settings["serial_adapters"])

    def info(self):
        """
        Returns information about this IOU device.

        :returns: formated string
        """

        if self.status() == Node.started:
            state = "started"
        else:
            state = "stopped"

        if self._settings["use_default_iou_values"]:
            memories_info = "default RAM and NVRAM IOU values"
        else:
            memories_info = "{ram} MB RAM and {nvram} KB NVRAM".format(ram=self._settings["ram"],
                                                                       nvram=self._settings["nvram"])

        info = """Device {name} is {state}
  Node ID is {id}, server's IOU device ID is {node_id}
  Hardware is Cisco IOU generic device with {memories_info}
  Device's server runs on {host}, console is on port {console}
  Image is {image_name}
  {nb_ethernet} Ethernet adapters and {nb_serial} serial adapters installed
""".format(name=self.name(),
           id=self.id(),
           node_id=self._node_id,
           state=state,
           memories_info=memories_info,
           host=self.compute().id(),
           console=self._settings["console"],
           image_name=os.path.basename(self._settings["path"]),
           nb_ethernet=self._settings["ethernet_adapters"],
           nb_serial=self._settings["serial_adapters"])

        port_info = ""
        for port in self._ports:
            if port.isFree():
                port_info += "     {port_name} is empty\n".format(port_name=port.name())
            else:
                port_info += "     {port_name} {port_description}\n".format(port_name=port.name(),
                                                                            port_description=port.description())

        return info + port_info

    def saveConfig(self):
        """
        Save the configs
        """

        self.httpPost("/iou/nodes/{node_id}/configs/save".format(node_id=self._node_id), self._saveConfigCallback)

    def _saveConfigCallback(self, result, error=False, context={}, **kwargs):

        if error:
            log.error("error while saving {} configs: {}".format(self.name(), result["message"]))
            self.server_error_signal.emit(self.id(), result["message"])
        else:
            log.info("{}: configs have been saved".format(self.name()))

    def exportConfig(self, startup_config_export_path, private_config_export_path):
        """
        Exports the startup-config and private-config.

        :param startup_config_export_path: export path for the startup-config
        :param private_config_export_path: export path for the private-config
        """

        self.httpGet("/iou/nodes/{node_id}/configs".format(node_id=self._node_id),
                     self._exportConfigCallback,
                     context={"startup_config_path": startup_config_export_path,
                              "private_config_path": private_config_export_path})

    def _exportConfigCallback(self, result, error=False, context={}, **kwargs):
        """
        Callback for exportConfig.

        :param result: server response
        :param error: indicates an error (boolean)
        """

        if error:
            log.error("error while exporting {} IOU configs: {}".format(self.name(), result["message"]))
            self.server_error_signal.emit(self.id(), result["message"])
        else:
            startup_config_path = context["startup_config_path"]
            private_config_path = context["private_config_path"]
            if startup_config_path:
                try:
                    with open(startup_config_path, "wb") as f:
                        log.info("saving {} startup-config to {}".format(self.name(), startup_config_path))
                        if "startup_config_content" in result and result["startup_config_content"]:
                            f.write(result["startup_config_content"].encode("utf-8"))
                except OSError as e:
                    self.error_signal.emit(self.id(), "Could not export startup-config to {}: {}".format(startup_config_path, e))

            if private_config_path:
                try:
                    with open(private_config_path, "wb") as f:
                        log.info("saving {} private-config to {}".format(self.name(), private_config_path))
                        if "private_config_content" in result and result["private_config_content"]:
                            f.write(result["private_config_content"].encode("utf-8"))
                except OSError as e:
                    self.error_signal.emit(self.id(), "Could not export private-config to {}: {}".format(private_config_path, e))

    def exportConfigToDirectory(self, directory):
        """
        Exports the initial-config to a directory.

        :param directory: destination directory path
        """

        self.httpGet("/iou/nodes/{node_id}/configs".format(node_id=self._node_id),
                     self._exportConfigToDirectoryCallback,
                     context={"directory": directory})

    def _exportConfigToDirectoryCallback(self, result, error=False, context={}, **kwargs):
        """
        Callback for exportConfigToDirectory.

        :param result: server response
        :param error: indicates an error (boolean)
        """

        if error:
            log.error("error while exporting {} IOU configs: {}".format(self.name(), result["message"]))
            self.server_error_signal.emit(self.id(), result["message"])
            return
        export_directory = context["directory"]

        if "startup_config_content" in result:
            startup_config_path = os.path.join(export_directory, normalize_filename(self.name())) + "_startup-config.cfg"
            try:
                with open(startup_config_path, "wb") as f:
                    log.info("saving {} startup-config to {}".format(self.name(), startup_config_path))
                    if result["startup_config_content"]:
                        f.write(result["startup_config_content"].encode("utf-8"))
            except OSError as e:
                self.error_signal.emit(self.id(), "could not export startup-config to {}: {}".format(startup_config_path, e))

        if "private_config_content" in result:
            private_config_path = os.path.join(export_directory, normalize_filename(self.name())) + "_private-config.cfg"
            try:
                with open(private_config_path, "wb") as f:
                    log.info("saving {} private-config to {}".format(self.name(), private_config_path))
                    if result["private_config_content"]:
                        f.write(result["private_config_content"].encode("utf-8"))
            except OSError as e:
                self.error_signal.emit(self.id(), "could not export private-config to {}: {}".format(startup_config_path, e))

    def importConfig(self, path):
        """
        Imports a startup-config.

        :param path: path to the startup-config
        """

        new_settings = {"startup_config": path}
        self.update(new_settings)

    def importPrivateConfig(self, path):
        """
        Imports a private-config.

        :param path: path to the private-config
        """

        new_settings = {"private_config": path}
        self.update(new_settings)

    def importConfigFromDirectory(self, directory):
        """
        Imports IOU configs from a directory.

        :param directory: source directory path
        """

        contents = os.listdir(directory)
        startup_config = normalize_filename(self.name()) + "_startup-config.cfg"
        private_config = normalize_filename(self.name()) + "_private-config.cfg"
        new_settings = {}
        if startup_config in contents:
            new_settings["startup_config"] = os.path.join(directory, startup_config)
        else:
            self.warning_signal.emit(self.id(), "no startup-config file could be found, expected file name: {}".format(startup_config))

        if private_config in contents:
            new_settings["private_config"] = os.path.join(directory, private_config)
        else:
            # private-config is optional
            log.debug("{}: no private-config file could be found, expected file name: {}".format(self.name(), private_config))

        if new_settings:
            self.update(new_settings)

    def console(self):
        """
        Returns the console port for this IOU device.

        :returns: port (integer)
        """

        return self._settings["console"]

    def configPage(self):
        """
        Returns the configuration page widget to be used by the node properties dialog.

        :returns: QWidget object
        """

        from .pages.iou_device_configuration_page import iouDeviceConfigurationPage
        return iouDeviceConfigurationPage

    @staticmethod
    def validateHostname(hostname):
        """
        Checks if the hostname is valid.

        :param hostname: hostname to check

        :returns: boolean
        """

        # IOS names must start with a letter, end with a letter or digit, and
        # have as interior characters only letters, digits, and hyphens.
        # They must be 63 characters or fewer.
        if re.search(r"""^[\-\w]+$""", hostname) and len(hostname) <= 63:
            return True
        return False

    @staticmethod
    def defaultSymbol():
        """
        Returns the default symbol path for this node.

        :returns: symbol path (or resource).
        """

        return ":/symbols/multilayer_switch.svg"

    @staticmethod
    def symbolName():

        return "IOU device"

    @staticmethod
    def categories():
        """
        Returns the node categories the node is part of (used by the device panel).

        :returns: list of node categories
        """

        return [Node.routers, Node.switches]

    def __str__(self):

        return "IOU device"
