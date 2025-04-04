#!/usr/bin/env python3
import sys
import os
import logging
import subprocess
import json
import argparse
import getpass
import shlex
import base64
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QListWidget,
    QPushButton, QVBoxLayout, QHBoxLayout, QMessageBox, QInputDialog,
    QCheckBox, QProgressBar, QTextEdit
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

# Easter egg check - must be first executable code after imports
if len(sys.argv) > 1 and sys.argv[1] == "moo":
    CHICKEN_CODE = b"""
ZGVmIGNoaWNrZW5fbW9vKCk6CiAgICBwcmludCgiIiIKICAgICAgIF8gIAogICAgICB7bz4KICAgICAg
IFxfXwogICAgICBfLy8pCiAgICAgLyA+IG9cXAogICAgIFxfXF9cL18vCiAgICAgICAvXy9fLwoKICAg
IFRoZSBjaGlja2VuIHNheXM6CiAgICAiV2h5IGRpZCB0aGUgY2hpY2tlbiBjcm9zcyB0aGUgcm9hZD8K
ICAgIFRvIHNob3cgdGhlIGNvdyBpdCBjb3VsZCBtb28gdG9vISBCd2FrIGJ3YWshIgogICAgIiIiKQoK
Y2hpY2tlbl9tb28oKQ==
"""
    try:
        decoded = base64.b64decode(CHICKEN_CODE).decode('utf-8')
        exec(decoded)
    except Exception as e:
        print("Egg cracked!", e)
    sys.exit(0)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

PKG_FILE = "pkg.cpm"
APP_FILE = "app.txt"
THEME_FILE = ".theme.cfg"

def convert_app_txt_to_pkg_cpm():
    try:
        if os.path.exists(APP_FILE):
            logging.info(f"Converting {APP_FILE} to {PKG_FILE}.")
            apps = []
            with open(APP_FILE, "r") as file:
                app_name, version, commands, description = None, None, [], ""
                for line in file:
                    line = line.strip()
                    if line.startswith("Commands:"):
                        commands.extend(line.split(": ")[1].split(", "))
                    elif line.startswith("Description:"):
                        description = line.split(": ", 1)[1]
                    elif line.startswith("App"):
                        if app_name and version and commands:
                            apps.append({
                                "name": app_name,
                                "version": version,
                                "commands": commands,
                                "description": description
                            })
                        parts = line.split()
                        app_name, version = parts[1], parts[2]
                        commands, description = [], ""
                if app_name and version and commands:
                    apps.append({
                        "name": app_name,
                        "version": version,
                        "commands": commands,
                        "description": description
                    })
            with open(PKG_FILE, "w") as pkg_file:
                json.dump(apps, pkg_file, indent=4)
            os.remove(APP_FILE)
            logging.info(f"Converted {APP_FILE} to {PKG_FILE} successfully.")
    except Exception as e:
        logging.error(f"Error converting {APP_FILE} to {PKG_FILE}: {e}")

