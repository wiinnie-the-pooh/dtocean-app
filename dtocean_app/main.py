# -*- coding: utf-8 -*-

#    Copyright (C) 2016 Mathew Topper, Rui Duarte
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Created on Thu Apr 23 12:51:14 2015

@author: Mathew Topper
"""

# Set up logging
import logging

module_logger = logging.getLogger(__name__)

import os
import sys
import json
import shutil
import tarfile
import tempfile
import traceback
import subprocess

import sip
import pandas as pd
import matplotlib.pyplot as plt
from PyQt4 import QtGui, QtCore

from dtocean_core.menu import ProjectMenu, ModuleMenu, ThemeMenu, DataMenu
from dtocean_core.pipeline import set_output_scope

from .core import GUICore
from .help import HelpWidget
from .menu import DBSelector
from .simulation import SimulationDock
from .extensions import GUIStrategyManager, GUIToolManager
from .pipeline import (PipeLine,
                       SectionItem,
                       HiddenHub,
                       HubItem,
                       InputBranchItem,
                       OutputBranchItem,
                       InputVarItem,
                       OutputVarItem)
from .utils.process import which

from .widgets.central import (ContextArea,
                              DetailsWidget,
                              FileManagerWidget,
                              PlotManagerWidget,
                              LevelComparison,
                              SimulationComparison)
from .widgets.dialogs import (DataCheck,
                              MainWindow,
                              ProjProperties,
                              Shuttle,
                              ProgressBar,
                              About)
from .widgets.display import (MPLWidget,
                              get_current_filetypes,
                              save_current_figure)
from .widgets.docks import (ListDock,
                            LogDock)


class ThreadReadRaw(QtCore.QThread):
    
    """QThread for reading raw data"""
    
    error_detected =  QtCore.pyqtSignal(object, object, object)

    def __init__(self, shell, variable, value):
        
        super(ThreadReadRaw, self).__init__()
        self._shell = shell
        self._variable = variable
        self._value = value
                
        return
    
    def run(self):
        
        try:
        
            self._variable.set_raw_interface(self._shell.core,
                                             self._value)
            self._variable.read(self._shell.core,
                                self._shell.project)
        
        except: 
            
            etype, evalue, etraceback = sys.exc_info()
            self.error_detected.emit(etype, evalue, etraceback)

        return
      

class ThreadDataFlow(QtCore.QThread):
    
    """QThread for initiating the dataflow"""
    
    taskFinished = QtCore.pyqtSignal()
    error_detected =  QtCore.pyqtSignal(object, object, object)

    def __init__(self, pipeline, shell):
        
        super(ThreadDataFlow, self).__init__()
        self.pipeline = pipeline
        self.shell = shell
        
        self.project_menu = ProjectMenu()
        
        return
    
    def run(self):
        
        try:
        
            # Check if filters can be initiated
            if self.shell.project.get_database_credentials() is not None:
                self.project_menu.initiate_filter(self.shell.core,
                                                  self.shell.project)
            
            self.project_menu.initiate_dataflow(self.shell.core,
                                                self.shell.project)
            
            # Execute the project boundaries interface
            if ("Project Boundaries Interface" in
                self.shell.project_menu.get_active(self.shell.core,
                                                   self.shell.project)):
            
                self.shell.project_menu._execute(
                                            self.shell.core,
                                            self.shell.project,
                                            "Project Boundaries Interface")
            
            self.pipeline._read_auto(self.shell)
            
            self.taskFinished.emit()
            
        except: 
            
            etype, evalue, etraceback = sys.exc_info()
            self.error_detected.emit(etype, evalue, etraceback)

        return
        
        
class ThreadCurrent(QtCore.QThread):
    
    """QThread for executing the current module"""
    
    taskFinished = QtCore.pyqtSignal()
    error_detected =  QtCore.pyqtSignal(object, object, object)

    def __init__(self, core, project):
        
        super(ThreadCurrent, self).__init__()
        self._core = core
        self._project = project
        
        self._module_menu = ModuleMenu()
        
        return
    
    def run(self):
        
        try:
        
            self._module_menu.execute_current(self._core,
                                              self._project)
            self.taskFinished.emit()
        
        except: 
            
            etype, evalue, etraceback = sys.exc_info()
            self.error_detected.emit(etype, evalue, etraceback)

        return
        
        
class ThreadThemes(QtCore.QThread):
    
    """QThread for executing all themes"""
    
    taskFinished = QtCore.pyqtSignal()
    error_detected =  QtCore.pyqtSignal(object, object, object)

    def __init__(self, core, project):
        
        super(ThreadThemes, self).__init__()
        self._core = core
        self._project = project
        
        self._theme_menu = ThemeMenu()
        
        return
    
    def run(self):
        
        try:
        
            self._theme_menu.execute_all(self._core,
                                         self._project)
            self.taskFinished.emit()
                                     
        except: 
            
            etype, evalue, etraceback = sys.exc_info()
            self.error_detected.emit(etype, evalue, etraceback)

        return

        
class ThreadStrategy(QtCore.QThread):
    
    """QThread for executing a strategy"""
    
    taskFinished = QtCore.pyqtSignal()
    error_detected =  QtCore.pyqtSignal(object, object, object)

    def __init__(self, strategy, core, project):
        
        super(ThreadStrategy, self).__init__()
        self._strategy = strategy
        self._core = core
        self._project = project
                
        return
    
    def run(self):
        
        try:
            
            self._strategy.execute(self._core,
                                   self._project)
            self.taskFinished.emit()
        
        except: 
            
            etype, evalue, etraceback = sys.exc_info()
            self.error_detected.emit(etype, evalue, etraceback)

        return

        
class ThreadTool(QtCore.QThread):
    
    """QThread for executing dtocean-wec"""
    
    error_detected =  QtCore.pyqtSignal(object, object, object)

    def __init__(self, core, project, tool):
        
        super(ThreadTool, self).__init__()
        self._tool = tool
        self._core = core
        self._project = project
        
        self._tool_manager = GUIToolManager()
                
        return
    
    def run(self):
        
        try:
                    
            self._tool_manager.execute_tool(self._core,
                                            self._project,
                                            self._tool)
                
        except: 
            
            etype, evalue, etraceback = sys.exc_info()
            self.error_detected.emit(etype, evalue, etraceback)

        return


class Shell(QtCore.QObject):
    
    # Signals
    project_activated = QtCore.pyqtSignal()
    project_title_change = QtCore.pyqtSignal(str)
    project_saved = QtCore.pyqtSignal()
    project_closed = QtCore.pyqtSignal()
    modules_activated = QtCore.pyqtSignal()
    themes_activated = QtCore.pyqtSignal()
    update_pipeline = QtCore.pyqtSignal(object)
    update_scope = QtCore.pyqtSignal(str)
    update_widgets = QtCore.pyqtSignal()
    reset_widgets = QtCore.pyqtSignal()
    update_run_action = QtCore.pyqtSignal()
    database_updated = QtCore.pyqtSignal(str)
    pipeline_active = QtCore.pyqtSignal()
    bathymetry_active = QtCore.pyqtSignal()
    filter_active = QtCore.pyqtSignal()
    dataflow_active = QtCore.pyqtSignal()
    module_executed = QtCore.pyqtSignal()
    themes_executed = QtCore.pyqtSignal()
    strategy_executed = QtCore.pyqtSignal()

    def __init__(self):
        
        super(Shell, self).__init__()
        
        self.core = None
        self.project_menu = None
        self.module_menu = None
        self.theme_menu = None
        self.data_menu = None
        self.project = None
        self.project_path = None
        self.strategy = None
        self._active_thread = None
        self._current_scope = None
        
        self.core = self._init_core()
        self.project_menu = self._init_project_menu()
        self.module_menu = self._init_module_menu()
        self.theme_menu = self._init_theme_menu()
        self.data_menu = self._init_data_menu()
        
        # Strategy execution flag change
        self.strategy_executed.connect(self.set_strategy_run)
        
        # Clear active thread after execution
        self.dataflow_active.connect(self._clear_active_thread)
        self.module_executed.connect(self._clear_active_thread)
        self.themes_executed.connect(self._clear_active_thread)
        self.strategy_executed.connect(self._clear_active_thread)
        
        return
    
    def _init_core(self):
        
        core = GUICore()
        
        # Relay status updated signal
        core.status_updated.connect(
            lambda: self.update_pipeline.emit(self))
        core.status_updated.connect(
            lambda: self.reset_widgets.emit())
        
        # Relay pipeline reset signal
        core.pipeline_reset.connect(
            lambda: self.update_run_action.emit())
        
        return core
    
    def _init_project_menu(self):
        
        return ProjectMenu()
        
    def _init_module_menu(self):
        
        return ModuleMenu()
        
    def _init_theme_menu(self):
        
        return ThemeMenu()
        
    def _init_data_menu(self):

        return DataMenu()
        
    def set_project_title(self, title):
        
        self.project.title = title
        self.project_title_change.emit(title)
        
        return
        
    def get_available_modules(self):
        
        available_modules = self.module_menu.get_available(self.core,
                                                           self.project)
                                                            
        return available_modules
        
    def get_active_modules(self):
        
        active_modules = self.module_menu.get_active(self.core,
                                                     self.project)
                                                            
        return active_modules
        
    def get_current_module(self):
        
        module_name = self.module_menu.get_current(self.core,
                                                   self.project)
                                                   
        return module_name
        
    def get_scheduled_modules(self):
        
        module_names = self.module_menu.get_scheduled(self.core,
                                                      self.project)
                                                   
        return module_names
        
    def get_completed_modules(self):
        
        module_names = self.module_menu.get_completed(self.core,
                                                      self.project)
                                                   
        return module_names
        
    def get_available_themes(self):
        
        available_themes = self.theme_menu.get_available(self.core,
                                                         self.project)
                                                            
        return available_themes
        
    def get_active_themes(self):
        
        active_themes = self.theme_menu.get_active(self.core,
                                                   self.project)
                                                            
        return active_themes
        
    def get_scheduled_themes(self):
        
        module_names = self.theme_menu.get_scheduled(self.core,
                                                     self.project)
                                                   
        return module_names
        
    @QtCore.pyqtSlot()
    def new_project(self, title="Untitled project"):
        
        self.project = self.project_menu.new_project(self.core, title)
        self.project_path = None
        
        self.project_activated.emit()
        
        # Relay active simulation change
        self.project.active_index_changed.connect(
            lambda: self.update_pipeline.emit(self))
        self.project.active_index_changed.connect(
            lambda: self.reset_widgets.emit())
        self.project.active_index_changed.connect(
            lambda: self.update_run_action.emit())
            
        self._current_scope = "global"
        
        # Update the scope widget
        self.update_scope.emit(self._current_scope)
        
        return
        
    @QtCore.pyqtSlot(str)
    def open_project(self, file_path):
        
        load_path = str(file_path)
        dto_dir_path = None
        prj_file_path = None
        sco_file_path = None
        stg_file_path = None
        
        # Check the extension
        if os.path.splitext(load_path)[1] == ".dto":
            
            dto_dir_path = tempfile.mkdtemp()
                                    
            tar = tarfile.open(load_path)
            tar.extractall(dto_dir_path)
            
            prj_file_path = os.path.join(dto_dir_path, "project.prj")
            sco_file_path = os.path.join(dto_dir_path, "scope.json")
            stg_file_path = os.path.join(dto_dir_path, "strategy.pkl")
            
            if not os.path.isfile(stg_file_path): stg_file_path = None
            
        elif os.path.splitext(load_path)[1] == ".prj":
            
            prj_file_path = load_path
            
        else:
            
            errStr = ("The file path must be a file with either .dto or "
                      ".prj extension")
            raise ValueError(errStr)
            
        # Load up the project
        load_project = self.core.load_project(prj_file_path)

        self.project = load_project
        
        # Load up the scope if one was found
        if sco_file_path is not None:        
        
            with open(sco_file_path, 'rb') as json_file:
                self._current_scope = json.load(json_file)
                
        else:
            
            self._current_scope = "global"
            
        # Load up the strategy if one was found
        if stg_file_path is not None:
            
            strategy_manager = GUIStrategyManager() 
            self.strategy = strategy_manager.load_strategy(stg_file_path)
            
        else:
            
            self.strategy = None
            
        # Record the path after a successful load
        self.project_path = load_path
        
        self.project_title_change.emit(load_project.title)
        
        # Relay active simulation change
        self.project.active_index_changed.connect(
            lambda: self.update_pipeline.emit(self))
        self.project.active_index_changed.connect(
            lambda: self.reset_widgets.emit())
        self.project.active_index_changed.connect(
            lambda: self.update_run_action.emit())
            
        # Update the scope widget
        self.update_scope.emit(self._current_scope)
            
        # Delete temp directory
        if dto_dir_path is not None: shutil.rmtree(dto_dir_path)
        
        return
        
    @QtCore.pyqtSlot(str)
    def save_project(self, file_path=None):
        
        if file_path is None:
            save_path = self.project_path
        else:
            save_path = str(file_path)
            
        if save_path is None:
            
            errStr = "A file path must be provided in order to save a project"
            raise ValueError(errStr)
            
        # Check the extension
        if os.path.splitext(save_path)[1] != ".dto":
        
            errStr = "The file path must be a file with .dto extension"
            raise ValueError(errStr)
            
        dto_dir_path = tempfile.mkdtemp()
            
        # Dump the project
        prj_file_path = os.path.join(dto_dir_path, "project.prj")
        self.core.dump_project(self.project, prj_file_path)
        
        # Dump the output scope
        sco_file_path = os.path.join(dto_dir_path, "scope.json")
        
        with open(sco_file_path, 'wb') as json_file:
            json.dump(self._current_scope, json_file)        
        
        # Set the standard archive contents
        arch_files = [prj_file_path, sco_file_path]
        arch_paths = ["project.prj", "scope.json"]
        
        # Dump the strategy (if there is one)
        if self.strategy is not None:
        
            strategy_manager = GUIStrategyManager() 
            stg_file_path = os.path.join(dto_dir_path, "strategy.pkl")
            strategy_manager.dump_strategy(self.strategy, stg_file_path)
            
            arch_files.append(stg_file_path)
            arch_paths.append("strategy.pkl")
            
        # Now tar the files together
        dto_file_name = os.path.split(save_path)[1]
        tar_file_name = "{}.tar".format(dto_file_name)
    
        archive = tarfile.open(tar_file_name, "w")
        
        for arch_file, arch_path in zip(arch_files, arch_paths):
            archive.add(arch_file, arcname=arch_path)
        
        archive.close()
        
        shutil.move(tar_file_name, save_path)
        shutil.rmtree(dto_dir_path)
        
        self.project_path = save_path
        self.project_saved.emit()
        
        return
        
    @QtCore.pyqtSlot()
    def close_project(self):
        
        self.project = None
        self.project_path = None
        self.strategy = None
        
        self.project_closed.emit()
        self.project_title_change.emit("")
        self.database_updated.emit("None")
        self.update_pipeline.disconnect()
        
        return
        
    @QtCore.pyqtSlot(str, str)
    def set_simulation_title(self, old_title, new_title):
        
        msg = "Changing title of simulation {} to {}".format(old_title,
                                                             new_title)
        module_logger.debug(msg)
        
        self.project.set_simulation_title(new_title, title=old_title)
                
        return
        
    @QtCore.pyqtSlot(str)
    def set_active_simulation(self, title):
        
        msg = "Setting simulation '{}' as active".format(title)
        module_logger.debug(msg)

        self.project.set_active_index(title=title)
        
        return
        
    @QtCore.pyqtSlot(object)
    def select_database(self, identifier):
        
        if identifier is None:
            self.data_menu.select_database(self.project, None)
            self.database_updated.emit("None")
        else:
            self.data_menu.select_database(self.project, str(identifier))
            self.database_updated.emit(identifier)
        
        return
        
    @QtCore.pyqtSlot()
    def initiate_pipeline(self):
        
        self.project_menu.initiate_pipeline(self.core, self.project)
        
        sites_available = self.core.has_data(self.project,
                                             "hidden.available_sites")
        systems_available = self.core.has_data(self.project,
                                               "hidden.available_systems")
                                               
        if sites_available or systems_available:
            self.project_menu.initiate_options(self.core, self.project)
        
        if sites_available: self.filter_active.emit()
            
        self.pipeline_active.emit()
        
        return
        
    @QtCore.pyqtSlot()
    def initiate_bathymetry(self):
        
        self.project_menu.initiate_bathymetry(self.core, self.project)
        self.bathymetry_active.emit()
        
        return

    @QtCore.pyqtSlot(list)
    def activate_module_list(self, module_list):
        
        all_mods = self.module_menu.get_available(self.core, self.project)
        ordered_mods = [x for x in all_mods if x in module_list]

        active_mods = self.module_menu.get_active(self.core, self.project)

        for module_name in ordered_mods:

            if module_name not in active_mods:
    
                self.module_menu.activate(self.core,
                                          self.project,
                                          module_name)
                                                        
        self.modules_activated.emit()

        return

    @QtCore.pyqtSlot(list)
    def activate_theme_list(self, theme_list):

        all_themes = self.theme_menu.get_available(self.core, self.project)
        ordered_themes = [x for x in all_themes if x in theme_list]

        active_themes = self.theme_menu.get_active(self.core, self.project)

        for theme_name in ordered_themes:

            if theme_name not in active_themes:
    
                self.theme_menu.activate(self.core, 
                                         self.project,
                                         theme_name)
                                                        
        self.themes_activated.emit()

        return
        
    @QtCore.pyqtSlot(object)
    def select_strategy(self, strategy):
        
        if strategy is None:
            logMsg = "Null strategy detected"
        else:
            logMsg = "Strategy {} detected".format(strategy.get_name())
            
        module_logger.debug(logMsg)
            
        self.strategy = strategy
        
        if strategy is None: return
        
        self.strategy.strategy_run = True
        
        force_unavailable = self.strategy.get_variables()
        simulation = self.project.get_simulation()
        
        simulation.set_unavailable_variables(force_unavailable)
        
        return
    
    @QtCore.pyqtSlot(object)
    def initiate_dataflow(self, pipeline):
        
        self._active_thread = ThreadDataFlow(pipeline,
                                             self)
        
        self._active_thread.taskFinished.connect(
                                        lambda: self.dataflow_active.emit())
                                        
        self._active_thread.start()
        
        return
        
    @QtCore.pyqtSlot(object, str, str)
    def read_file(self, variable, interface_name, file_path):
                
        variable.read_file(self.core,
                           self.project,
                           str(file_path),
                           str(interface_name))
        
        return
        
        
    @QtCore.pyqtSlot(object, str, str)
    def write_file(self, variable, interface_name, file_path):
        
        variable.write_file(self.core,
                            self.project,
                            str(file_path),
                            str(interface_name))
        
        return

    @QtCore.pyqtSlot()
    def execute_current(self):
        
        self._active_thread = ThreadCurrent(self.core,
                                            self.project)
        
        self._active_thread.taskFinished.connect(
                                        lambda: self.module_executed.emit())
                                        
        self._active_thread.start()
        
        return
        
    @QtCore.pyqtSlot()
    def execute_themes(self):
        
        self._active_thread = ThreadThemes(self.core,
                                           self.project)
        
        self._active_thread.taskFinished.connect(
                                        lambda: self.themes_executed.emit())
                                        
        self._active_thread.start()
        
        return
        
    @QtCore.pyqtSlot()
    def execute_strategy(self):
        
        if self.strategy is None: return
        
        self._active_thread = ThreadStrategy(self.strategy,
                                             self.core,
                                             self.project)
        
        self._active_thread.taskFinished.connect(
                                        lambda: self.strategy_executed.emit())
                                        
        self._active_thread.start()
        
        return
        
    @QtCore.pyqtSlot()
    def set_strategy_run(self):
        
        self.strategy.strategy_run = self.strategy.allow_rerun
        
        return
        
    @QtCore.pyqtSlot(str)
    def set_output_scope(self, scope):
        
        # Switch the output scope on all simulations
        for sim_idx in xrange(len(self.project)):
        
            set_output_scope(self.core,
                             self.project,
                             scope,
                             sim_index=sim_idx)
                             
        self._current_scope = scope
        
        return   
        
    @QtCore.pyqtSlot()
    def _clear_active_thread(self):
        
        if self._active_thread is None: return
        
        self._active_thread.wait()
        self._active_thread = None
        
        return
        
    
class DTOceanWindow(MainWindow):

    def __init__(self, shell, debug=False):
        
        super(DTOceanWindow, self).__init__()
        
        # Context Area
        self._data_context = None
        self._plot_context = None
        self._comp_context = None
        
        # Details widgets
        self._data_details = None
        self._plot_details = None
        
        # Dialogs
        self._project_properties = None
        self._data_check = None
        self._module_shuttle = None
        self._assessment_shuttle = None
        self._db_selector = None
        self._strategy_manager = None
        self._help = None
        self._progress = None
        self._about = None
        
        # Docks
        self._pipeline_dock = None
        self._simulation_dock = None
        self._system_dock = None
        
        # Widget re-use
        self._last_tree_item = None
        self._last_data_item = None
        self._last_data_item_status = None
        self._last_plot_id = None
                
        # Last used stack index
        self._last_stack_index = None
        
        # Threads
        self._thread_read_raw = None
        self._thread_tool = None
        
        # Tools
        self._tool_manager = None
        
        # Redirect excepthook
        if not debug: sys.excepthook = self._display_error
        
        # Init Shell
        self._shell = self._init_shell(shell)
        
        # Init context areas
        self._init_context()
        
        # Init dialogs
        self._init_shuttles()
        self._init_dialogs()
        
        # Initiate docks
        self._init_pipeline_dock()
        self._init_simulation_dock()
        self._init_system_dock(debug)
        
        # Initiate menus
        self._init_file_menu()
        self._init_sim_menu()
        self._init_data_menu()
        self._init_view_menu(debug)
        self._init_tools_menu()
        self._init_help_menu()

        return
        
    def _init_shell(self, shell):
        
        shell.project_activated.connect(self._active_project_ui_switch)
        shell.project_closed.connect(self._closed_project_ui_switch)
        shell.update_widgets.connect(
                    lambda: self._set_context_widget(self._last_tree_item))
        shell.reset_widgets.connect(
                    lambda: self._set_context_widget(self._last_tree_item, -1))
        shell.pipeline_active.connect(self._active_pipeline_ui_switch)
        shell.bathymetry_active.connect(self._active_bathymetry_ui_switch)
        shell.filter_active.connect(self._active_filter_ui_switch)
        shell.dataflow_active.connect(self._active_dataflow_ui_switch)
        shell.update_run_action.connect(self._run_action_ui_switch)
        shell.module_executed.connect(self._run_action_ui_switch)
        shell.themes_executed.connect(self._run_action_ui_switch)
        shell.strategy_executed.connect(self._run_action_ui_switch)
        shell.strategy_executed.connect(
            lambda: self.stackedWidget.setCurrentIndex(self._last_stack_index))
        shell.update_scope.connect(self._current_scope_ui_switch)

        # Collect all saved and unsaved signals        
        shell.project_title_change.connect(self._set_project_unsaved)
        shell.project_activated.connect(self._set_project_unsaved)
        shell.reset_widgets.connect(self._set_project_unsaved)
        shell.update_run_action.connect(self._set_project_unsaved)
        shell.project_saved.connect(self._set_project_saved)

        return shell
        
    def _init_context(self):
        
        # Blank context
        blank_widget = QtGui.QWidget(self)
        self.stackedWidget.addWidget(blank_widget)
        
        # Data context
        self._data_context = ContextArea(self)
        self.stackedWidget.addWidget(self._data_context)
        
         # Plot context
        self._plot_context = ContextArea(self)
        self.stackedWidget.addWidget(self._plot_context)
        
         # Comparison context
        self._comp_context = ContextArea(self)
        self._comp_context._top_left.setMaximumWidth(16777215)
        self._comp_context._top_right.setMinimumWidth(320)
        self.stackedWidget.addWidget(self._comp_context)
        
        # Collect the input widget parent
        self._shell.core.set_input_parent(self._data_context._bottom)
                
        return
        
    def _init_shuttles(self):
        
        # Set up the module shuttle widget
        self._module_shuttle = Shuttle(self, "Add Modules...")
        self._module_shuttle.list_updated.connect(
                                            self._shell.activate_module_list)
                                            
        # Close the button as undo is not yet available
        self._module_shuttle.buttonBox.button(
                    QtGui.QDialogButtonBox.Ok).clicked.connect(
                        lambda: self.actionAdd_Modules.setDisabled(True))
                             
        # Set up the assessment shuttle widget
        self._assessment_shuttle = Shuttle(self, "Add Assessment...")
        self._assessment_shuttle.list_updated.connect(
                                            self._shell.activate_theme_list)
                                            
        # Close the button as undo is not yet available
        self._assessment_shuttle.buttonBox.button(
                    QtGui.QDialogButtonBox.Ok).clicked.connect(
                         lambda: self.actionAdd_Assessment.setDisabled(True))
                             
        return
        
    def _init_dialogs(self):

        # Set up project properties dialog
        self._project_properties = ProjProperties(self)
        self._project_properties.buttonBox.button(
                         QtGui.QDialogButtonBox.Ok).clicked.connect(
                                                 self._set_project_title)
        
        # Set up the database selection dialog
        self._db_selector = DBSelector(self, self._shell.data_menu)
        self._db_selector.database_selected.connect(
                                    self._shell.select_database)
        self._shell.database_updated.connect(
                                    self._db_selector._update_current)
        
        # Set up the strategy manager
        self._strategy_manager = GUIStrategyManager(self)
        self._strategy_manager.setModal(True)
        self._strategy_manager.strategy_selected.connect(
                                    self._shell.select_strategy)

        # Set up the data check diaglog
        self._data_check = DataCheck(self)
        self._data_check.setModal(True)
        
        # Set up progress bar
        self._progress = ProgressBar(self)
        self._progress.setModal(True)
        self._progress.force_quit.connect(self.close)
        
        # Set up the help dialog
        self._help = HelpWidget(self)
        
        # Set up the about dialog (actionAbout)
        self._about = About(self)
        self._about.setModal(True)
        
        return
        
    def _init_pipeline_dock(self):
        
        # Give the bottom left corner to left dock
        self.setCorner(QtCore.Qt.Corner(0x00002), QtCore.Qt.DockWidgetArea(1))
        
        # Pipeline dock
        self._pipeline_dock = PipeLine(self)
        self._pipeline_dock._close_filter._close_dock.connect(
                        lambda: self.actionShow_Pipeline.setEnabled(True))
        self.addDockWidget(QtCore.Qt.DockWidgetArea(1), self._pipeline_dock)
        
        # Set widgets on tree click
        self._pipeline_dock.treeWidget.itemClicked.connect(
                                                self._set_details_widget)
        self._pipeline_dock.treeWidget.itemClicked.connect(
                                                self._set_context_widget)
                                                    
        # Change the output scope on button click
        self._pipeline_dock.globalRadioButton.clicked.connect(
                            lambda: self._shell.set_output_scope("global"))
        self._pipeline_dock.localRadioButton.clicked.connect(
                            lambda: self._shell.set_output_scope("local"))
        self._pipeline_dock.scopeFrame.setDisabled(True)
                                                    
        # Refresh on module and theme activation or execution
        self._shell.modules_activated.connect(
                            lambda: self._pipeline_dock._refresh(self._shell))
        self._shell.themes_activated.connect(
                            lambda: self._pipeline_dock._refresh(self._shell))
        self._shell.module_executed.connect(
                            lambda: self._pipeline_dock._refresh(self._shell))
        self._shell.themes_executed.connect(
                            lambda: self._pipeline_dock._refresh(self._shell))
        self._shell.strategy_executed.connect(
                            lambda: self._pipeline_dock._refresh(self._shell))
                            
        # Add context menu(s)
        self._pipeline_dock.treeWidget.customContextMenuRequested.connect(
                    lambda x: self._pipeline_dock._make_menus(self._shell, x))
                    
        # Handle errors
        self._pipeline_dock.error_detected.connect(self._display_error)

        return

    def _init_simulation_dock(self):

        # Simulation dock
        self._simulation_dock = SimulationDock(self)
        self._simulation_dock._close_filter._close_dock.connect(
                        lambda: self.actionShow_Simulations.setEnabled(True))  
        self.addDockWidget(QtCore.Qt.DockWidgetArea(1), self._simulation_dock)
        self._simulation_dock.name_changed.connect(
                                          self._shell.set_simulation_title)
        self._simulation_dock.active_changed.connect(
                                          self._shell.set_active_simulation)
        
        # Add context menu(s)
        self._simulation_dock.listWidget.customContextMenuRequested.connect(
                lambda x: self._simulation_dock._make_menus(self._shell, x))
        
        # Set disabled until dataflow activated.
        self._simulation_dock.setDisabled(True)
        
        # Tab docks
        self.setTabPosition(QtCore.Qt.DockWidgetArea(1),
                            QtGui.QTabWidget.TabPosition(0))
        self.tabifyDockWidget(self._simulation_dock, self._pipeline_dock)
        
        # Collect unsaved signals
        self._simulation_dock.name_changed.connect(self._set_project_unsaved)
        self._simulation_dock.active_changed.connect(self._set_project_unsaved)
        
        return

    def _init_system_dock(self, disable_log=False):
        
        if disable_log: return
              
        # System dock
        self._system_dock = LogDock(self)
        self._system_dock._close_filter._close_dock.connect(
                        lambda: self.actionSystem_Log.setEnabled(True))
        self.addDockWidget(QtCore.Qt.DockWidgetArea(8), self._system_dock)

        return
        
    def _init_file_menu(self):

        self.actionNew.triggered.connect(self._new_project)
        self.actionOpen.triggered.connect(self._open_project)
        self.actionSave.triggered.connect(self._save_project)
        self.actionSave_As.triggered.connect(self._saveas_project)
        self.actionProperties.triggered.connect(
                                            self._set_project_properties)
        self.actionClose.triggered.connect(self._close_project)
        self.actionExit.triggered.connect(self.close)
        
        return
        
    def _init_sim_menu(self):

        # Set up the simulation menu
        self.actionAdd_Modules.triggered.connect(self._set_module_shuttle)
        self.actionAdd_Assessment.triggered.connect(
                                                self._set_assessment_shuttle)
        self.actionAdd_Strategy.triggered.connect(self._set_strategy)
        self.actionRun_Current.triggered.connect(self._execute_current)
        self.actionRun_Themes.triggered.connect(self._execute_themes)
        self.actionRun_Strategy.triggered.connect(self._execute_strategy)
                                                
        return
                                                
    def _init_data_menu(self):
    
        # Database selection dialog
        self.actionSelect_Database.triggered.connect(
                                                self._set_database_properties)
    
        # Set up data preparation stages
        self.actionInitiate_Pipeline.triggered.connect(self._initiate_pipeline)
        self.actionInitiate_Bathymetry.triggered.connect(
                                                     self._initiate_bathymetry)
        self.actionInitiate_Dataflow.triggered.connect(self._initiate_dataflow)
        
        # Data export / import functions
        self.actionExport.triggered.connect(self._export_data)
        self.actionImport.triggered.connect(self._import_data)
    
        return
        
    def _init_view_menu(self, disable_log=False):
        
        # Dock show buttons
        self.actionShow_Pipeline.triggered.connect(self._pipeline_dock.show)
        self.actionShow_Pipeline.triggered.connect(
                        lambda: self.actionShow_Pipeline.setDisabled(True))
                        
        self.actionShow_Simulations.triggered.connect(
                                                    self._simulation_dock.show)
        self.actionShow_Simulations.triggered.connect(
                        lambda: self.actionShow_Simulations.setDisabled(True))
                        
        if not disable_log:
                        
            self.actionSystem_Log.triggered.connect(self._system_dock.show)
            self.actionSystem_Log.triggered.connect(
                            lambda: self.actionSystem_Log.setDisabled(True))
                            
        # Context Actions
        self.actionData.triggered.connect(
                            lambda: self.stackedWidget.setCurrentIndex(1))
        self.actionPlots.triggered.connect(
                            lambda: self.stackedWidget.setCurrentIndex(2))
        self.actionComparison.triggered.connect(
                            lambda: self.stackedWidget.setCurrentIndex(3))
        self.actionData.triggered.connect(
                        lambda: self._set_context_widget(self._last_tree_item))
        self.actionPlots.triggered.connect(
                        lambda: self._set_context_widget(self._last_tree_item))
                            
        self.contextGroup = QtGui.QActionGroup(self)
        self.contextGroup.addAction(self.actionData)
        self.contextGroup.addAction(self.actionPlots)
        self.contextGroup.addAction(self.actionComparison)

        return
        
    def _init_tools_menu(self):
        
        """Dynamically generate tool menu entries and signal/slots"""
        
        self._tool_manager = GUIToolManager()
        
        all_tools = self._tool_manager.get_available()
        
        for tool_name in all_tools:
                        
            new_action = self._add_dynamic_action(tool_name, "menuTools")
            new_action.triggered.connect(
                    lambda x, name=tool_name: self._open_tool(name))
                        
            self._dynamic_actions[tool_name] = new_action
                
        return
        
    def _init_help_menu(self):
    
        self.actionHelp_Index.triggered.connect(self._help.show)
        self.actionAbout.triggered.connect(self._about.show)
    
        return
        
    @QtCore.pyqtSlot(str)        
    def _set_window_title(self, title):
        
        if not title:
            title_str = "DTOcean"
        else:
            title_str = "DTOcean: {}".format(title)
            
        self.setWindowTitle(title_str)

        return

    @QtCore.pyqtSlot()
    def _set_project_properties(self):

        self._project_properties.lineEdit.setText(self._shell.project.title)
        self._project_properties.show()

        return

    @QtCore.pyqtSlot()
    def _set_project_title(self):

        new_title = self._project_properties.lineEdit.text()
        self._shell.set_project_title(new_title)

        return
        
    @QtCore.pyqtSlot()
    def _set_project_saved(self):
        
        if self._shell.project is None: return
        
        proj_title = self._shell.project.title
        self._set_window_title(proj_title)

        return
        
    @QtCore.pyqtSlot()
    def _set_project_unsaved(self):
        
        if self._shell.project is None: return
        
        proj_title = "{}*".format(self._shell.project.title)
        self._set_window_title(proj_title)

        return
        
    @QtCore.pyqtSlot()
    def _set_database_properties(self):

        self._db_selector.show()

        return
        
    @QtCore.pyqtSlot()
    def _active_project_ui_switch(self):
        
        # Disable Actions
        self.actionNew.setDisabled(True)
        self.actionSave.setDisabled(True)
        self.actionSave_As.setDisabled(True)
        self.actionComparison.setDisabled(True)
        
        # Enable Actions
        self.actionProperties.setEnabled(True)
        self.actionClose.setEnabled(True)
        self.actionData.setEnabled(True)
        self.actionPlots.setEnabled(True)
        self.actionInitiate_Pipeline.setEnabled(True)
        self.actionSelect_Database.setEnabled(True)
        self.actionExport.setEnabled(True)
        self.actionImport.setEnabled(True)
        
        # Activate the pipeline
        start_branch_map = [{"hub": SectionItem,
                             "name": "Configuration"},
                            {"hub": HubItem,
                             "name": "Scenario",
                             "args": ["project",
                                      InputBranchItem,
                                      True,
                                      ["System Type Selection",
                                       "Database Filtering Interface",
                                       "Project Boundaries Interface"]]}
                            ]
                            
        self._pipeline_dock._set_branch_map(start_branch_map)
        self._pipeline_dock._refresh(self._shell)
        self._pipeline_dock._set_title("Define scenario selections...")
        self._pipeline_dock.scopeFrame.setEnabled(True)
        
        # Link the project to the simulation dock and initialise the list
        self._simulation_dock.setDisabled(True)
        self._shell.project.sims_updated.connect(
                                     self._simulation_dock._update_simulations)
        self._simulation_dock._update_simulations(self._shell.project)
        
        # Set up details widget on the data context area
        self._data_details = DetailsWidget(self)
        self._data_context._top_left_box.addWidget(self._data_details)

        # Set up file manager widget on the data context area
        self._data_file_manager = FileManagerWidget(self)
        self._data_context._top_right_box.addWidget(self._data_file_manager)
        self._data_file_manager.setDisabled(True)
        
        # Set up details widget on the plot context area
        self._plot_details = DetailsWidget(self)
        self._plot_context._top_left_box.addWidget(self._plot_details)
        
        # Set up plot manager widget on the plot context area
        self._plot_manager = PlotManagerWidget(self)
        self._plot_context._top_right_box.addWidget(self._plot_manager)
        self._plot_manager.setDisabled(True)
        
        # Set up the level comparison in the comparison context area
        self._level_comparison = LevelComparison(self)
        self._comp_context._top_left_box.addWidget(self._level_comparison)
        
        # Set up the simulation comparison in the comparison context area
        self._sim_comparison = SimulationComparison(self)
        self._comp_context._top_right_box.addWidget(self._sim_comparison)
        
        # Set up level comparison signals
        self._level_comparison.varBox.currentIndexChanged.connect(
                                            self._sim_comparison_ui_switch)
        self._level_comparison.plot_levels.connect(self._set_level_plot)
        self._level_comparison.tab_levels.connect(self._set_level_table)
        self._level_comparison.save_plot.connect(self._save_comparison_plot)
        self._level_comparison.save_data.connect(self._save_comparison_data)
        
        # Set up simulation comparison signals
        self._sim_comparison.plot_levels.connect(self._set_sim_plot)
        self._sim_comparison.tab_levels.connect(self._set_sim_table)
        self._sim_comparison.save_plot.connect(self._save_comparison_plot)
        self._sim_comparison.save_data.connect(self._save_comparison_data)

        # Update the central widget
        self.stackedWidget.setCurrentIndex(1)
        self.actionData.setChecked(True)
        
        # Connect actions
        self._shell.update_pipeline.connect(self._tool_menu_ui_switch)
        self._shell.update_pipeline.connect(self._set_project_unsaved)
        
        # Trigger the pipeline
        self._pipeline_dock._set_top_item()
        
        # Trigget tools menu
        self._tool_menu_ui_switch(self._shell)

        return
        
    @QtCore.pyqtSlot()
    def _closed_project_ui_switch(self):

        # Disable Actions
        self.actionSave.setDisabled(True)
        self.actionSave_As.setDisabled(True)
        self.actionProperties.setDisabled(True)
        self.actionClose.setDisabled(True)
        self.actionData.setDisabled(True)
        self.actionPlots.setDisabled(True)
        self.actionComparison.setDisabled(True)
        self.actionInitiate_Pipeline.setDisabled(True)
        self.actionSelect_Database.setDisabled(True)
        self.actionInitiate_Dataflow.setDisabled(True)
        self.actionInitiate_Bathymetry.setDisabled(True)
        self.actionAdd_Modules.setDisabled(True)
        self.actionAdd_Assessment.setDisabled(True)
        self.actionAdd_Strategy.setDisabled(True)
        self.actionRun_Current.setDisabled(True)
        self.actionRun_Themes.setDisabled(True)
        self.actionRun_Strategy.setDisabled(True)
        self.actionExport.setDisabled(True)
        self.actionImport.setDisabled(True)

        # Enable actions
        self.actionNew.setEnabled(True)

        # Clear the pipeline
        self._pipeline_dock._clear()
        self._pipeline_dock._set_title("Waiting...")
        self._pipeline_dock.scopeFrame.setDisabled(True)
        
        # Disable the simulation widget
        self._simulation_dock.setDisabled(True)
        self._simulation_dock._update_simulations(None)
        
        # Remove details widget from data context
        self._data_context._top_left_box.removeWidget(self._data_details)
        self._data_details.setParent(None)
        self._data_details.deleteLater()
        self._data_details = None
        
        # Remove file manager widget from data context
        self._data_context._top_right_box.removeWidget(self._data_file_manager)
        self._data_file_manager.setParent(None)
        self._data_file_manager.deleteLater()
        self._data_file_manager = None

        # Remove details widget from plot context
        self._plot_context._top_left_box.removeWidget(self._plot_details)
        self._plot_details.setParent(None)
        self._plot_details.deleteLater()
        self._plot_details = None
                
        # Remove plot manager widget from plot context
        self._plot_context._top_right_box.removeWidget(self._plot_manager)
        self._plot_manager.setParent(None)
        self._plot_manager.deleteLater()
        self._plot_manager = None
        
        # Remove level comparison widget from comparison context
        self._comp_context._top_left_box.removeWidget(self._level_comparison)
        self._level_comparison.setParent(None)
        self._level_comparison.deleteLater()
        self._level_comparison = None
                
        # Remove simulation comparison widget from comparison context
        self._plot_context._top_right_box.removeWidget(self._sim_comparison)
        self._sim_comparison.setParent(None)
        self._sim_comparison.deleteLater()
        self._sim_comparison = None
        
        # Remove main widget from comparison context
        if self._comp_context._bottom_contents is not None:
            
            self._comp_context._bottom_box.removeWidget(
                                        self._comp_context._bottom_contents)
            self._comp_context._bottom_contents.setParent(None)
            
            if isinstance(self._comp_context._bottom_contents, MPLWidget):
                self._comp_context._bottom_contents.figure.clear()

#            self._plot_context._bottom_contents.deleteLater()
            sip.delete(self._comp_context._bottom_contents)
            self._comp_context._bottom_contents = None

        # Update the central widget
        self.stackedWidget.setCurrentIndex(0)
        self._last_tree_item = None
        self._last_data_item = None
        self._last_data_item_status = None
        self._last_plot_id = None
        
        # Reset the window title
        self._set_window_title("")
        
        # Trigger the tool menu switcher
        self._tool_menu_ui_switch(self._shell)

        return
        
    @QtCore.pyqtSlot()
    def _active_filter_ui_switch(self):
        
        # Enable Actions
        self.actionInitiate_Bathymetry.setEnabled(True)
        
        return
        
    @QtCore.pyqtSlot()
    def _active_pipeline_ui_switch(self):
        
        # Close dialog
        self._db_selector.close()
        
        # Disable Actions
        self.actionInitiate_Pipeline.setDisabled(True)
        self.actionSelect_Database.setDisabled(True)
        
        # Enabale Actions
        self.actionAdd_Modules.setEnabled(True)
        self.actionAdd_Assessment.setEnabled(True)
        self.actionAdd_Strategy.setEnabled(True)
        self.actionInitiate_Dataflow.setEnabled(True)
        
        # Update the pipeline
        fresh_branch_map = [{"hub": SectionItem,
                             "name": "Configuration"},
                            {"hub": HubItem,
                             "name": "Scenario",
                             "args": ["project",
                                      InputBranchItem,
                                      True,
                                      ["System Type Selection",
                                       "Database Filtering Interface",
                                       "Project Boundaries Interface"]]},
                            {"hub": HubItem,
                             "name": "Modules",
                             "args": ["modules",
                                      InputBranchItem,
                                      False]},
                            {"hub": HubItem,
                             "name": "Assessment",
                             "args": ["themes",
                                      InputBranchItem,
                                      False]}
                            ]
                            
        self._pipeline_dock._set_branch_map(fresh_branch_map)
        self._pipeline_dock._refresh(self._shell)
        
        return
        
    @QtCore.pyqtSlot()
    def _active_bathymetry_ui_switch(self):
        
        # Disable Actions
        self.actionInitiate_Bathymetry.setDisabled(True)
        
        # Update the pipeline
        self._pipeline_dock._refresh(self._shell)
        
        return
        
    @QtCore.pyqtSlot()
    def _active_dataflow_ui_switch(self):
                       
        self._pipeline_dock._refresh(self._shell)
        
        # Close dialogs
        self._module_shuttle.close()
        self._assessment_shuttle.close()
        
        # Enable the simulation widget
        self._simulation_dock.setEnabled(True)
        
        # Setup and enable comparison context
        self._level_comparison._set_interfaces(self._shell)
        self._sim_comparison._set_interfaces(self._shell, include_str=True)
        
        if self._shell.strategy is not None:
            
            self._level_comparison.strategyBox.setChecked(False)
            self._level_comparison.strategyBox.setEnabled(True)
            
            self._sim_comparison.strategyBox.setChecked(False)
            self._sim_comparison.strategyBox.setEnabled(True)
        
        self.actionComparison.setEnabled(True)

        # Enable Actions
        self.actionSave.setEnabled(True)
        self.actionSave_As.setEnabled(True)
        self._run_action_ui_switch()
        
        # Disable Actions
        self.actionAdd_Modules.setDisabled(True)
        self.actionAdd_Assessment.setDisabled(True)
        self.actionAdd_Strategy.setDisabled(True)
        self.actionInitiate_Dataflow.setDisabled(True)
        self.actionInitiate_Bathymetry.setDisabled(True)
        
        return
        
    @QtCore.pyqtSlot(str)
    def _current_scope_ui_switch(self, scope):     
        
        sane_scope = str(scope)
        
        if sane_scope == "global":
            
            self._pipeline_dock.globalRadioButton.setChecked(True)
            
        elif sane_scope == "local":
            
            self._pipeline_dock.localRadioButton.setChecked(True)
            
        else:
            
            errStr = ("Valid scopes are 'local' or 'global'. Passed scope "
                      "was {}").format(sane_scope)
            raise ValueError(errStr)
        
    @QtCore.pyqtSlot()
    def _run_action_ui_switch(self):
        
        modules_scheduled = self._shell.get_scheduled_modules()
        modules_completed = self._shell.get_completed_modules()
        themes_scheduled = self._shell.get_scheduled_themes()
        
        # Set the run action buttons
        if (self._shell.strategy is None or
                (self._shell.strategy is not None and 
                 not self._shell.strategy.strategy_run)):
            
            self.actionRun_Strategy.setDisabled(True)
                    
            if modules_scheduled:
                
                self.actionRun_Current.setEnabled(True)
                
                if themes_scheduled:
                    self.actionRun_Themes.setEnabled(True)
                else:
                    self.actionRun_Themes.setDisabled(True)
                
            else:
                
                self.actionRun_Current.setDisabled(True)
                self.actionRun_Themes.setDisabled(True)
      
        else:
            
            self.actionRun_Current.setDisabled(True)
            self.actionRun_Themes.setDisabled(True)
            
            if modules_scheduled:
                self.actionRun_Strategy.setEnabled(True)
            else:
                self.actionRun_Strategy.setDisabled(True)
                
        # Set the pipeline title
        if not modules_completed and modules_scheduled:
            pipeline_msg = "Define simulation inputs..."
        elif modules_completed and modules_scheduled:
            pipeline_msg = "Simulation in progress..."
        elif modules_completed and not modules_scheduled:
            pipeline_msg = "Simulation complete..."
        elif (not modules_completed and
              not modules_scheduled and
              themes_scheduled):
            pipeline_msg = "Assessment only mode..."
        elif (not modules_completed and
              not modules_scheduled and
              not themes_scheduled):
            pipeline_msg = "No modules or assessments selected..."
        else:
            errStr = "Whoa, take 'er easy there, Pilgrim"
            raise SystemError(errStr)
        
        self._pipeline_dock._set_title(pipeline_msg)

        return
        
    @QtCore.pyqtSlot(int)
    def _sim_comparison_ui_switch(self, box_number):
        
        if box_number == -1:
            self._sim_comparison.setDisabled(True)
        else:
            self._sim_comparison.setEnabled(True)
            
        return
    
    @QtCore.pyqtSlot(object)
    def _tool_menu_ui_switch(self, shell):
        
        for tool_name, action in self._dynamic_actions.iteritems():
            
            tool = self._tool_manager.get_tool(tool_name)
            
            if self._tool_manager.can_execute_tool(shell.core,
                                                   shell.project,
                                                   tool):
                
                action.setEnabled(True)
                
            else:
                
                action.setDisabled(True)

        return
    @QtCore.pyqtSlot()
    def _set_module_shuttle(self):
                
        self._module_shuttle._add_items_from_lists(
                                        self._shell.get_available_modules(),
                                        self._shell.get_active_modules())

        self._module_shuttle.show()

        return

    @QtCore.pyqtSlot()
    def _set_assessment_shuttle(self):

        self._assessment_shuttle._add_items_from_lists(
                                        self._shell.get_available_themes(),
                                        self._shell.get_active_themes())

        self._assessment_shuttle.show()

        return
        
    @QtCore.pyqtSlot()
    def _set_strategy(self):

        self._strategy_manager.show(self._shell)

        return
        
    @QtCore.pyqtSlot(object, int)
    def _set_details_widget(self, var_item, column):
        
        if isinstance(var_item, (InputVarItem, OutputVarItem)):

            # Collect the meta data from the variable
            meta = var_item._variable.get_metadata(self._shell.core)
            title = meta.title
            description = meta.description
        
        else:
        
            title = None
            description = None
    
        self._data_details._set_details(title, description)
        self._plot_details._set_details(title, description)
        
        return
        
    @QtCore.pyqtSlot(object, int)
    def _set_context_widget(self, var_item, column=None):
        
        # Use fake -1 column value to reset all the stored items 
        if column == -1:
            self._last_tree_item = None
            self._last_data_item = None
            self._last_data_item_status = None
            self._last_plot_id = None
        
        current_context_action = self.contextGroup.checkedAction()
          
        if current_context_action is None:
            
            pass
          
        elif str(current_context_action.text()) == "Data":
            
            self._set_data_widget(var_item)
            self._set_file_manager_widget(var_item)
            
        elif str(current_context_action.text()) == "Plots":
            
            self._set_plot_widget(var_item)
            self._set_plot_manager_widget(var_item)
            
        self._last_tree_item = var_item
        
        return
        
    def _set_file_manager_widget(self, var_item):
        
        # Avoid being in a race where the data file manager is None
        if self._data_file_manager is None: return
        
        current_context_action = self.contextGroup.checkedAction()
          
        if (current_context_action is None or
            str(current_context_action.text()) == "Plots"):
            
            return
            
        variable = None
        
        load_ext_dict = {}
        
        if isinstance(var_item, InputVarItem):
            
            variable = var_item._variable
            
            interface_dict = var_item._variable.get_file_input_interfaces(
                                                          self._shell.core,
                                                          include_auto=True)
            
            if interface_dict:
                                
                for interface_name, ext_list in interface_dict.iteritems():
                                        
                    repeated_exts = set(ext_list).intersection(
                                                        load_ext_dict.keys())
                    
                    if repeated_exts:
                        
                        extsStr =  ", ".join(repeated_exts)
                        errStr = ("Repeated interface extensions '{}'"
                                  "found").format(extsStr)
                        
                        raise RuntimeError(errStr)
                        
                    interface_exts = {ext: interface_name for ext in ext_list}

                    load_ext_dict.update(interface_exts)
                                        
        save_ext_dict = {}

        if isinstance(var_item, (InputVarItem, OutputVarItem)):
            
            variable = var_item._variable
            
            interface_dict = var_item._variable.get_file_output_interfaces(
                                                          self._shell.core,
                                                          self._shell.project,
                                                          include_auto=True)

            
            if interface_dict:
                                
                for interface_name, ext_list in interface_dict.iteritems():
                                        
                    repeated_exts = set(ext_list).intersection(
                                                        save_ext_dict.keys())
                    
                    if repeated_exts:
                        
                        extsStr =  ", ".join(repeated_exts)
                        errStr = ("Repeated interface extensions '{}'"
                                  "found").format(extsStr)
                        
                        raise RuntimeError(errStr)
                        
                    interface_exts = {ext: interface_name for ext in ext_list}

                    save_ext_dict.update(interface_exts)
                    
        if not load_ext_dict: load_ext_dict = None
        if not save_ext_dict: save_ext_dict = None
        
        if self._data_file_manager._load_connected:
            self._data_file_manager.load_file.disconnect()
            self._data_file_manager._load_connected = False
            
        if self._data_file_manager._save_connected:
            self._data_file_manager.save_file.disconnect()
            self._data_file_manager._save_connected = False
        
        self._data_file_manager._set_files(variable,
                                           load_ext_dict,
                                           save_ext_dict)
        
        if self._data_file_manager._file_mode is None: return
        
        if isinstance(var_item, InputVarItem):
            self._data_file_manager.load_file.connect(self._shell.read_file)
            self._data_file_manager._load_connected = True
            
        if isinstance(var_item, (InputVarItem, OutputVarItem)):
            self._data_file_manager.save_file.connect(self._shell.write_file)
            self._data_file_manager._save_connected = True
                    
        return
        
    def _set_plot_manager_widget(self, var_item):
        
        # Avoid race condition
        if self._plot_manager is None: return
        
        current_context_action = self.contextGroup.checkedAction()
          
        if (current_context_action is None or
            str(current_context_action.text()) == "Data"):
            
            return

        plot_list = []
        plot_auto = False
        
        if isinstance(var_item, (InputVarItem, OutputVarItem)):
                        
            plot_list = var_item._variable.get_available_plots(
                                                          self._shell.core,
                                                          self._shell.project)
            
            all_interfaces = var_item._variable._get_receivers(
                                                          self._shell.core,
                                                          self._shell.project,
                                                          "PlotInterface",
                                                          "AutoPlot")

            if set(all_interfaces) - set(plot_list):
                plot_auto = True
                            
        if self._plot_manager._plot_connected:
            self._plot_manager.plot.disconnect()
            self._plot_manager._plot_connected = False
        
        if not plot_list: plot_list = None
            
        self._plot_manager._set_plots(var_item,
                                      plot_list,
                                      plot_auto)
        
        if not plot_list is None and not plot_auto: return
            
        if isinstance(var_item, (InputVarItem, OutputVarItem)):
            self._plot_manager.plot.connect(self._set_plot_widget)
            self._plot_manager._plot_connected = True
                            
        return
        
    def _set_data_widget(self, var_item):
       
        if var_item is None: return

        if (self._last_data_item is not None and 
            var_item._id == self._last_data_item._id and
            type(var_item) == type(self._last_data_item)):

            if (var_item._status != self._last_data_item_status and
                                        "unavailable" in var_item._status):
                
                self._data_context._bottom_contents.setDisabled(True)
                self._last_data_item_status = var_item._status
                          
            return
                                 
        if self._data_context._bottom_contents is not None:
            
            # Wait for any file reading.
            if self._thread_read_raw is not None:
                self._thread_read_raw.wait()
                self._thread_read_raw = None
                                    
            self._data_context._bottom_box.removeWidget(
                                        self._data_context._bottom_contents)
            self._data_context._bottom_contents.setParent(None)
#            self._data_context._bottom_contents.deleteLater()
            sip.delete(self._data_context._bottom_contents)
            self._data_context._bottom_contents = None
        
        self._last_data_item = var_item
        self._last_data_item_status = var_item._status
                    
        widget = var_item._get_data_widget(self._shell)

        if widget is None: return
    
        # Add the widget to the context
        self._data_context._bottom_box.addWidget(widget)
        self._data_context._bottom_contents = widget
        
        # Connect the widgets read and nullify events
        widget._get_read_event().connect(
            lambda: self._read_raw(var_item._variable, widget._get_result()))
            
        widget._get_nullify_event().connect(
            lambda: self._read_raw(var_item._variable, None))
            
        if "unavailable" in var_item._status: widget.setDisabled(True)
                
        return
        
    @QtCore.pyqtSlot(object, str)
    def _set_plot_widget(self, var_item,  plot_name="auto"):
        
        if var_item is None: return

        if var_item._id == self._last_plot_id and plot_name is "auto": return
        
        if plot_name == "auto": plot_name = None
        
        if self._plot_context._bottom_contents is not None:
                        
            self._plot_context._bottom_box.removeWidget(
                                        self._plot_context._bottom_contents)
            self._plot_context._bottom_contents.setParent(None)
            
            fignum = self._plot_context._bottom_contents.figure.number
#            self._plot_context._bottom_contents.deleteLater()
            sip.delete(self._plot_context._bottom_contents)
            plt.close(fignum)
            
            self._plot_context._bottom_contents = None
        
        self._last_plot_id = var_item._id
                                        
        widget = var_item._get_plot_widget(self._shell, plot_name)
        
        if widget is None: return
    
        # Add the widget to the context
        self._plot_context._bottom_box.addWidget(widget)
        self._plot_context._bottom_contents = widget
        
        # Draw the widget
        widget.draw_idle()
        
        assert len(plt.get_fignums()) <= 2
            
        if "unavailable" in var_item._status: widget.setDisabled(True)
        
        return
    
    @QtCore.pyqtSlot(str, bool)
    def _set_level_plot(self, var_id, ignore_strategy):
    
        # Sanitise var_id
        var_id = str(var_id)
        
        # Collect the current scope
        if self._pipeline_dock.globalRadioButton.isChecked():
            scope = "global"
        elif self._pipeline_dock.localRadioButton.isChecked():
            scope = "local"
        else:
            errStr = "Feck!"
            raise SystemError(errStr)
            
        if self._comp_context._bottom_contents is not None:
            
            self._comp_context._bottom_box.removeWidget(
                                        self._comp_context._bottom_contents)
            self._comp_context._bottom_contents.setParent(None)
            
            if isinstance(self._comp_context._bottom_contents, MPLWidget):
                fignum = self._comp_context._bottom_contents.figure.number
                sip.delete(self._comp_context._bottom_contents)
                plt.close(fignum)
            else:
                sip.delete(self._comp_context._bottom_contents)
                
#            self._plot_context._bottom_contents.deleteLater()
            
            self._comp_context._bottom_contents = None
            
            # Switch off save button
            self._level_comparison.buttonBox.button(
                                QtGui.QDialogButtonBox.Save).setDisabled(True)
        
        # Collect the sim titles from the sim dock             
        sim_titles = self._simulation_dock._get_list_values()
                    
        # Get the plot figure
        widget = self._strategy_manager.get_level_values_plot(
                                                            self._shell,
                                                            var_id,
                                                            scope,
                                                            ignore_strategy,
                                                            sim_titles)
        
        # Add the widget to the context
        self._comp_context._bottom_box.addWidget(widget)
        self._comp_context._bottom_contents = widget
        
        # Draw the widget
        widget.draw_idle()
        
        assert len(plt.get_fignums()) <= 2
        
        # Switch on save button
        self._sim_comparison.buttonBox.button(
                            QtGui.QDialogButtonBox.Save).setDisabled(True)
        self._level_comparison.buttonBox.button(
                            QtGui.QDialogButtonBox.Save).setEnabled(True)
        
        return
        
    @QtCore.pyqtSlot(str, bool)
    def _set_level_table(self, var_id, ignore_strategy):
    
        # Sanitise var_id
        var_id = str(var_id)
        
        # Collect the current scope
        if self._pipeline_dock.globalRadioButton.isChecked():
            scope = "global"
        elif self._pipeline_dock.localRadioButton.isChecked():
            scope = "local"
        else:
            errStr = "Feck!"
            raise SystemError(errStr)
            
        if self._comp_context._bottom_contents is not None:
            
            self._comp_context._bottom_box.removeWidget(
                                        self._comp_context._bottom_contents)
            self._comp_context._bottom_contents.setParent(None)
            
            if isinstance(self._comp_context._bottom_contents, MPLWidget):
                fignum = self._comp_context._bottom_contents.figure.number
                sip.delete(self._comp_context._bottom_contents)
                plt.close(fignum)
            else:
                sip.delete(self._comp_context._bottom_contents)
                
            self._comp_context._bottom_contents = None
            
            # Switch off save button
            self._level_comparison.buttonBox.button(
                                QtGui.QDialogButtonBox.Save).setDisabled(True)
            
        # Get the table widget
        widget = self._strategy_manager.get_level_values_df(self._shell,
                                                            var_id,
                                                            scope,
                                                            ignore_strategy)
        
        # Add the widget to the context
        self._comp_context._bottom_box.addWidget(widget)
        self._comp_context._bottom_contents = widget
        
        # Switch on save button
        self._sim_comparison.buttonBox.button(
                            QtGui.QDialogButtonBox.Save).setDisabled(True)
        self._level_comparison.buttonBox.button(
                            QtGui.QDialogButtonBox.Save).setEnabled(True)
        
        return
        
    @QtCore.pyqtSlot(str, str, bool)
    def _set_sim_plot(self, var_one_id, module, ignore_strategy):
    
        # Sanitise strings
        var_one_id = str(var_one_id)
        module = str(module)
                
        # Get the first variable id from the level comparison widget
        var_two_name = str(self._level_comparison.varBox.currentText())
        var_two_id = self._level_comparison._get_var_id(var_two_name)
        
        # Collect the current scope
        if self._pipeline_dock.globalRadioButton.isChecked():
            scope = "global"
        elif self._pipeline_dock.localRadioButton.isChecked():
            scope = "local"
        else:
            errStr = "Feck!"
            raise SystemError(errStr)
                        
        if self._comp_context._bottom_contents is not None:
            
            self._comp_context._bottom_box.removeWidget(
                                        self._comp_context._bottom_contents)
            self._comp_context._bottom_contents.setParent(None)
            
            if isinstance(self._comp_context._bottom_contents, MPLWidget):
                fignum = self._comp_context._bottom_contents.figure.number
                sip.delete(self._comp_context._bottom_contents)
                plt.close(fignum)
            else:
                sip.delete(self._comp_context._bottom_contents)
                
#            self._comp_context._bottom_contents.deleteLater()
            self._comp_context._bottom_contents = None
            
            # Switch off save button
            self._sim_comparison.buttonBox.button(
                                QtGui.QDialogButtonBox.Save).setDisabled(True)
            
        # Get the plot figure
        widget = self._strategy_manager.get_comparison_values_plot(
                                                            self._shell, 
                                                            var_one_id,
                                                            var_two_id,
                                                            module,
                                                            scope,
                                                            ignore_strategy)

        # Add the widget to the context
        self._comp_context._bottom_box.addWidget(widget)
        self._comp_context._bottom_contents = widget
        
        # Draw the widget
        widget.draw_idle()
        
        assert len(plt.get_fignums()) <= 2
        
        # Switch save buttons
        self._level_comparison.buttonBox.button(
                            QtGui.QDialogButtonBox.Save).setDisabled(True)
        self._sim_comparison.buttonBox.button(
                            QtGui.QDialogButtonBox.Save).setEnabled(True)
        
        return
        
    @QtCore.pyqtSlot(str, str, bool)
    def _set_sim_table(self, var_one_id, module, ignore_strategy):
    
        # Sanitise strings
        var_one_id = str(var_one_id)
        module = str(module)
                
        # Get the first variable id from the level comparison widget
        var_two_name = str(self._level_comparison.varBox.currentText())
        var_two_id = self._level_comparison._get_var_id(var_two_name)
        
        # Collect the current scope
        if self._pipeline_dock.globalRadioButton.isChecked():
            scope = "global"
        elif self._pipeline_dock.localRadioButton.isChecked():
            scope = "local"
        else:
            errStr = "Feck!"
            raise SystemError(errStr)
                        
        if self._comp_context._bottom_contents is not None:
            
            self._comp_context._bottom_box.removeWidget(
                                        self._comp_context._bottom_contents)
            self._comp_context._bottom_contents.setParent(None)
            
            if isinstance(self._comp_context._bottom_contents, MPLWidget):
                fignum = self._comp_context._bottom_contents.figure.number
                sip.delete(self._comp_context._bottom_contents)
                plt.close(fignum)
            else:
                sip.delete(self._comp_context._bottom_contents)
                
            self._comp_context._bottom_contents = None
            
            # Switch off save button
            self._sim_comparison.buttonBox.button(
                                QtGui.QDialogButtonBox.Save).setDisabled(True)
            
        # Get the table widget
        widget = self._strategy_manager.get_comparison_values_df(
                                                            self._shell, 
                                                            var_one_id,
                                                            var_two_id,
                                                            module,
                                                            scope,
                                                            ignore_strategy)
        
        # Add the widget to the context
        self._comp_context._bottom_box.addWidget(widget)
        self._comp_context._bottom_contents = widget
        
        # Switch on save button
        self._sim_comparison.buttonBox.button(
                            QtGui.QDialogButtonBox.Save).setEnabled(True)
        self._level_comparison.buttonBox.button(
                            QtGui.QDialogButtonBox.Save).setDisabled(True)
        
        return
        
    @QtCore.pyqtSlot()    
    def _save_comparison_plot(self):
        
        extlist = ["{} (*.{})".format(v, k) for k, v in
                                           get_current_filetypes().iteritems()]
        extStr = ";;".join(extlist)

        fdialog_msg = "Save plot"
            
        save_path = QtGui.QFileDialog.getSaveFileName(None,
                                                      fdialog_msg,
                                                      '.',
                                                      extStr)
        
        save_current_figure(str(save_path))
        
        return
        
    @QtCore.pyqtSlot()    
    def _save_comparison_data(self):
        
        extlist = ["comma-separated values (*.csv)"]
        extStr = ";;".join(extlist)

        fdialog_msg = "Save data"
            
        save_path = QtGui.QFileDialog.getSaveFileName(None,
                                                      fdialog_msg,
                                                      '.',
                                                      extStr)
        
        df = self._strategy_manager._last_df
        df.to_csv(str(save_path), index=False)
        
        return
        
    @QtCore.pyqtSlot(object)
    def _read_raw(self, variable, value):
        
        self._thread_read_raw = ThreadReadRaw(self._shell,
                                              variable,
                                              value)
        self._thread_read_raw.error_detected.connect(self._display_error)        
        self._thread_read_raw.start()
                            
        return
        
    @QtCore.pyqtSlot()
    def _new_project(self):      
        
        reply = self._project_close_warning()
        
        if reply == QtGui.QMessageBox.Yes: self._shell.new_project()
        
        return

    @QtCore.pyqtSlot()
    def _open_project(self):
        
        msg = "Open Project"
        valid_exts = "DTOcean Files (*.dto *.prj)"         
        
        file_path = QtGui.QFileDialog.getOpenFileName(None,
                                                      msg,
                                                      '.',
                                                      valid_exts)
        
        if not file_path: return
            
        reply = self._project_close_warning()
        
        if reply != QtGui.QMessageBox.Yes: return
                
        if self._shell.project is not None:
            self._shell.close_project()
                
        self._shell.open_project(file_path)
        
        self._active_project_ui_switch()
        self._active_pipeline_ui_switch()
        
        # Recreate the existing branch map
        new_branch_map = [{"hub": SectionItem,
                           "name": "Configuration"},
                          {"hub": HubItem,
                           "name": "Scenario",
                           "args": ["project",
                                    InputBranchItem,
                                    True,
                                    ["System Type Selection",
                                     "Database Filtering Interface",
                                     "Project Boundaries Interface"]]},
                          {"hub": HubItem,
                           "name": "Modules",
                           "args": ["modules",
                                    InputBranchItem,
                                    True]},
                          {"hub": HubItem,
                           "name": "Assessment",
                           "args": ["themes",
                                    InputBranchItem,
                                    True]},
                          {"hub": SectionItem,
                           "name": "Results"},
                          {"hub": HubItem,
                           "name": "Assessment",
                           "args": ["themes",
                                    OutputBranchItem,
                                    True]},
                          {"hub": HubItem,
                           "name": "Modules",
                           "args": ["modules",
                                    OutputBranchItem,
                                    True]}
                           ]
                    
        self._pipeline_dock._set_branch_map(new_branch_map)
        self._active_dataflow_ui_switch()
        
        self._shell.core.status_updated.emit()
        self._set_project_saved()
        
        return
        
    @QtCore.pyqtSlot()
    def _save_project(self):
        
        if self._shell.project_path is None:
            self._saveas_project()
        else:
            self._shell.save_project()
        
        return
        
    @QtCore.pyqtSlot()
    def _saveas_project(self):
        
        msg = "Save Project"
        valid_exts = "DTOcean Files (*.dto)"
        
        file_path = QtGui.QFileDialog.getSaveFileName(None,
                                                      msg,
                                                      '.',
                                                      valid_exts)
        
        if file_path:
            self._shell.save_project(file_path)
        
        return
        
    @QtCore.pyqtSlot()
    def _close_project(self):
        
        reply = self._project_close_warning()
        
        if reply == QtGui.QMessageBox.Yes: self._shell.close_project()
        
        return
    
    @QtCore.pyqtSlot()
    def _export_data(self):
        
        msg = "Export Data"
        valid_exts = "Datastate Files (*.dts)"
        
        file_path = QtGui.QFileDialog.getSaveFileName(None,
                                                      msg,
                                                      '.',
                                                      valid_exts)
                
        if file_path:
            self._shell.core.dump_datastate(self._shell.project,
                                            str(file_path))
        
        return
    
    @QtCore.pyqtSlot()
    def _import_data(self):
        
        msg = "Import Data"
        valid_exts = "Datastate Files (*.dts)"
        
        file_path = QtGui.QFileDialog.getOpenFileName(None,
                                                      msg,
                                                      '.',
                                                      valid_exts)
        
        if file_path:
            self._shell.core.load_datastate(self._shell.project,
                                            str(file_path),
                                            exclude="hidden")
        
        return
        
    @QtCore.pyqtSlot()
    def _initiate_pipeline(self):
        
        # Find the "System Type Selection" branch
        branch_item = self._pipeline_dock._find_item("System Type Selection",
                                                     InputBranchItem)
                                                     
        # Check for required values
        required_address = branch_item._get_required_address(self._shell)
        
        # Remap OK button
        self._data_check.buttonBox.button(
                         QtGui.QDialogButtonBox.Ok).clicked.disconnect()
        self._data_check.buttonBox.button(
                         QtGui.QDialogButtonBox.Ok).clicked.connect(
                                             self._shell.initiate_pipeline)
        self._data_check.buttonBox.button(
                         QtGui.QDialogButtonBox.Ok).clicked.connect(
                                                     self._data_check.accept)
        
        self._data_check.show(required_address)
                
        return
        
    @QtCore.pyqtSlot()
    def _initiate_bathymetry(self):
        
        if self._shell.project_menu.is_executable(self._shell.core,
                                                  self._shell.project,
                                                  "Site Boundary Selection"):
            required_address = None
            
        else:
        
            raw_required = {"Section": ["Scenario"],
                            "Branch": ["Database Filtering Interface"],
                            "Item": ["Selected Site"]}
                            
            required_address = pd.DataFrame(raw_required)
        
        # Remap OK button
        self._data_check.buttonBox.button(
                         QtGui.QDialogButtonBox.Ok).clicked.disconnect()
        self._data_check.buttonBox.button(
                         QtGui.QDialogButtonBox.Ok).clicked.connect(
                                             self._shell.initiate_bathymetry)
        self._data_check.buttonBox.button(
                         QtGui.QDialogButtonBox.Ok).clicked.connect(
                                                     self._data_check.accept)
        
        self._data_check.show(required_address)
                
        return
        
    @QtCore.pyqtSlot()
    def _initiate_dataflow(self):
        
        required_address = None
                
        # Check if filters can be initiated
        if self._shell.project.get_database_credentials() is not None: 
        
            # Find the "Database Filtering Interface" branch
            branch_item = self._pipeline_dock._find_item(
                                                "Database Filtering Interface",
                                                InputBranchItem)
                                                         
            # Check for required values
            required_address = branch_item._get_required_address(self._shell)
        
        # Remap OK button
        self._data_check.buttonBox.button(
                         QtGui.QDialogButtonBox.Ok).clicked.disconnect()
        self._data_check.buttonBox.button(
                         QtGui.QDialogButtonBox.Ok).clicked.connect(
                                             self._progress_dataflow)
        self._data_check.buttonBox.button(
                         QtGui.QDialogButtonBox.Ok).clicked.connect(
                                             self._data_check.accept)
        
        self._data_check.show(required_address)
                                
        return
        
    @QtCore.pyqtSlot()
    def _execute_current(self):
        
        # Get the current module name
        current_mod = self._shell.get_current_module()
        
        # Find the module branch
        branch_item = self._pipeline_dock._find_item(current_mod,
                                                     InputBranchItem)
                                                         
        # Check for required values
        required_address = branch_item._get_required_address(self._shell)
        
        # Find any required values for any themes:
        all_themes = self._shell.get_active_themes()
        
        for theme_name in all_themes:
            
            branch_item = self._pipeline_dock._find_item(theme_name,
                                                         InputBranchItem)
            
            # Check for required values
            theme_address = branch_item._get_required_address(self._shell)
            
            # Loop if None
            if theme_address is None: continue
        
            # Otherwise merge
            if required_address is None:
                required_address = theme_address
            else:
                required_address = pd.concat([required_address, theme_address],
                                             ignore_index=True)
                        
        # Remap OK button
        self._data_check.buttonBox.button(
                         QtGui.QDialogButtonBox.Ok).clicked.disconnect()
        self._data_check.buttonBox.button(
                         QtGui.QDialogButtonBox.Ok).clicked.connect(
                                             self._progress_current)
        self._data_check.buttonBox.button(
                         QtGui.QDialogButtonBox.Ok).clicked.connect(
                                             self._data_check.accept)
        
        self._data_check.show(required_address)
                                
        return
        
    @QtCore.pyqtSlot()
    def _execute_themes(self):
                                                         
        # Check for required values
        required_address = None
        
        # Find any required values for any themes:
        all_themes = self._shell.get_active_themes()
        
        for theme_name in all_themes:
            
            branch_item = self._pipeline_dock._find_item(theme_name,
                                                         InputBranchItem)
            
            # Check for required values
            theme_address = branch_item._get_required_address(self._shell)
            
            # Loop if None
            if theme_address is None: continue
        
            # Otherwise merge
            if required_address is None:
                required_address = theme_address
            else:
                required_address = pd.concat([required_address, theme_address],
                                             ignore_index=True)
                        
        # Remap OK button
        self._data_check.buttonBox.button(
                         QtGui.QDialogButtonBox.Ok).clicked.disconnect()
        self._data_check.buttonBox.button(
                         QtGui.QDialogButtonBox.Ok).clicked.connect(
                                             self._progress_themes)
        self._data_check.buttonBox.button(
                         QtGui.QDialogButtonBox.Ok).clicked.connect(
                                             self._data_check.accept)
        
        self._data_check.show(required_address)
                                
        return
        
    @QtCore.pyqtSlot()
    def _execute_strategy(self):
        
        # Get the current module name
        scheduled_mods = self._shell.get_scheduled_modules()
        
        required_address = None
        
        for scheduled_mod in scheduled_mods:
        
            # Find the module branch
            branch_item = self._pipeline_dock._find_item(scheduled_mod,
                                                         InputBranchItem)
                                                             
            # Check for required values
            mod_address = branch_item._get_required_address(self._shell)
            
            # Loop if None
            if mod_address is None: continue
        
            # Otherwise merge
            if required_address is None:
                required_address = mod_address
            else:
                required_address = pd.concat([required_address, mod_address],
                                             ignore_index=True)
        
        # Find any required values for any themes:
        all_themes = self._shell.get_active_themes()
        
        for theme_name in all_themes:
            
            branch_item = self._pipeline_dock._find_item(theme_name,
                                                         InputBranchItem)
            
            # Check for required values
            theme_address = branch_item._get_required_address(self._shell)
            
            # Loop if None
            if theme_address is None: continue
        
            # Otherwise merge
            if required_address is None:
                required_address = theme_address
            else:
                required_address = pd.concat([required_address, theme_address],
                                             ignore_index=True)
                        
        # Remap OK button
        self._data_check.buttonBox.button(
                         QtGui.QDialogButtonBox.Ok).clicked.disconnect()
        self._data_check.buttonBox.button(
                         QtGui.QDialogButtonBox.Ok).clicked.connect(
                                             self._progress_strategy)
        self._data_check.buttonBox.button(
                         QtGui.QDialogButtonBox.Ok).clicked.connect(
                                             self._data_check.accept)
        
        self._data_check.show(required_address)
                                
        return
        
    @QtCore.pyqtSlot()        
    def _progress_dataflow(self):
        
        # Recreate the existing branch map
        new_branch_map = [{"hub": SectionItem,
                           "name": "Configuration"},
                          {"hub": HubItem,
                           "name": "Scenario",
                           "args": ["project",
                                    InputBranchItem,
                                    True,
                                    ["System Type Selection",
                                     "Database Filtering Interface",
                                     "Project Boundaries Interface"]]},
                          {"hub": HubItem,
                           "name": "Modules",
                           "args": ["modules",
                                    InputBranchItem,
                                    True]},
                          {"hub": HubItem,
                           "name": "Assessment",
                           "args": ["themes",
                                    InputBranchItem,
                                    True]},
                          {"hub": SectionItem,
                           "name": "Results"},
                          {"hub": HubItem,
                           "name": "Assessment",
                           "args": ["themes",
                                    OutputBranchItem,
                                    True]},
                          {"hub": HubItem,
                           "name": "Modules",
                           "args": ["modules",
                                    OutputBranchItem,
                                    True]}
                           ]
                            
        self._pipeline_dock._set_branch_map(new_branch_map)
        
        self._progress.allow_close = False
        self._progress.set_pulsing()
        self._shell.initiate_dataflow(self._pipeline_dock)
        self._shell._active_thread.error_detected.connect(self._display_error)
        self._shell._active_thread.finished.connect(self._close_progress)
        self._progress.show()
        
        return

    @QtCore.pyqtSlot()        
    def _progress_current(self):
        
        self._progress.allow_close = False
        self._progress.set_pulsing()
        self._shell.execute_current()
        self._shell._active_thread.error_detected.connect(self._display_error)
        self._shell._active_thread.finished.connect(self._close_progress)
        self._progress.show()
        
        return
        
    @QtCore.pyqtSlot()        
    def _progress_themes(self):
        
        self._progress.allow_close = False
        self._progress.set_pulsing()
        self._shell.execute_themes()
        self._shell._active_thread.error_detected.connect(self._display_error)
        self._shell._active_thread.finished.connect(self._close_progress)
        self._progress.show()
        
        return
        
    @QtCore.pyqtSlot()        
    def _progress_strategy(self):
        
        
        self._last_stack_index = self.stackedWidget.currentIndex()
        self.stackedWidget.setCurrentIndex(0)
        
        self._progress.allow_close = False
        self._progress.set_pulsing()
        self._shell.execute_strategy()
        self._shell._active_thread.error_detected.connect(self._display_error)
        self._shell._active_thread.finished.connect(self._close_progress)
        self._progress.show()
        
        return
        
    @QtCore.pyqtSlot(str)        
    def _open_tool(self, tool_name):
        
        if self._thread_tool is not None: return
                
        # Pick up the tool
        tool = self._tool_manager.get_tool(tool_name)
        
        self._thread_tool = ThreadTool(self._shell.core,
                                       self._shell.project,
                                       tool)
        self._thread_tool.start()
        self._thread_tool.error_detected.connect(self._display_error)
        self._thread_tool.finished.connect(lambda: self._close_tool(tool))
                
        return
        
    @QtCore.pyqtSlot(object)        
    def _close_tool(self, tool):
        
        if tool.has_widget():
            widget = tool.get_widget()
            if widget is not None: widget.show()
        
        self._thread_tool = None
        
        return

    @QtCore.pyqtSlot()
    def _close_progress(self):
        
        self._progress.allow_close = True
        self._progress.close()
        
        return

    @QtCore.pyqtSlot(object, object, object)  
    def _display_error(self, etype, evalue, etraceback):
        
        type_str = str(etype)
        type_strs = type_str.split(".")
        sane_type_str = type_strs[-1].replace("'>", "")
        
        if sane_type_str[0].lower() in "aeiou":
            article = "An"
        else:
            article = "A"
        
        errMsg = "{} {} occurred: {:s}".format(article, sane_type_str, evalue)

        module_logger.critical(errMsg)
        module_logger.critical(''.join(traceback.format_tb(etraceback)))        
        QtGui.QMessageBox.critical(self, "ERROR", errMsg)
            
        return
        
    def _project_close_warning(self):
        
        if self._shell.project is None: return QtGui.QMessageBox.Yes
        
        qstr = "Unsaved progress will be lost. Continue?"
        
        reply = QtGui.QMessageBox.warning(self,
                                          'Project close',
                                          qstr,
                                          QtGui.QMessageBox.Yes,
                                          QtGui.QMessageBox.No)
        
        return reply

    def closeEvent(self, event):
        
        reply = QtGui.QMessageBox.question(self,
                                           'Exit',
                                           "Quit DTOcean?",
                                           QtGui.QMessageBox.Yes,
                                           QtGui.QMessageBox.No)

        if reply == QtGui.QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()
            
        return
