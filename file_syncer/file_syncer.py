# This is a simple file syncer that can sync files from one folder to another folder.
# Date: 2024-07-30
# Author: Qing Wu
# Version: 0.2
# Change log:
# v0.2: Add the to support to sync files in folders

from gui.Ui_file_syncer import Ui_MainWindow
from gui import resources_rc
from PyQt5.QtWidgets import QMainWindow, QFileDialog, QMessageBox, QApplication, QProgressDialog
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot, Qt
from PyQt5.QtGui import QIcon
import win32file
import sys
import os
import shutil
from datetime import datetime
import time

class FileSyncer(QMainWindow):
    log_signal = pyqtSignal(str)
    stop_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.log = ""
        self.setWindowTitle("File Syncer v0.2")
        # set the icon
        self.setWindowIcon(QIcon(':/icon.png'))
        
        self.available_files = []
        self.copying_files_target_1 = []
        self.copying_files_target_2 = []
        self.target_1_files = []
        self.target_2_files = []
        
        self.ui.pushButton_open_detection_folder.clicked.connect(
            lambda: self.set_folder_path(self.ui.lineEdit_detection_foler))
        self.ui.pushButton_open_target_foler_1.clicked.connect(
            lambda: self.set_folder_path(self.ui.lineEdit_target_folder_1))
        self.ui.pushButton_open_target_foler_2.clicked.connect(
            lambda: self.set_folder_path(self.ui.lineEdit_target_folder_2))
        
        self.ui.pushButton_start.clicked.connect(self.start_syncing)
        self.ui.pushButton_stop.clicked.connect(self.stop_syncing)
        
        self.sync_thread = None
        
        self.detction_folder = ""
        self.target_folder_1 = ""
        self.target_folder_2 = ""
        self.refresh_time = 60
        self.min_file_size = 0
        
        self.file_prefix = ""
        self.file_contains = ""
        self.file_suffix = ""
        self.file_prefix_status = False
        self.file_contains_status = False
        self.file_suffix_status = False

        self.log_signal.connect(self.add_log)
        
        # self.ui.lineEdit_detection_foler.setText("D:/test_target1")
        # self.ui.lineEdit_target_folder_1.setText("D:/test_target2")

    def update_settings(self):
        self.detction_folder = self.ui.lineEdit_detection_foler.text()
        self.target_folder_1 = self.ui.lineEdit_target_folder_1.text()
        self.refresh_time = int(self.ui.spinBox_refresh_time.text())
        self.min_file_size = int(self.ui.spinBox_mini_file_size.text())
        
        self.file_prefix = self.ui.lineEdit_file_name_prefix.text()
        self.file_contains = self.ui.lineEdit_file_name_contains.text()
        self.file_suffix = self.ui.lineEdit_file_name_suffix.text()
        
        if self.ui.checkBox_enable_target_folder.isChecked():
            target_folder_2 = self.ui.lineEdit_target_folder_2.text()
            if target_folder_2 == "":
                QMessageBox.warning(self, "Warning", "Please enter the target folder 2")
                return False
            elif target_folder_2 == self.target_folder_1:
                QMessageBox.warning(self, "Warning", "Target folder 1 and target folder 2 cannot be the same")
                return False
            else:
                self.target_folder_2 = target_folder_2
            
        if self.ui.checkBox_enable_file_name_prefix.isChecked():
            file_prefix = self.ui.lineEdit_file_name_prefix.text()
            if file_prefix == "":
                QMessageBox.warning(self, "Warning", "Please enter the file name prefix")
                return False
            else:
                self.file_prefix = file_prefix
        if self.ui.checkBox_enable_file_name_contains.isChecked():
            file_contains = self.ui.lineEdit_file_name_contains.text()
            if file_contains == "":
                QMessageBox.warning(self, "Warning", "Please enter the file name contains")
                return False
            else:
                self.file_contains = file_contains
        
        if self.ui.checkBox_enable_file_name_suffix.isChecked():
            file_suffix = self.ui.lineEdit_file_name_suffix.text()
            if file_suffix == "":
                QMessageBox.warning(self, "Warning", "Please enter the file name suffix")
                return False
            else:
                self.file_suffix = file_suffix
        
        return True

    @pyqtSlot(str)
    def add_log(self, log: str):
        current_time = datetime.now().strftime("%H:%M:%S")
        log = f"[{current_time}] {log}"
        self.ui.plainTextEdit_log.appendPlainText(log)
        self.log += log + "\n"

    def set_folder_path(self, line_edit):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        line_edit.setText(folder_path)

    def scan_target_folders(self):
        '''
        Scan target folders and update: target_1_files, target_2_files, copying_files_target_1, copying_files_target_2
        Remove files that are being copied from the list of available files.
        '''
        self.target_1_files = os.listdir(self.target_folder_1) 
        self.target_2_files = os.listdir(self.target_folder_2) if self.ui.checkBox_enable_target_folder.isChecked() else []
        
        self.copying_files_target_1 = [file.replace(".copying", "") for file in self.target_1_files if file.endswith(".copying")]
        self.copying_files_target_2 = [file.replace(".copying", "") for file in self.target_2_files if file.endswith(".copying")]
        
        # Log the files that are being copied to target folders
        self.log_signal.emit(f"[{len(self.copying_files_target_1)}] files are being copied to {self.target_folder_1}")
        print(f'Files are being copied to {self.target_folder_1}:\n{self.copying_files_target_1}\n')
        if self.target_folder_2 != "":
            self.log_signal.emit(f"[{len(self.copying_files_target_2)}] files are being copied to {self.target_folder_2}")
            print(f'Files are being copied to {self.target_folder_2}:\n{self.copying_files_target_2}\n')
        
        self.target_1_files = [file for file in self.target_1_files if not file.endswith(".copying")]
        print(f'target_1_files: {self.target_1_files}')
        if self.target_folder_2 != "":
            self.target_2_files = [file for file in self.target_2_files if not file.endswith(".copying")]
            print(f'target_2_files: {self.target_2_files}')

    def scan_source_folder(self):
        '''
        Scan detection folder and update: available_files
        '''
        self.available_files = []
        for root, dirs, files in os.walk(self.detction_folder):
            for file in files:
                file_path = os.path.join(root, file)
                if self.is_file_valid(file_path):
                    relative_path = os.path.relpath(file_path, self.detction_folder)
                    self.available_files.append(relative_path)

        self.log_signal.emit(f"-----------Scanning folder: {self.detction_folder}------------")
        self.log_signal.emit(f"[{len(self.available_files)}] files found.")
        
        # Check if files are already in target folders, and log the information
        target1_existing_files = [file for file in self.available_files if os.path.exists(os.path.join(self.target_folder_1, file))]
        self.log_signal.emit(f"[{len(target1_existing_files)}] files already in {self.target_folder_1}\n{target1_existing_files}")
        print(f'target1_existing_files:\n{target1_existing_files}\n')

        if self.ui.checkBox_enable_target_folder.isChecked():
            target2_existing_files = [file for file in self.available_files if os.path.exists(os.path.join(self.target_folder_2, file))]
            self.log_signal.emit(f"[{len(target2_existing_files)}] files already in {self.target_folder_2}")
            print(f'target2_existing_files:\n{target2_existing_files}\n')

    def is_file_valid(self, file_path):
        file_name = os.path.basename(file_path)
        if self.file_prefix_status and not file_name.startswith(self.file_prefix):
            return False
        if self.file_contains_status and self.file_contains not in file_name:
            return False
        if self.file_suffix_status and not file_name.endswith(self.file_suffix):
            return False
        if os.path.getsize(file_path) <= self.min_file_size * 1024 * 1024:
            return False
        if self.is_file_being_written(file_path):
            return False
        return True


    def is_file_being_written(self, file_path):
        try:
            handle = win32file.CreateFile(
                file_path,
                win32file.GENERIC_WRITE,
                win32file.FILE_SHARE_READ,
                None,
                win32file.OPEN_EXISTING,
                win32file.FILE_ATTRIBUTE_NORMAL,
                None
            )
            win32file.CloseHandle(handle)
            return False
        except Exception:
            return True

    def enable_or_disable_settings(self, enable: bool):
        normal_components = [
            self.ui.lineEdit_detection_foler,
            self.ui.lineEdit_target_folder_1,
            self.ui.lineEdit_target_folder_2,
            self.ui.pushButton_open_detection_folder,
            self.ui.pushButton_open_target_foler_1,
            self.ui.spinBox_refresh_time,
            self.ui.spinBox_mini_file_size,
            self.ui.checkBox_enable_file_name_prefix,
            self.ui.checkBox_enable_file_name_contains,
            self.ui.checkBox_enable_file_name_suffix,
            self.ui.checkBox_enable_target_folder,
            self.ui.pushButton_start
        ]
        for component in normal_components:
            component.setEnabled(enable)
            
        condition_componet_dict = {
            self.ui.checkBox_enable_target_folder: [self.ui.lineEdit_target_folder_2],
            self.ui.checkBox_enable_file_name_prefix: [self.ui.lineEdit_file_name_prefix],
            self.ui.checkBox_enable_file_name_contains: [self.ui.lineEdit_file_name_contains],
            self.ui.checkBox_enable_file_name_suffix: [self.ui.lineEdit_file_name_suffix]
        }
        
        for condition_component, target_components in condition_componet_dict.items():
            for target_component in target_components:
                target_component.setEnabled(enable and condition_component.isChecked())
    
    def clean_up_temp_files(self):
        # 删除临时的 .copying 文件
        for folder in [self.target_folder_1, self.target_folder_2] if self.ui.checkBox_enable_target_folder.isChecked() else [self.target_folder_1]:
            for root, _, files in os.walk(folder):
                for file in files:
                    if file.endswith(".copying"):
                        file_path = os.path.join(root, file)
                        start_time = time.time()
                        while True:
                            try:
                                os.chmod(file_path, 0o777)  # try to change the file permission to 777 to delete it
                                os.remove(file_path)
                                self.log_signal.emit(f"Removed unfinished file: {file_path}")
                                break
                            except Exception as e:
                                self.log_signal.emit(f"Error removing file {file_path}: {e}")
                                time.sleep(1)  
                            if time.time() - start_time > 30:  # set a time limit for removing the file
                                self.log_signal.emit(f"Failed to remove {file_path} after multiple attempts")
                                QMessageBox.warning(self, "Warning", f"Failed to remove {file_path} after multiple attempts")
                                break


    def stop_syncing(self):
        reply = QMessageBox.question(self, "Stop Syncing", "Are you sure you want to stop syncing?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.log_signal.emit("Stopping syncing...")
            self.enable_or_disable_settings(True)  # enable settings and start button
            self.ui.pushButton_stop.setEnabled(False)  # disable Stop button
            if self.sync_thread:
                self.progress_dialog = QProgressDialog("Stopping, please wait...", "Cancel", 0, 0, self)
                self.progress_dialog.setWindowTitle("Stopping Sync")
                self.progress_dialog.setWindowModality(Qt.WindowModal)
                self.progress_dialog.show()
                self.sync_thread.stop()
                self.sync_thread.finished.connect(self.on_sync_thread_finished)
        else:
            return

    def on_sync_thread_finished(self):
        self.progress_dialog.close()
        self.clean_up_temp_files()
        self.log_signal.emit("Syncing stopped and cleaned up temporary files.")

    def start_syncing(self):
        if not self.update_settings():
            return
                
        if not os.path.exists(self.detction_folder):
            QMessageBox.warning(self, "Warning", "Detection folder not found, please check the path")
            self.log_signal.emit(f"Detection folder not found: {self.detction_folder}")
            return
        if not os.path.exists(self.target_folder_1):
            QMessageBox.warning(self, "Warning", "Target folder 1 not found, please check the path")
            self.log_signal.emit(f"Target folder 1 not found: {self.target_folder_1}")
            return
        if self.ui.checkBox_enable_target_folder.isChecked() and (not os.path.exists(self.target_folder_2)):
            QMessageBox.warning(self, "Warning", "Target folder 2 not found, please check the path")
            self.log_signal.emit(f"Target folder 2 not found: {self.target_folder_2}")
            return
        
        self.log_signal.emit("Starting syncing...")
        
        self.enable_or_disable_settings(False)  # disable settings and start button       
        self.ui.pushButton_stop.setEnabled(True)  # enable Stop button

        self.sync_thread = SyncThread(self)
        self.sync_thread.log_signal.connect(self.add_log)
        self.stop_signal.connect(self.sync_thread.handle_stop)
        self.sync_thread.start()

    def closeEvent(self, event):
        reply = QMessageBox.question(self, "Quit", "Are you sure you want to quit?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            if self.sync_thread and self.sync_thread.isRunning():
                self.stop_syncing()
                self.sync_thread.finished.connect(QApplication.quit)
                event.ignore()  # ignore the close event, wait for the sync_thread to finish
            else:
                event.accept()
        else:
            event.ignore()

class SyncThread(QThread):
    log_signal = pyqtSignal(str)

    def __init__(self, syncer):
        super().__init__()
        self.syncer = syncer
        self.running = True

    def run(self):
        while self.running:
            self.syncer.scan_target_folders()
            self.syncer.scan_source_folder()
            self.copy_files_with_check() 
            for _ in range(self.syncer.refresh_time * 10):  # check every 0.1 second
                if not self.running:
                    return
                time.sleep(0.1)

    def stop(self):
        self.running = False

    @pyqtSlot()
    def handle_stop(self):
        self.stop()
        self.log_signal.emit("Stopped syncing.")
        self.wait()
        self.finished.emit()  # emit the finished signal to close the progress dialog


    def copy_files_with_check(self):
        target_folders = [self.syncer.target_folder_1]
        if self.syncer.ui.checkBox_enable_target_folder.isChecked():
            target_folders.append(self.syncer.target_folder_2)

        for target_folder in target_folders:
            existing_files = set(os.path.relpath(os.path.join(root, file), target_folder)
                                for root, _, files in os.walk(target_folder) for file in files)

            for relative_path in self.syncer.available_files:
                if not self.running:
                    return  # exit the loop immediately

                source_path = os.path.join(self.syncer.detction_folder, relative_path)
                target_path_temp = os.path.join(target_folder, relative_path + ".copying")
                target_path = os.path.join(target_folder, relative_path)
                
                if relative_path in existing_files or os.path.exists(target_path_temp):
                    self.syncer.log_signal.emit(f"[{relative_path}] is being copied or already exists, skipping...")
                    continue

                target_dir = os.path.dirname(target_path)
                if not os.path.exists(target_dir):
                    os.makedirs(target_dir)

                try:
                    self.syncer.log_signal.emit(f"Copying '{relative_path}' -> '{target_folder}'")
                    shutil.copyfile(source_path, target_path_temp)
                    if not self.running:
                        return  # exit the loop immediately
                    shutil.move(target_path_temp, target_path)
                    self.syncer.log_signal.emit(f"Done: '{relative_path}' -> '{target_folder}'")
                except Exception as e:
                    self.syncer.log_signal.emit(f"Error: {e}")
                    self.syncer.log_signal.emit(f"Error: Cannot copy file: {relative_path} to {target_folder}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FileSyncer()
    window.ui.pushButton_stop.setEnabled(False) 
    window.show()
    sys.exit(app.exec_())