def load_apps():
    try:
        convert_app_txt_to_pkg_cpm()

        if not os.path.exists(PKG_FILE):
            logging.error("No package file found!")
            if QApplication.instance() is not None:
                QMessageBox.critical(None, "Error", "No package file found!")
            return []

        logging.info(f"Loading app list from: {PKG_FILE}")
        with open(PKG_FILE, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        logging.error("Package file not found!")
        if QApplication.instance() is not None:
            QMessageBox.critical(None, "Error", "Package file not found!")
        return []
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing {PKG_FILE}: {e}")
        if QApplication.instance() is not None:
            QMessageBox.critical(None, "Error", f"Error parsing {PKG_FILE}: {e}")
        return []

class CommandRunner(QThread):
    progress = pyqtSignal(int)
    error_signal = pyqtSignal(list)
    success_signal = pyqtSignal()

    def __init__(self, commands, password=None):
        super().__init__()
        self.commands = commands
        self.password = password

    def run(self):
        errors = []
        for index, command in enumerate(self.commands):
            try:
                if command.startswith("sudo "):
                    full_command = f"echo {self.password} | sudo -S {command[5:]}"
                    logging.debug(f"Running with sudo: {full_command}")
                else:
                    full_command = command
                    logging.debug(f"Running: {full_command}")

                subprocess.run(full_command, shell=True, check=True, stderr=subprocess.PIPE)

            except subprocess.CalledProcessError as e:
                error_message = f"Command '{command}' failed: {e.stderr.decode().strip()}"
                logging.error(error_message)
                errors.append(error_message)

            self.progress.emit(int((index + 1) / len(self.commands) * 100))

        if errors:
            self.error_signal.emit(errors)
        else:
            self.success_signal.emit()

class AppInstaller(QWidget):
    def __init__(self):
        super().__init__()
        self.apps = load_apps()
        self.dark_mode = self.load_theme_setting()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        search_layout.addWidget(search_label)
        self.search_entry = QLineEdit()
        self.search_entry.textChanged.connect(self.filter_apps)
        search_layout.addWidget(self.search_entry)
        layout.addLayout(search_layout)

        self.app_list = QListWidget()
        self.app_list.itemClicked.connect(self.show_details)
        layout.addWidget(self.app_list)

        self.details_box = QTextEdit()
        self.details_box.setReadOnly(True)
        layout.addWidget(self.details_box)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        button_layout = QHBoxLayout()
        self.install_button = QPushButton("Install")
        self.install_button.clicked.connect(self.on_install)
        button_layout.addWidget(self.install_button)

        self.theme_toggle = QCheckBox("Dark Mode")
        self.theme_toggle.setChecked(self.dark_mode)
        self.theme_toggle.stateChanged.connect(self.toggle_theme)
        button_layout.addWidget(self.theme_toggle)

        layout.addLayout(button_layout)
        self.setLayout(layout)

        self.setWindowTitle("Chilly Package Manager")
        self.setMinimumWidth(400)
        self.setMaximumWidth(600)

        self.apply_theme()
        self.show()
        self.filter_apps()

    def filter_apps(self):
        search_term = self.search_entry.text().lower()
        self.app_list.clear()
        for app in self.apps:
            if search_term in app["name"].lower() or search_term in app["description"].lower():
                self.app_list.addItem(f"{app['name']} {app['version']}")

    def show_details(self, item):
        app_name = item.text()
        for app in self.apps:
            full_name = f"{app['name']} {app['version']}"
            if full_name == app_name:
                self.details_box.setText(f"Name: {app['name']}\nVersion: {app['version']}\n\nDescription:\n{app['description']}")

    def on_install(self):
        selected_item = self.app_list.currentItem()
        if selected_item:
            app_name = selected_item.text()
            for app in self.apps:
                full_name = f"{app['name']} {app['version']}"
                if full_name == app_name:
                    requires_sudo = any(cmd.startswith("sudo ") for cmd in app['commands'])
                    password = None

                    if requires_sudo:
                        password, ok = QInputDialog.getText(
                            self, "Sudo Password", "Enter your sudo password:", QLineEdit.Password
                        )
                        if not ok or not password:
                            QMessageBox.warning(self, "Cancelled", "Installation cancelled.")
                            return

                    self.install_button.setEnabled(False)
                    self.progress_bar.show()

                    self.runner = CommandRunner(app['commands'], password)
                    self.runner.progress.connect(self.progress_bar.setValue)
                    self.runner.error_signal.connect(self.on_errors)
                    self.runner.success_signal.connect(self.on_success)
                    self.runner.start()
                    return
        else:
            QMessageBox.critical(self, "Error", "Please select an app to install.")

    def on_errors(self, errors):
        self.install_button.setEnabled(True)
        self.progress_bar.hide()
        QMessageBox.warning(
            self, "Installation Completed with Errors",
            "Installation completed, but some commands failed:\n" + "\n".join(errors)
        )

    def on_success(self):
        self.install_button.setEnabled(True)
        self.progress_bar.hide()
        QMessageBox.information(self, "Installation", "Installation completed successfully!")
        os.execv(sys.argv[0], sys.argv)

    def toggle_theme(self):
        self.dark_mode = self.theme_toggle.isChecked()
        self.save_theme_setting()
        self.apply_theme()

    def apply_theme(self):
        if self.dark_mode:
            self.setStyleSheet("""
                QWidget { background-color: #2e2e2e; color: white; }
                QPushButton { background-color: #1e1e1e; color: white; }
                QLineEdit, QListWidget, QProgressBar, QTextEdit { background-color: #444; color: white; }
            """)
        else:
            self.setStyleSheet("""
                QWidget { background-color: white; color: black; }
                QPushButton { background-color: #2ecc71; color: white; }
                QLineEdit, QListWidget, QProgressBar, QTextEdit { background-color: #fff; color: black; }
            """)

    def save_theme_setting(self):
        with open(THEME_FILE, "w") as file:
            file.write("dark" if self.dark_mode else "light")

    def load_theme_setting(self):
        if os.path.exists(THEME_FILE):
            with open(THEME_FILE, "r") as file:
                return file.read().strip() == "dark"
        return False

def cli_main():
    parser = argparse.ArgumentParser(description='Chilly Package Manager CLI')
    parser.add_argument('--list', action='store_true', help='List all available packages')
    parser.add_argument('--search', type=str, help='Search for packages by name or description')
    parser.add_argument('--install', type=str, help='Install a package by name and version')
    args = parser.parse_args()

    apps = load_apps()

    if args.list:
        print("Available packages:")
        for app in apps:
            print(f"{app['name']} {app['version']} - {app['description']}")
    elif args.search:
        term = args.search.lower()
        found = [app for app in apps if term in app['name'].lower() or term in app['description'].lower()]
        if found:
            print(f"Found {len(found)} packages matching '{args.search}':")
            for app in found:
                print(f"{app['name']} {app['version']} - {app['description']}")
        else:
            print(f"No packages found matching '{args.search}'.")
    elif args.install:
        app_name_version = args.install
        target_app = next((app for app in apps if f"{app['name']} {app['version']}" == app_name_version), None)
        if not target_app:
            print(f"Error: Package '{app_name_version}' not found.")
            sys.exit(1)
        
        requires_sudo = any(cmd.startswith("sudo ") for cmd in target_app['commands'])
        password = None
        if requires_sudo:
            password = getpass.getpass("Enter your sudo password: ")
            if not password:
                print("Installation cancelled.")
                sys.exit(1)
        
        total = len(target_app['commands'])
        errors = []
        for idx, cmd in enumerate(target_app['commands'], 1):
            progress = int((idx / total) * 100)
            print(f"Progress: {progress}% - Executing: {cmd}")
            
            if cmd.startswith("sudo ") and password:
                full_cmd = f"echo {shlex.quote(password)} | sudo -S {cmd[5:]}"
            else:
                full_cmd = cmd
            
            try:
                subprocess.run(full_cmd, shell=True, check=True, stderr=subprocess.PIPE)
            except subprocess.CalledProcessError as e:
                errors.append(f"Command '{cmd}' failed: {e.stderr.decode().strip()}")
        
        if errors:
            print("Errors occurred:")
            for error in errors:
                print(f"  - {error}")
            sys.exit(1)
        else:
            print("Installation successful!")
            sys.exit(0)
    else:
        parser.print_help()

if __name__ == "__main__":
    if "--cli" in sys.argv:
        sys.argv.remove("--cli")
        cli_main()
    else:
        app = QApplication(sys.argv)
        installer = AppInstaller()
        sys.exit(app.exec_())
# End of the script
# This script is a simple package manager GUI and CLI for installing applications.
# It provides a graphical interface for searching, viewing details, and installing applications,
# as well as a command-line interface for listing, searching, and installing applications.
# It uses PyQt5 for the GUI and subprocess for executing shell commands.
# The script is designed to be user-friendly and provides feedback during the installation process.
# It handles errors gracefully and allows users to toggle between light and dark themes.
# The script is structured to be modular, with separate functions for loading applications,
# executing commands, and managing the GUI.
# The script also includes logging for debugging and error tracking.
# The script is intended to be run as a standalone application or as a command-line tool.
# It is designed to be cross-platform and should work on any system with Python 3 and the required libraries installed.
# The script is open-source and can be modified or redistributed under the terms of the MIT License.
# The script is provided as-is, without warranty of any kind.
# The author is not responsible for any damages or issues that may arise from using this script.    
