"""
Common styling constants and functions for the PyQt6 GUI.
"""

# Nature Theme Colors
COLORS = {
    "bg_main": "#EDF1D6",        # Very light green/cream background
    "bg_secondary": "#FFFFFF",   # White for panels to provide clean contrast
    "bg_hover": "#9DC08B",       # Light green hover state
    "text_primary": "#000000",   # Black for readability
    "text_secondary": "#40513B", # Dark green text
    "text_muted": "#609966",     # Medium green for muted text
    "accent": "#609966",         # Primary brand color (medium green)
    "accent_hover": "#40513B",   # Darker green for hover states
    "accent_secondary": "#9DC08B", # Lighter green
    "border": "#9DC08B",         # Light green borders
    "success": "#609966",        # Vibrant green for online status
    "error": "#FF5252",          # Soft red for offline/errors
    "btn_bg": "#609966",         # Button background
    "btn_hover": "#40513B",      # Button hover
    "scrollbar_bg": "#EDF1D6",   # Scrollbar background
    "scrollbar_handle": "#9DC08B",# Scrollbar handle
    "message_sent": "#9DC08B",   # Bubble color for sent messages
    "message_received": "#FFFFFF", # Bubble color for received messages
}

# Typography
FONT_FAMILY = "'Segoe UI', 'Inter', 'Roboto', 'Helvetica Neue', sans-serif"

MAIN_STYLE = f"""
QMainWindow {{
    background-color: {COLORS['bg_main']};
    color: {COLORS['text_primary']};
    font-family: {FONT_FAMILY};
}}
QMessageBox {{
    background-color: {COLORS['bg_secondary']};
    color: {COLORS['text_primary']};
    font-family: {FONT_FAMILY};
    border-radius: 8px;
}}
QMessageBox QPushButton {{
    background-color: {COLORS['btn_bg']};
    color: #FFFFFF;
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 6px 16px;
    font-weight: 500;
}}
QMessageBox QPushButton:hover {{
    background-color: {COLORS['btn_hover']};
    border: 1px solid {COLORS['accent']};
}}
QStatusBar {{
    background-color: {COLORS['bg_secondary']};
    color: {COLORS['text_secondary']};
    border-top: 1px solid {COLORS['border']};
    font-size: 12px;
    padding: 4px;
}}
QScrollBar:vertical {{
    border: none;
    background: {COLORS['scrollbar_bg']};
    width: 10px;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background: {COLORS['scrollbar_handle']};
    min-height: 20px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical:hover {{
    background: {COLORS['accent']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
"""

SIDEBAR_STYLE = f"""
QWidget {{
    background-color: {COLORS['bg_secondary']};
    border-right: 1px solid {COLORS['border']};
    font-family: {FONT_FAMILY};
}}
QListWidget {{
    background-color: transparent;
    border: none;
    outline: none;
}}
QListWidget::item {{
    color: {COLORS['text_primary']};
    padding: 10px 12px;
    margin: 2px 8px;
    border-radius: 6px;
    font-size: 14px;
    border: 1px solid transparent;
}}
QListWidget::item:hover {{
    background-color: {COLORS['bg_hover']};
    color: #FFFFFF;
    border: 1px solid {COLORS['accent']};
}}
QListWidget::item:selected {{
    background-color: {COLORS['accent']};
    color: #FFFFFF;
    font-weight: bold;
    border: 1px solid {COLORS['accent_hover']};
}}
"""

ADD_GROUP_BUTTON_STYLE = f"""
QPushButton {{
    background-color: transparent;
    color: {COLORS['accent']};
    border: 1px solid {COLORS['accent']};
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: bold;
}}
QPushButton:hover {{
    background-color: {COLORS['accent']};
    color: #FFFFFF;
}}
"""

CHAT_AREA_STYLE = f"""
QWidget {{
    background-color: {COLORS['bg_main']};
}}
"""

HEADER_STYLE = f"""
QWidget {{
    background-color: {COLORS['bg_secondary']};
    border-bottom: 1px solid {COLORS['border']};
}}
"""

MESSAGE_INPUT_STYLE = f"""
QLineEdit {{
    background-color: #FFFFFF;
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 18px;
    padding: 8px 16px;
    font-size: 14px;
    font-family: {FONT_FAMILY};
}}
QLineEdit:focus {{
    border: 1px solid {COLORS['accent']};
    background-color: #FAFAFA;
}}
"""

SEND_BUTTON_STYLE = f"""
QPushButton {{
    background-color: {COLORS['accent']};
    color: #FFFFFF;
    border: none;
    border-radius: 18px;
    padding: 8px 20px;
    font-size: 14px;
    font-weight: bold;
    font-family: {FONT_FAMILY};
}}
QPushButton:hover {{
    background-color: {COLORS['accent_hover']};
}}
QPushButton:pressed {{
    background-color: {COLORS['text_secondary']};
}}
"""

ENCRYPTION_BADGE_STYLE = f"""
QLabel {{
    background-color: {COLORS['bg_main']};
    color: {COLORS['success']};
    border: 1px solid {COLORS['success']};
    border-radius: 12px;
    padding: 4px 8px;
    font-size: 12px;
}}
"""
