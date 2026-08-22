"""
Adaptive Framework Desktop GUI - PyQt6-based desktop application.
"""

import sys
import asyncio
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTextEdit, QLineEdit, QPushButton, QLabel,
    QTreeWidget, QTreeWidgetItem, QSplitter, QListWidget,
    QListWidgetItem, QMessageBox, QInputDialog, QMenu,
    QToolBar, QStatusBar, QDockWidget, QScrollArea,
    QFrame, QProgressBar, QComboBox, QCheckBox,
    QGroupBox, QFormLayout, QSpinBox
)
from PyQt6.QtCore import (
    Qt, QThread, QTimer, pyqtSignal, pyqtSlot,
    QUrl, QSize, QSettings
)
from PyQt6.QtGui import (
    QAction, QIcon, QFont, QColor, QPalette,
    QTextCursor, QTextCharFormat
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel

from adaptive_framework import create_framework, AdaptiveFramework


class AsyncWorker(QThread):
    """Worker thread for async operations."""
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    
    def __init__(self, coro):
        super().__init__()
        self.coro = coro
    
    def run(self):
        try:
            result = asyncio.run(self.coro)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class LogHandler:
    """Handler to redirect logs to GUI."""
    def __init__(self, text_edit: QTextEdit):
        self.text_edit = text_edit
    
    def write(self, message: str):
        if message.strip():
            self.text_edit.append(message.strip())
            # Auto-scroll
            cursor = self.text_edit.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.text_edit.setTextCursor(cursor)


class AgentControlWidget(QWidget):
    """Widget for controlling the autonomous agent."""
    
    def __init__(self, framework: AdaptiveFramework):
        super().__init__()
        self.framework = framework
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Goal input
        goal_group = QGroupBox("Set Goal")
        goal_layout = QVBoxLayout()
        
        self.goal_input = QLineEdit()
        self.goal_input.setPlaceholderText("Enter goal description...")
        goal_layout.addWidget(QLabel("Goal:"))
        goal_layout.addWidget(self.goal_input)
        
        criteria_layout = QHBoxLayout()
        self.criteria_input = QLineEdit()
        self.criteria_input.setPlaceholderText("Success criteria (comma-separated)")
        criteria_layout.addWidget(QLabel("Criteria:"))
        criteria_layout.addWidget(self.criteria_input)
        goal_layout.addLayout(criteria_layout)
        
        self.iterations_spin = QSpinBox()
        self.iterations_spin.setRange(1, 100)
        self.iterations_spin.setValue(20)
        goal_layout.addWidget(QLabel("Max Iterations:"))
        goal_layout.addWidget(self.iterations_spin)
        
        btn_layout = QHBoxLayout()
        self.run_btn = QPushButton("Run Goal")
        self.run_btn.clicked.connect(self.run_goal)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_agent)
        self.stop_btn.setEnabled(False)
        btn_layout.addWidget(self.run_btn)
        btn_layout.addWidget(self.stop_btn)
        goal_layout.addLayout(btn_layout)
        
        goal_group.setLayout(goal_layout)
        layout.addWidget(goal_group)
        
        # Status
        status_group = QGroupBox("Agent Status")
        status_layout = QVBoxLayout()
        
        self.status_label = QLabel("Status: Idle")
        self.iteration_label = QLabel("Iteration: 0")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.iteration_label)
        status_layout.addWidget(self.progress_bar)
        
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        # Task list
        task_group = QGroupBox("Tasks")
        task_layout = QVBoxLayout()
        
        self.task_list = QTreeWidget()
        self.task_list.setHeaderLabels(["Description", "Status", "Action"])
        task_layout.addWidget(self.task_list)
        
        task_group.setLayout(task_layout)
        layout.addWidget(task_group)
        
        self.setLayout(layout)
    
    def run_goal(self):
        goal = self.goal_input.text().strip()
        if not goal:
            return
        
        criteria = [c.strip() for c in self.criteria_input.text().split(",") if c.strip()]
        max_iter = self.iterations_spin.value()
        
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText("Status: Running...")
        self.task_list.clear()
        
        async def run():
            return await self.framework.execute("agent.run", {
                "goal": {"description": goal, "success_criteria": criteria},
                "max_iterations": max_iter
            })
        
        self.worker = AsyncWorker(run())
        self.worker.finished.connect(self.on_goal_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()
    
    def stop_agent(self):
        # Would need to implement pause in framework
        self.status_label.setText("Status: Stopping...")
    
    @pyqtSlot(object)
    def on_goal_finished(self, result):
        state = result.get("state", {})
        status = state.get("status", "unknown")
        iteration = state.get("iteration", 0)
        
        self.status_label.setText(f"Status: {status.capitalize()}")
        self.iteration_label.setText(f"Iteration: {iteration}")
        self.progress_bar.setValue(100 if status == "completed" else 0)
        
        self.task_list.clear()
        for task in state.get("tasks", []):
            item = QTreeWidgetItem([
                task.get("description", ""),
                task.get("status", ""),
                task.get("action", "")
            ])
            if task.get("status") == "completed":
                item.setBackground(1, QColor("lightgreen"))
            elif task.get("status") == "failed":
                item.setBackground(1, QColor("lightcoral"))
            self.task_list.addTopLevelItem(item)
        
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
    
    @pyqtSlot(str)
    def on_error(self, error):
        self.status_label.setText(f"Status: Error")
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        QMessageBox.critical(self, "Error", error)


class MemoryWidget(QWidget):
    """Widget for memory management."""
    
    def __init__(self, framework: AdaptiveFramework):
        super().__init__()
        self.framework = framework
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Search
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search memories...")
        self.search_input.returnPressed.connect(self.search_memories)
        search_layout.addWidget(self.search_input)
        
        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self.search_memories)
        search_layout.addWidget(self.search_btn)
        layout.addLayout(search_layout)
        
        # Vector search
        vec_layout = QHBoxLayout()
        self.vec_search = QLineEdit()
        self.vec_search.setPlaceholderText("Semantic search...")
        self.vec_search.returnPressed.connect(self.vector_search)
        vec_layout.addWidget(self.vec_search)
        
        self.vec_btn = QPushButton("Vector Search")
        self.vec_btn.clicked.connect(self.vector_search)
        vec_layout.addWidget(self.vec_btn)
        layout.addLayout(vec_layout)
        
        # Results
        self.results_list = QTreeWidget()
        self.results_list.setHeaderLabels(["Type", "Content", "Confidence"])
        layout.addWidget(self.results_list)
        
        # Add memory
        add_group = QGroupBox("Add Memory")
        add_layout = QFormLayout()
        
        self.mem_type = QComboBox()
        self.mem_type.addItems(["fact", "preference", "pattern", "skill", "correction"])
        add_layout.addRow("Type:", self.mem_type)
        
        self.mem_content = QTextEdit()
        self.mem_content.setMaximumHeight(80)
        add_layout.addRow("Content:", self.mem_content)
        
        self.add_mem_btn = QPushButton("Add Memory")
        self.add_mem_btn.clicked.connect(self.add_memory)
        add_layout.addRow(self.add_mem_btn)
        
        add_group.setLayout(add_layout)
        layout.addWidget(add_group)
        
        self.setLayout(layout)
    
    def search_memories(self):
        query = self.search_input.text().strip()
        if not query:
            return
        
        async def search():
            return await self.framework.recall(limit=20)
        
        self.worker = AsyncWorker(search())
        self.worker.finished.connect(self.on_search_results)
        self.worker.start()
    
    def vector_search(self):
        query = self.vec_search.text().strip()
        if not query or not self.framework.vector_memory:
            return
        
        async def search():
            return await self.framework.vector_memory.search(query, limit=20)
        
        self.worker = AsyncWorker(search())
        self.worker.finished.connect(self.on_vector_results)
        self.worker.start()
    
    @pyqtSlot(object)
    def on_search_results(self, memories):
        self.results_list.clear()
        for m in memories:
            item = QTreeWidgetItem([
                m.type,
                str(m.content)[:100],
                f"{m.confidence:.2f}"
            ])
            self.results_list.addTopLevelItem(item)
    
    @pyqtSlot(object)
    def on_vector_results(self, results):
        self.results_list.clear()
        for entry, score in results:
            item = QTreeWidgetItem([
                "vector",
                entry.text[:100],
                f"{score:.3f}"
            ])
            self.results_list.addTopLevelItem(item)
    
    def add_memory(self):
        content_text = self.mem_content.toPlainText().strip()
        if not content_text:
            return
        
        async def add():
            return await self.framework.remember(
                type=self.mem_type.currentText(),
                content={"data": content_text},
                confidence=0.8
            )
        
        self.worker = AsyncWorker(add())
        self.worker.finished.connect(lambda r: self.mem_content.clear())
        self.worker.start()


