import sys
import os
import logging
import subprocess
import json
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QListWidget, 
    QPushButton, QVBoxLayout, QHBoxLayout, QMessageBox, QInputDialog, 
    QCheckBox, QProgressBar, QTextEdit
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

# Configure logging
logging.basicConfig(level=logging.DEBUG)

PKG_FILE = "pkg.cpm"
APP_FILE = "app.txt"
THEME_FILE = "theme.cfg"

# Utility to convert app.txt to pkg.cpm
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

# Load apps from pkg.cpm
def load_apps():
    try:
        convert_app_txt_to_pkg_cpm()

        if not os.path.exists(PKG_FILE):
            logging.error("No package file found!")
            QMessageBox.critical(None, "Error", "No package file found!")
            return []

        logging.info(f"Loading app list from: {PKG_FILE}")
        with open(PKG_FILE, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        logging.error("Package file not found!")
        QMessageBox.critical(None, "Error", "Package file not found!")
        return []
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing {PKG_FILE}: {e}")
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
        errors = []  # Collect all errors
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
        self.progress_bar.hide()  # Initially hide the progress bar
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

        self.apply_theme()  # Apply the theme based on the saved setting
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
                    self.progress_bar.show()  # Show the progress bar during installation

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
        self.progress_bar.hide()  # Hide the progress bar on completion
        QMessageBox.warning(
            self, "Installation Completed with Errors",
            "Installation completed, but some commands failed:\n" + "\n".join(errors)
        )

    def on_success(self):
        self.install_button.setEnabled(True)
        self.progress_bar.hide()  # Hide the progress bar on success
        QMessageBox.information(self, "Installation", "Installation completed successfully!")
        os.execv(sys.argv[0], sys.argv)

    def toggle_theme(self):
        self.dark_mode = self.theme_toggle.isChecked()
        self.save_theme_setting()
        self.apply_theme()

    def apply_theme(self):
        if self.dark_mode:
            self.set_dark_theme()
        else:
            self.set_light_theme()

    def set_dark_theme(self):
        self.setStyleSheet("""
            QWidget { background-color: #2e2e2e; color: white; }
            QPushButton { background-color: #1e1e1e; color: white; }
            QLineEdit, QListWidget, QProgressBar, QTextEdit { background-color: #444; color: white; }
        """)

    def set_light_theme(self):
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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    installer = AppInstaller()
    sys.exit(app.exec_())