class MCPWidget(QWidget):
    """Widget for MCP server management."""
    
    def __init__(self, framework: AdaptiveFramework):
        super().__init__()
        self.framework = framework
        self.init_ui()
        self.refresh_servers()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Connect server
        connect_group = QGroupBox("Connect MCP Server")
        connect_layout = QFormLayout()
        
        self.server_name = QLineEdit()
        self.server_name.setPlaceholderText("my-server")
        connect_layout.addRow("Name:", self.server_name)
        
        self.server_cmd = QLineEdit()
        self.server_cmd.setPlaceholderText("npx @modelcontextprotocol/server-filesystem /path")
        connect_layout.addRow("Command:", self.server_cmd)
        
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.connect_server)
        connect_layout.addRow(self.connect_btn)
        
        connect_group.setLayout(connect_layout)
        layout.addWidget(connect_group)
        
        # Server list
        self.server_list = QTreeWidget()
        self.server_list.setHeaderLabels(["Name", "Tools", "Resources", "Prompts"])
        layout.addWidget(self.server_list)
        
        # Tool caller
        tool_group = QGroupBox("Call Tool")
        tool_layout = QFormLayout()
        
        self.tool_server = QComboBox()
        tool_layout.addRow("Server:", self.tool_server)
        
        self.tool_name = QLineEdit()
        tool_layout.addRow("Tool:", self.tool_name)
        
        self.tool_args = QTextEdit()
        self.tool_args.setMaximumHeight(60)
        self.tool_args.setPlainText("{}")
        tool_layout.addRow("Arguments (JSON):", self.tool_args)
        
        self.call_btn = QPushButton("Call Tool")
        self.call_btn.clicked.connect(self.call_tool)
        tool_layout.addRow(self.call_btn)
        
        tool_group.setLayout(tool_layout)
        layout.addWidget(tool_group)
        
        self.setLayout(layout)
    
    def refresh_servers(self):
        async def list_servers():
            return await self.framework.execute("mcp.list_servers", {})
        
        self.worker = AsyncWorker(list_servers())
        self.worker.finished.connect(self.on_servers_listed)
        self.worker.start()
    
    @pyqtSlot(object)
    def on_servers_listed(self, result):
        servers = result.get("servers", {})
        self.server_list.clear()
        self.tool_server.clear()
        
        for name, info in servers.items():
            item = QTreeWidgetItem([
                name,
                str(info.get("tools", 0)),
                str(info.get("resources", 0)),
                str(info.get("prompts", 0))
            ])
            self.server_list.addTopLevelItem(item)
            self.tool_server.addItem(name)
    
    def connect_server(self):
        name = self.server_name.text().strip()
        cmd = self.server_cmd.text().strip()
        if not name or not cmd:
            return
        
        async def connect():
            return await self.framework.execute("mcp.connect", {
                "name": name,
                "command": cmd.split()
            })
        
        self.worker = AsyncWorker(connect())
        self.worker.finished.connect(lambda r: self.refresh_servers())
        self.worker.start()
    
    def call_tool(self):
        server = self.tool_server.currentText()
        tool = self.tool_name.text().strip()
        args_text = self.tool_args.toPlainText().strip()
        
        if not server or not tool:
            return
        
        try:
            args = json.loads(args_text) if args_text else {}
        except json.JSONDecodeError:
            QMessageBox.warning(self, "Error", "Invalid JSON")
            return
        
        async def call():
            return await self.framework.execute("mcp.call_tool", {
                "server": server,
                "tool": tool,
                "arguments": args
            })
        
        self.worker = AsyncWorker(call())
        self.worker.finished.connect(self.on_tool_result)
        self.worker.start()
    
    @pyqtSlot(object)
    def on_tool_result(self, result):
        QMessageBox.information(self, "Tool Result", json.dumps(result, indent=2))


class LogWidget(QWidget):
    """Widget for viewing logs."""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Monospace", 9))
        layout.addWidget(self.log_text)
        
        btn_layout = QHBoxLayout()
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.log_text.clear)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
    
    def log(self, message: str):
        self.log_text.append(message)
        # Keep last 1000 lines
        doc = self.log_text.document()
        if doc.blockCount() > 1000:
            cursor = QTextCursor(doc)
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor.movePosition(QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.KeepAnchor, doc.blockCount() - 1000)
            cursor.removeSelectedText()


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.framework: Optional[AdaptiveFramework] = None
        self.init_ui()
        self.init_framework()
    
    def init_ui(self):
        self.setWindowTitle("Adaptive Framework")
        self.setMinimumSize(1200, 800)
        
        # Central widget with tabs
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # Placeholder widgets (will be replaced after framework init)
        self.agent_widget = QLabel("Initializing...")
        self.memory_widget = QLabel("Initializing...")
        self.mcp_widget = QLabel("Initializing...")
        self.log_widget = LogWidget()
        
        self.tabs.addTab(self.agent_widget, "Agent")
        self.tabs.addTab(self.memory_widget, "Memory")
        self.tabs.addTab(self.mcp_widget, "MCP")
        self.tabs.addTab(self.log_widget, "Logs")
        
        # Toolbar
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        
        # Actions
        self.refresh_action = QAction("Refresh", self)
        self.refresh_action.triggered.connect(self.refresh_all)
        toolbar.addAction(self.refresh_action)
        
        toolbar.addSeparator()
        
        self.settings_action = QAction("Settings", self)
        toolbar.addAction(self.settings_action)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Initializing framework...")
        
        # Menu bar
        menubar = self.menuBar()
        
        file_menu = menubar.addMenu("File")
        file_menu.addAction("New Goal", self.new_goal_dialog)
        file_menu.addAction("Exit", self.close)
        
        view_menu = menubar.addMenu("View")
        view_menu.addAction("Toggle Logs", lambda: self.tabs.setTabVisible(3, not self.tabs.isTabVisible(3)))
        
        help_menu = menubar.addMenu("Help")
        help_menu.addAction("Documentation", lambda: QMessageBox.information(self, "Docs", "See README.md"))
        help_menu.addAction("About", self.show_about)
    
    def init_framework(self):
        """Initialize framework in background."""
        async def init():
            fw = await create_framework()
            return fw
        
        self.init_worker = AsyncWorker(init())
        self.init_worker.finished.connect(self.on_framework_ready)
        self.init_worker.error.connect(self.on_init_error)
        self.init_worker.start()
    
    @pyqtSlot(object)
    def on_framework_ready(self, fw):
        self.framework = fw
        self.status_bar.showMessage("Framework ready")
        
        # Replace placeholder widgets
        self.agent_widget = AgentControlWidget(fw)
        self.memory_widget = MemoryWidget(fw)
        self.mcp_widget = MCPWidget(fw)
        
        self.tabs.removeTab(0)
        self.tabs.insertTab(0, self.agent_widget, "Agent")
        self.tabs.removeTab(1)
        self.tabs.insertTab(1, self.memory_widget, "Memory")
        self.tabs.removeTab(2)
        self.tabs.insertTab(2, self.mcp_widget, "MCP")
        
        # Setup log handler
        import logging
        logging.getLogger().addHandler(logging.StreamHandler(self.log_widget))
        
        self.log_widget.log("Framework initialized successfully")
    
    @pyqtSlot(str)
    def on_init_error(self, error):
        self.status_bar.showMessage(f"Error: {error}")
        QMessageBox.critical(self, "Initialization Error", error)
    
    def refresh_all(self):
        if self.framework:
            if hasattr(self.agent_widget, 'refresh_servers'):
                self.agent_widget.refresh_servers()
            if hasattr(self.mcp_widget, 'refresh_servers'):
                self.mcp_widget.refresh_servers()
    
    def new_goal_dialog(self):
        goal, ok = QInputDialog.getText(self, "New Goal", "Enter goal description:")
        if ok and goal:
            self.tabs.setCurrentWidget(self.agent_widget)
            self.agent_widget.goal_input.setText(goal)
    
    def show_about(self):
        QMessageBox.about(self, "About Adaptive Framework",
            "Adaptive Framework v0.1.0\n\n"
            "Self-improving AI agent with:\n"
            "• MCP Integration\n"
            "• Vector Memory (Semantic Search)\n"
            "• Autonomous Agent Loop\n"
            "• Self-Learning Capabilities\n\n"
            "Built with PyQt6")
    
    def closeEvent(self, event):
        if self.framework:
            asyncio.run(self.framework.stop())
        event.accept()


def run_gui(data_dir: Optional[str] = None):
    """Run the desktop GUI application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Adaptive Framework")
    app.setOrganizationName("AdaptiveFramework")
    
    # Set dark theme
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    app.setPalette(palette)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())