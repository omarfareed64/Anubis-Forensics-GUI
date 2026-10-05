# Anubis Forensics GUI - Advanced Digital Forensics Platform

A comprehensive digital forensics platform with a modern PyQt5-based GUI frontend designed for professional forensic analysis, remote acquisition, and evidence management.

## 🎯 Overview

Anubis Forensics GUI is a powerful digital forensics tool that provides:

- **Case Management**: Complete case lifecycle management with evidence tracking
- **Remote Acquisition**: Secure remote file system access and memory acquisition
- **Local Analysis**: Comprehensive local evidence collection and analysis
- **Web Artifact Extraction**: Automated browser artifact collection and analysis
- **USB Device Analysis**: Advanced USB device forensics capabilities
- **Memory Forensics**: Memory dump acquisition and analysis tools
- **AI-Powered Analysis**: LLM integration for automated report generation and case insights
- **Automated Workflows**: Streamlined investigation processes for digital forensics professionals

**Positioning**: Anubis Forensics GUI serves as a comprehensive digital forensics solution similar to Magnet AXIOM Cyber, designed to help investigators automate their tasks and streamline the forensic analysis process. The platform integrates Large Language Models (LLMs) to generate helpful reports about cases, providing intelligent insights and automated documentation.

## 🏗️ Architecture Overview

### Frontend (PyQt5 GUI)
- **Technology**: PyQt5 with modern Material Design-inspired styling
- **Architecture**: MVC pattern with service layer abstraction
- **State Management**: Centralized through service layer
- **Async Support**: Non-blocking backend operations
- **Responsive Design**: Adaptive UI for different screen sizes

### Backend Integration
- **API Client**: Abstracted HTTP communication layer with retry logic
- **Data Models**: Structured dataclasses for type safety
- **Configuration**: Environment-based configuration management
- **Logging**: Centralized logging with file rotation and error tracking

## 📁 Project Structure

```
Anubis-Forensics-GUI/
├── main.py                     # Application entry point (splash screen → main window)
├── config.py                   # Configuration + .env loader
├── requirements.txt            # Python dependencies
├── run.bat                     # One-click launcher (creates .venv on first run)
├── .env.example                # Optional API keys (VirusTotal, LLM)
├── assets/4x/                  # Icons and logo
├── assets/design/              # UI design source (Adobe Illustrator)
├── cases/                      # One folder per case: info.json, evidence/, memory_analysis/,
│                               #   web_artifacts/, srum_analysis/, registry_analysis/, usb_analysis/, reports/
├── memory_analysis/            # Bundled sample Volatility/VirusTotal output (used when a case has none)
├── pages/                      # PyQt5 user interface
│   ├── base_page.py            # Shared top bar, tab bar and widget styles
│   ├── main_window.py          # Page navigation and the selected case
│   ├── home_page.py            # Create case / add evidence / browse cases
│   ├── case_creation_page.py
│   ├── resource_page.py        # Remote acquisition or local image
│   ├── remote_acquisition_page.py   # Connect to a target (PsExec + C$ share)
│   ├── remote_connection_page.py    # Targeted locations, file browser, memory dumps, evidence table
│   ├── analysis_page.py        # MEMORY / WEB / SRUM / REGISTRY / USB analysis views
│   ├── report_page.py          # Report generation and Markdown/HTML/PDF export
│   └── splash_screen.py
├── services/                   # Forensic logic (no Qt widgets)
│   ├── memory_analyzer.py      # Volatility 3 pipeline, file dumping/hashing, VirusTotal client
│   ├── web_artifact_extractor.py    # Chromium/Firefox history, downloads, cookies, logins, bookmarks
│   ├── srum_analyzer.py        # SRUDB.dat parsing with dissect.esedb (+ SOFTWARE hive look-ups)
│   ├── registry_analyzer.py    # RawCopy acquisition, regipy plugins, hive diff, transaction logs
│   ├── usb_analyzer.py         # USB history from live registry or SYSTEM hive + triage report
│   ├── report_service.py       # Rule-based report builder with optional LLM narrative
│   ├── evidence_store.py       # Evidence descriptors (paths, sizes, SHA256) inside a case
│   ├── filebrowser_session.py  # Password-protected FileBrowser sessions on targets
│   └── api_client.py           # Optional backend API client (not required to run the GUI)
├── utils/
│   ├── paths.py                # Locations of bundled tools and case sub-folders
│   ├── network.py              # Reliable reachability check (real echo reply, not just ping's exit code)
│   ├── logger.py
│   └── file_browser_launcher.py     # Helper process that shows the remote FileBrowser UI (auto-login)
├── tests/                      # Unit tests: python -m unittest discover -v
├── third_party/RawCopy/        # RawCopy source code (AutoIt) by Joakim Schicht
├── PSTools/PsExec.exe          # Remote execution
├── RawCopy.exe                 # Copies locked files (registry hives, SRUM, event logs)
├── winpmem_mini_x64_rc2.exe    # Full memory acquisition
├── procdump.exe                # Per-process memory dumps
├── filebrowser.exe             # Web file browser deployed on the target
└── rla.exe                     # Fallback tool for registry transaction logs
```

## 🚀 Quick Start

### Prerequisites
- **OS**: Windows 10/11 (registry, SRUM and remote acquisition use Windows tools)
- **Python**: 3.10 or newer (tested on 3.13 and 3.14)
- **Administrative privileges**: needed to copy locked files (registry hives, SRUDB.dat) from the local machine
- **Network access**: for remote acquisition (SMB `C$` share + PsExec) and for the optional VirusTotal / LLM look-ups

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/omarfareed64/Anubis-Forensics-GUI.git
   cd Anubis-Forensics-GUI
   ```

2. **Run it** — `run.bat` creates a virtual environment and installs the dependencies on first start:
   ```bat
   run.bat
   ```
   Or manually:
   ```bash
   py -3 -m venv .venv
   .venv\Scripts\python -m pip install -r requirements.txt
   .venv\Scripts\python main.py
   ```

3. **Optional API keys** — copy `.env.example` to `.env` and fill in:
   - `VIRUSTOTAL_API_KEY` to check dumped files and IP addresses against VirusTotal
   - `LLM_API_KEY` (+ `LLM_API_BASE`, `LLM_MODEL`) to let an OpenAI-compatible LLM (Together AI, OpenAI, Groq, Ollama…) write the narrative sections of the report. Without a key the report is still generated by the built-in rule-based engine.

### Typical workflow

1. **Case Info** → create a case (or pick an existing one with *Add Evidence To Existing Case*). Everything the tool produces is stored under `cases/<number>_<name>/`.
2. **Resource** → *Remote Acquisition* (connect to a target with a local administrator account, then acquire targeted locations, browse files, or dump memory with winpmem/procdump) or *Local Image* (reference evidence files already on disk).
3. **Analyze Evidence**
   - **MEMORY**: select a memory image and run Volatility 3 (`windows.info`, `pslist`, `cmdline`, `netscan`, `malfind`, `userassist`), dump files of injected processes, hash them and optionally query VirusTotal. Results are browsable per plugin.
   - **WEB**: extract history, downloads, search terms, cookies, saved logins and bookmarks from Edge/Chrome/Brave/Opera/Firefox profiles (remote host, this machine, or any profile/user folder).
   - **SRUM**: parse `SRUDB.dat` (network usage, application resource usage, connectivity…) with optional `SOFTWARE` hive for user names and Wi-Fi SSIDs.
   - **REGISTRY**: acquire hives with RawCopy, run regipy plugins, diff two hives, apply transaction logs, parse headers.
   - **USB**: USB device history from the live registry or from an acquired `SYSTEM` hive, with triage rules and an HTML report.
4. **Report** → generate the Markdown report (rule-based, optionally enriched by an LLM) and export it as Markdown, HTML or PDF.

## 🔧 Configuration

### Environment Variables (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `VIRUSTOTAL_API_KEY` | `` | Enables VirusTotal look-ups (free key: 4 requests/minute) |
| `LLM_API_KEY` | `` | API key for the report narrative (any OpenAI-compatible endpoint) |
| `LLM_API_BASE` | `https://api.together.xyz/v1` | Chat completions endpoint |
| `LLM_MODEL` | `meta-llama/Llama-3.3-70B-Instruct-Turbo` | Model name |
| `LOG_LEVEL` | `INFO` | Logging level |
| `LOG_FILE` | `logs/app.log` | Log file path |

## 🎯 Core Features

### 1. Case Management
- **Create Cases**: Generate new forensic cases with detailed metadata
- **Case Browser**: Search and filter existing cases
- **Evidence Tracking**: Organize evidence within case folders
- **Case Metadata**: Store case information in structured JSON format

### 2. Remote Acquisition
- **Secure Connections**: Connect to remote machines using Windows credentials
- **File System Access**: Browse remote file systems through embedded web UI
- **Memory Acquisition**: Remote memory dump collection using winpmem
- **Process Dumps**: Remote process memory extraction using procdump
- **Automatic Cleanup**: Secure cleanup of remote services and temporary files

### 3. Local Evidence Collection
- **Register Evidence**: Add disk images, memory images and other files already on disk to a case
- **Memory Image Analysis**: Run the Volatility 3 pipeline on any memory image
- **Locked File Acquisition**: Copy this machine's registry hives and SRUM database with RawCopy (Administrator rights needed)
- **Evidence Records**: Every item is recorded with path, size, SHA-256 and timestamp

### 4. Web Artifact Extraction
- **Browser Forensics**: Automated collection of browser artifacts
- **Bookmarks Analysis**: Extract and analyze browser bookmarks
- **Cookie Analysis**: Browser cookie examination and analysis
- **History Analysis**: Browser history extraction and timeline analysis
- **HTML Reports**: Generate comprehensive web artifact reports

### 5. USB Device Analysis
- **Device Detection**: Automatic USB device identification
- **Artifact Extraction**: USB device artifact collection
- **Timeline Analysis**: USB device usage timeline reconstruction
- **Registry Analysis**: USB device registry key examination

## 🔍 **Five Forensic Analysis Options - Detailed Explanations**

This section explains each type of analysis in general terms. What Anubis itself implements for each option is described in Chapter 4, section 4.2, "How Each Analysis Option Is Implemented".

### **1. Memory Analysis (RAM Forensics)**

**What is Memory Analysis?**
Memory analysis, also known as RAM forensics or volatile memory forensics, involves the examination of a computer's random access memory (RAM) to extract digital evidence that exists only in volatile memory and is lost when the system is powered off.

**Why is Memory Analysis Important?**
- **Volatile Evidence**: Captures evidence that disappears when the system is shut down
- **Running Processes**: Reveals currently running applications and their states
- **Network Connections**: Shows active network connections and communication
- **Encrypted Data**: May contain decrypted data that was encrypted on disk
- **Malware Detection**: Identifies malicious processes and injected code
- **User Activity**: Captures user sessions, passwords, and recent activities

**How Memory Analysis Works:**
1. **Memory Acquisition**: Using tools like WinPmem to create a memory dump
2. **Symbol Resolution**: Identifying the Windows kernel version and loading matching symbol tables (Volatility 2 called these "profiles")
3. **Process Analysis**: Extracting running processes, their memory maps, and loaded modules
4. **Network Analysis**: Identifying active network connections and listening ports
5. **String Extraction**: Searching for meaningful text strings in memory
6. **Artifact Recovery**: Extracting files, registry hives, and other artifacts from memory

**Key Artifacts Revealed:**
- **Running Processes**: List of all active processes with PIDs and memory addresses
- **Network Connections**: Active TCP/UDP connections and associated processes
- **Loaded DLLs**: Dynamic link libraries loaded by processes
- **Command History**: Recently executed commands and command line arguments
- **Encryption Keys**: Cryptographic keys and certificates in memory
- **Browser Data**: Passwords, cookies, and session data from web browsers
- **Malware Artifacts**: Suspicious processes, injected code, and rootkits

**Forensic Value:**
Memory analysis provides a "snapshot" of system activity at the time of acquisition, revealing what was happening on the system when the memory dump was taken. This is crucial for incident response, malware analysis, and understanding user behavior patterns.

---

### **2. Web Artifact Analysis (Browser Forensics)**

**What is Web Artifact Analysis?**
Web artifact analysis involves the examination of web browser data to reconstruct a user's online activities, including browsing history, downloads, bookmarks, cookies, and other web-related artifacts stored by browsers.

**Why is Web Artifact Analysis Important?**
- **User Behavior**: Reveals user's online activities and interests
- **Timeline Reconstruction**: Provides chronological evidence of web browsing
- **Evidence Preservation**: Captures web-based evidence that may be deleted from servers
- **Authentication Data**: Contains login credentials and session information
- **Download History**: Shows files downloaded and their sources
- **Search Queries**: Reveals search terms and visited websites

**How Web Artifact Analysis Works:**
1. **Browser Identification**: Locating browser profile directories
2. **Database Extraction**: Accessing browser databases (SQLite files)
3. **History Analysis**: Parsing browsing history and download records
4. **Cookie Examination**: Extracting authentication and tracking cookies
5. **Bookmark Analysis**: Recovering saved bookmarks and favorites
6. **Cache Analysis**: Examining cached web pages and resources
7. **Form Data**: Extracting saved form data and autofill information

**Key Artifacts Revealed:**
- **Browsing History**: URLs visited, page titles, and timestamps
- **Download Records**: Files downloaded, sources, and completion times
- **Cookies**: Authentication tokens, session data, and tracking information
- **Bookmarks**: Saved websites and folder structures
- **Search Queries**: Terms searched in various search engines
- **Login Credentials**: Saved usernames and encrypted passwords
- **Form Data**: Auto-filled information and saved form entries
- **Cache Files**: Cached web pages, images, and other resources

**Forensic Value:**
Web artifacts provide a comprehensive picture of a user's online activities, including websites visited, searches performed, files downloaded, and authentication patterns. This information is crucial for investigations involving cybercrime, fraud, intellectual property theft, and general user activity analysis.

---

### **3. Registry Analysis (Windows Registry Forensics)**

**What is Registry Analysis?**
Registry analysis involves the examination of the Windows Registry, a hierarchical database that stores configuration settings and options for the Windows operating system and installed applications. The registry contains a wealth of forensic information about system activity and user behavior.

**Why is Registry Analysis Important?**
- **System Configuration**: Reveals system settings and installed software
- **User Activity**: Tracks user actions and application usage
- **Startup Programs**: Identifies programs that start automatically
- **Device History**: Records connected hardware and devices
- **Network Information**: Contains network configuration and connection history
- **Security Settings**: Shows security policies and access controls
- **Timeline Evidence**: Provides timestamps for various system events

**How Registry Analysis Works:**
1. **Hive Identification**: Locating registry hive files (SYSTEM, SOFTWARE, SAM, etc.)
2. **Key Enumeration**: Navigating through registry key hierarchies
3. **Value Extraction**: Reading registry values and their data
4. **Timeline Analysis**: Examining timestamps associated with registry keys
5. **Cross-Reference Analysis**: Correlating data across multiple registry locations
6. **Deleted Key Recovery**: Attempting to recover deleted registry entries

**Key Artifacts Revealed:**
- **UserAssist Keys**: Program execution history and frequency
- **Run Keys**: Programs configured to start automatically
- **USB Device History**: Connected USB devices and their timestamps
- **Network Connections**: Network adapter settings and connection history
- **Installed Software**: List of installed applications and their versions
- **System Information**: Hardware configuration and system details
- **Security Settings**: Password policies and access controls
- **Recent Documents**: Recently accessed files and applications
- **Shell Bags**: User interface customization and folder views

**Forensic Value:**
The Windows Registry serves as a comprehensive log of system activity, providing evidence of user actions, system changes, and application behavior. Registry analysis can reveal when programs were installed, when devices were connected, and what activities occurred on the system over time.

---

### **4. USB Device Analysis (USB Forensics)**

**What is USB Device Analysis?**
USB device analysis involves the examination of artifacts related to USB device connections, including device identification, connection history, and usage patterns. This analysis helps reconstruct when USB devices were connected to a system and what activities occurred with them.

**Why is USB Device Analysis Important?**
- **Device Tracking**: Identifies USB devices that have been connected to the system
- **Timeline Reconstruction**: Provides chronological evidence of device usage
- **Data Transfer Evidence**: Shows when devices were connected and potentially used for data transfer
- **Device Identification**: Reveals device types, manufacturers, and serial numbers
- **Security Investigations**: Important for cases involving data theft or unauthorized access
- **Compliance**: Helps verify device usage policies and compliance requirements

**How USB Device Analysis Works:**
1. **Registry Examination**: Analyzing USB-related registry keys
2. **SetupAPI Log Analysis**: Reviewing device installation logs
3. **Event Log Analysis**: Examining system event logs for USB events
4. **Device Enumeration**: Identifying connected and previously connected devices
5. **Timeline Construction**: Creating chronological timeline of device usage
6. **Metadata Extraction**: Gathering device information and connection details

**Key Artifacts Revealed:**
- **Device Identifiers**: Vendor IDs, product IDs, and serial numbers
- **Connection History**: When devices were first and last connected
- **Device Types**: Storage devices, input devices, network adapters, etc.
- **Driver Information**: Installed drivers and device drivers
- **Mount Points**: Drive letters assigned to storage devices
- **Usage Patterns**: Frequency and duration of device connections
- **Device Names**: User-assigned names and device descriptions
- **Firmware Information**: Device firmware versions and capabilities

**Forensic Value:**
USB device analysis provides crucial evidence in cases involving data theft, unauthorized access, or device usage investigations. It can help establish timelines of device usage, identify specific devices involved in incidents, and provide evidence of data transfer activities.

---

### **5. SRUM Analysis (System Resource Usage Monitor)**

**What is SRUM Analysis?**
SRUM (System Resource Usage Monitor) analysis involves the examination of Windows' built-in system monitoring database that tracks application usage, network activity, and energy consumption. SRUM provides detailed information about how system resources are used over time.

**Why is SRUM Analysis Important?**
- **Application Usage**: Reveals which applications were used and for how long
- **Network Activity**: Tracks network usage patterns and data transfer
- **Energy Consumption**: Shows power usage patterns and battery information
- **User Behavior**: Provides insights into user activity patterns
- **System Performance**: Indicates system resource utilization
- **Timeline Evidence**: Offers detailed chronological data about system usage
- **Compliance Monitoring**: Helps verify software usage compliance

**How SRUM Analysis Works:**
1. **Database Location**: Locating the SRUM database file (Windows\System32\sru\SRUDB.dat)
2. **Database Access**: Opening the ESE (Extensible Storage Engine) database, the same format used by other Windows components; it is not SQLite
3. **Table Extraction**: Reading each provider table and resolving application and user IDs through `SruDbIdMapTable`
4. **Data Parsing**: Converting raw data into meaningful forensic information
5. **Timeline Analysis**: Creating chronological usage patterns
6. **Cross-Reference Analysis**: Correlating data with other forensic sources

**Key Artifacts Revealed:**
- **Application Usage**: Programs executed, duration, and frequency
- **Network Statistics**: Bytes sent/received, connection durations
- **Energy Data**: Energy use per application and battery charge levels
- **User Attribution**: Which user account (SID) ran each application
- **Resource Utilization**: CPU time and bytes read from and written to disk per application
- **Network Interfaces**: Network adapters and Wi-Fi profiles used, with connection durations
- **Push Notifications**: Notifications received per application

**Forensic Value:**
SRUM analysis provides a comprehensive view of system usage patterns, offering detailed evidence about application usage, network activity, and system behavior over time. This information is valuable for understanding user behavior, investigating system performance issues, and establishing usage patterns in forensic investigations.

---

**Integration and Cross-Analysis:**
The five analysis options complement each other:
- **Memory + Registry**: Correlating running processes with registry entries such as UserAssist and Run keys
- **Web + USB**: Linking web downloads with USB device connections
- **SRUM + Registry**: Connecting application usage with users and network profiles
- **Timeline Reconstruction**: Placing events from all sources on one timeline
- **Evidence Correlation**: Cross-referencing findings for stronger conclusions

In Anubis, correlation is currently automated for memory findings (process, parent and child processes, network contacts, dumped files and VirusTotal verdicts). Correlation across all five options and a unified timeline are planned work, described in Chapter 5.

## 🔌 Backend API Integration

### API Client Usage

The application includes a comprehensive API client for backend communication:

```python
from services.api_client import APIClient, SyncAPIClient
from models.data_models import Case, Evidence, SearchCriteria

# Async usage (recommended)
async with APIClient() as client:
    # Create a case
    case_data = {
        "number": "CASE-001",
        "name": "Investigation Case",
        "description": "Digital forensics investigation"
    }
    response = await client.create_case(case_data)
    
    # List cases with filtering
    criteria = SearchCriteria(
        query="investigation",
        filters={"status": "active"},
        page=1,
        page_size=20
    )
    cases_response = await client.list_cases(criteria)

# Sync usage (for compatibility)
client = SyncAPIClient()
response = client.health_check()
```

### Available API Endpoints

#### Case Management
- `POST /cases` - Create new case
- `GET /cases/{id}` - Get case by ID
- `PUT /cases/{id}` - Update case
- `DELETE /cases/{id}` - Delete case
- `GET /cases` - List cases with filtering

#### Evidence Management
- `POST /cases/{case_id}/evidence` - Add evidence to case
- `GET /cases/{case_id}/evidence/{evidence_id}` - Get evidence
- `PUT /cases/{case_id}/evidence/{evidence_id}` - Update evidence
- `DELETE /cases/{case_id}/evidence/{evidence_id}` - Delete evidence
- `GET /cases/{case_id}/evidence` - List evidence

#### Remote Acquisition
- `POST /acquisition/sessions` - Create acquisition session
- `GET /acquisition/sessions/{id}` - Get session details
- `PUT /acquisition/sessions/{id}` - Update session
- `POST /acquisition/sessions/{id}/start` - Start acquisition
- `POST /acquisition/sessions/{id}/stop` - Stop acquisition
- `GET /acquisition/sessions/{id}/progress` - Get progress

#### Agent Management
- `GET /agents` - List available agents
- `GET /agents/{id}` - Get agent details
- `POST /agents` - Register new agent

#### File Operations
- `POST /files/upload` - Upload file
- `GET /health` - Health check

## 🎨 Frontend Development

### UI Architecture

The frontend follows a modular architecture:

- **BasePage**: Common UI elements and styling
- **Page Components**: Individual page implementations
- **MainWindow**: Central navigation and page management
- **Service Layer**: Business logic and API communication

### Adding New Pages

1. **Create the page class**
   ```python
   from pages.base_page import BasePage
   from PyQt5.QtCore import pyqtSignal
   
   class NewPage(BasePage):
       # Define signals for navigation
       next_page_requested = pyqtSignal()
       
       def __init__(self):
           super().__init__()
           self.setup_page_content()
       
       def setup_page_content(self):
           # Add your UI elements here
           pass
   ```

2. **Register in MainWindow**
   ```python
   # In main_window.py
   self.new_page = NewPage()
   self.stacked_widget.addWidget(self.new_page)
   
   # Connect signals
   self.new_page.next_page_requested.connect(self._show_next_page)
   ```

### Styling Guidelines

The application uses consistent styling:

```python
# Colors (defined in base_page.py)
COLOR_ORANGE = "#F57C1F"
COLOR_DARK = "#23292f"
COLOR_GRAY = "#e5e5e5"

# Fonts
FONT_TITLE = QFont("Cascadia Mono", 22, QFont.Weight.Bold)
FONT_TAB = QFont("Archivo", 16, QFont.Weight.Bold)

# Common styling methods
self.create_styled_input(placeholder="Enter text")
self.create_styled_button("Click Me", callback=self.handle_click)
```

## 📊 Logging

### Logging Configuration

```python
from utils.logger import get_logger, log_exceptions

# Get logger
logger = get_logger("my_module")

# Log messages
logger.info("Operation completed successfully")
logger.warning("Something to watch out for")
logger.error("An error occurred", exc_info=True)

# Decorator for automatic exception logging
@log_exceptions("my_module")
def risky_function():
    # This function's exceptions will be automatically logged
    pass
```

### Log Files

- **Main log**: `logs/app.log`
- **Error log**: `logs/app_error.log`
- **Rotation**: 10MB max file size, 5 backup files

## 🧪 Testing

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-qt

# Run tests
pytest tests/

# Run with coverage
pytest --cov=. tests/
```

### Test Structure

```
tests/
├── unit/
│   ├── test_models.py
│   ├── test_services.py
│   └── test_utils.py
├── integration/
│   ├── test_api_client.py
│   └── test_backend_integration.py
└── ui/
    ├── test_pages.py
    └── test_navigation.py
```

## 🚀 Deployment

### Production Setup

1. **Environment Configuration**
   ```bash
   export API_BASE_URL="https://your-backend.com/api/v1"
   export API_KEY="your-api-key"
   export LOG_LEVEL="WARNING"
   export DEBUG="False"
   ```

2. **Build Executable** (optional)
   ```bash
   pip install pyinstaller
   pyinstaller --onefile --windowed main.py
   ```

3. **Docker Deployment** (optional)
   ```dockerfile
   FROM python:3.9-slim
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install -r requirements.txt
   COPY . .
   CMD ["python", "main.py"]
   ```

## 🔧 Troubleshooting

### Remote Connection Issues
- **Administrative Privileges**: Ensure you have admin rights on both local and remote machines
- **Network Connectivity**: Verify network access to target machines
- **Firewall Settings**: Check Windows Firewall settings on target machines
- **PSTools**: Ensure PSTools are properly installed and accessible
- **Credentials**: Verify username/password have sufficient privileges

### Web UI Issues
- **pywebview**: Install with `pip install pywebview`
- **Direct Access**: If webview fails, access file browser directly at `http://[IP]:8080`
- **Port Conflicts**: Ensure port 8080 is available on target machine

### Memory Acquisition Issues
- **winpmem**: Ensure winpmem_mini_x64_rc2.exe is in project root
- **Permissions**: Run application with administrative privileges
- **Antivirus**: Temporarily disable antivirus if it blocks memory acquisition

### General Issues
- **Python Version**: Ensure Python 3.8+ is installed
- **Dependencies**: Reinstall requirements if modules are missing
- **Logs**: Check log files in `logs/` directory for detailed error information

## 🤝 Contributing

### Development Workflow

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/new-feature
   ```
3. **Make changes and test**
4. **Update documentation**
5. **Submit a pull request**

### Code Style

- Follow PEP 8 for Python code
- Use type hints for function parameters and return values
- Add docstrings for all public functions and classes
- Keep functions small and focused
- Use meaningful variable and function names

### Commit Messages

Use conventional commit format:
```
feat: add new case creation functionality
fix: resolve API timeout issue
docs: update API documentation
style: format code according to PEP 8
refactor: extract common UI components
test: add unit tests for data models
```

## 📝 License

[Add your license information here]

## 🆘 Support

For support and questions:
- Create an issue in the repository
- Contact the development team
- Check the documentation

## ⚠️ Legal Notice

**Important**: This application is designed for forensic analysis and should be used in accordance with legal and ethical guidelines. Ensure proper authorization before conducting any forensic investigations. Users are responsible for complying with all applicable laws and regulations in their jurisdiction.

---

## Chapter 4: Implementation Process and Testing

### 4.1 Software Development Platform

#### **Development Environment**
- **Operating system**: Windows 11 (the target platform; registry, SRUM, USB and remote acquisition rely on Windows mechanisms)
- **Language runtime**: Python 3.14 in a project-local virtual environment (`.venv`), created automatically by `run.bat` / `run.ps1`
- **Version control**: Git, hosted on GitHub
- **Test hardware**: Windows 11 laptop with 16 GB RAM and an NVIDIA GeForce RTX 3050 Ti Laptop GPU (4 GB)
- **Target lab**: Windows virtual machines for remote acquisition tests **[fill in: hypervisor and guest versions used]**

#### **Core Technologies**

| Area | Technology | Used for |
|------|-----------|----------|
| User interface | PyQt5 5.15, PyQtWebEngine | Desktop GUI, embedded HTML reports |
| Case storage | JSON files in a folder per case | `info.json`, evidence descriptors, analysis output |
| Memory forensics | Volatility 3 (run as `vol -r json`) | `windows.info`, `pslist`, `cmdline`, `netscan`, `malfind`, `userassist`, `dumpfiles` |
| Registry forensics | regipy | Plugin analysis, hive comparison, transaction logs, header parsing |
| SRUM | dissect.esedb | Parsing the ESE database `SRUDB.dat` in pure Python |
| Browser forensics | Python `sqlite3` (read-only, immutable mode) | Chromium and Firefox databases |
| Reports | mistune, Qt `QPdfWriter` | Markdown to HTML and PDF |
| Threat intelligence | VirusTotal API v3 (`requests`) | File-hash and IP reputation |
| AI narrative | Any OpenAI-compatible chat API (`requests`) | Executive summary, relationships, recommendations |

#### **Forensic Tools Integration**
- **PsExec (Sysinternals)**: remote command execution on the target
- **SMB administrative share (`\\host\C$`)**: copying tools to the target and evidence back
- **WinPmem (`winpmem_mini_x64_rc2.exe`)**: full physical memory acquisition
- **ProcDump**: per-process memory dumps
- **RawCopy**: copying files that Windows keeps locked (registry hives, `SRUDB.dat`, event logs)
- **FileBrowser**: temporary web file browser deployed on the target for manual file selection, protected by a one-time login per session
- **rla.exe**: fallback for applying registry transaction logs

#### **AI Integration**
The report narrative is produced by any service that implements the OpenAI-compatible `/chat/completions` endpoint. The provider is chosen in `.env` with `LLM_API_BASE`, `LLM_MODEL` and `LLM_API_KEY`, so no code change is needed to switch between a cloud service and a local model. The configuration tested for this project is **`gemma4:31b` on Ollama Cloud**. Local execution through Ollama on the investigator's own GPU is also supported, which keeps evidence on the workstation.

The first prototype used llama-index, sentence-transformers and PyTorch for a retrieval pipeline and had an API key written into the source code. That stack no longer installed on current Python versions, prevented the application from starting, and exposed a secret, so it was replaced by the design described in section 4.2.

### 4.2 Code Design

#### **Architecture**

The application is split into three layers. Each layer only depends on the one below it.

```
pages/      PyQt5 user interface: one class per screen, background work in QThread workers
services/   Forensic logic: acquisition, parsing, correlation, reporting (no widgets)
utils/      Paths of bundled tools and case folders, logging, helper processes
```

| Module | Responsibility |
|--------|----------------|
| `pages/main_window.py` | Navigation between screens and the single "current case" shared by all pages |
| `pages/remote_acquisition_page.py` | Connects to a target: reachability check, SMB share, deploys FileBrowser through PsExec |
| `pages/remote_connection_page.py` | Targeted collection, file browser, memory dumps, evidence table |
| `pages/analysis_page.py` | The five analysis views: MEMORY, WEB, SRUM, REGISTRY, USB |
| `pages/report_page.py` | Report generation and export to Markdown, HTML and PDF |
| `services/memory_analyzer.py` | Volatility pipeline, file dumping and hashing, VirusTotal client |
| `services/web_artifact_extractor.py` | Browser artifact extraction and HTML report |
| `services/srum_analyzer.py` | SRUM parsing with ID, SID and Wi-Fi profile resolution |
| `services/registry_analyzer.py` | Hive acquisition, regipy plugins, hive diff, transaction logs, header |
| `services/usb_analyzer.py` | USB history from the live registry or an acquired `SYSTEM` hive, triage rules |
| `services/report_service.py` | Rule-based findings and Markdown report, optional LLM narrative |
| `services/evidence_store.py` | Evidence descriptors with path, size, SHA-256 and timestamp |
| `utils/paths.py` | Absolute locations of every bundled tool and of the case sub-folders |

#### **Key Design Decisions**

**1. Every case is a self-contained folder.** Creating a case builds this structure, and every feature writes its output into it:

```
cases/<number>_<name>/
├── info.json            case number, name, examiner, notes
├── evidence/            evidence_<n>.json descriptors (+ acquired files)
├── memory_analysis/     Volatility JSON, dumped files, VirusTotal results
├── web_artifacts/       one time-stamped folder per extraction
├── registry_analysis/   acquired hives, plugin results, comparisons
├── srum_analysis/       one CSV per SRUM table
├── usb_analysis/        device list and HTML triage report
└── reports/             generated forensic reports
```

**2. Evidence is recorded, not just copied.** Each acquisition or analysis calls `record_evidence()`, which writes a numbered descriptor with the file paths, sizes, SHA-256 hashes and a timestamp. The evidence table and the report appendix are built from these descriptors.

**3. Long operations never block the interface.** Acquisition, analysis, VirusTotal look-ups and report generation run in `QThread` workers that report progress through Qt signals. Each registry operation creates its own analyzer object inside its thread. An earlier version shared one object between threads and connected and disconnected its signals from the worker; PyQt5 then terminated the whole application without an error message (see section 4.3).

**4. External tools run as separate processes.** Volatility is executed as `vol -r json` rather than imported, so a crashing plugin cannot take the GUI down, and its JSON output is parsed and flattened:

```python
def run_plugin(self, plugin: str, extra_args: list[str] | None = None, timeout: int = 3600) -> list:
    command = [self.vol, "-q", "-r", "json", "-f", self.dump_path, plugin, *(extra_args or [])]
    self.progress(f"Running {plugin} ...")
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                            creationflags=NO_WINDOW, timeout=timeout)
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "").strip().splitlines()[-3:]
        raise RuntimeError(f"{plugin} failed (exit {result.returncode}): {' | '.join(tail)}")
    text = result.stdout.strip()
    start = text.find("[")
    if start == -1:
        return []
    return flatten_volatility(json.loads(text[start:]))
```

**5. Facts come from rules; the LLM only writes prose.** `ReportService.build_findings()` correlates malfind regions, the process tree, network connections and VirusTotal results into structured findings, and all tables in the report are rendered from those findings. The LLM receives only the findings as JSON and is asked to return three Markdown text fields. It is instructed never to invent PIDs, hashes or IP addresses. If no key is configured, or the call fails, the rule-based text is used and the report states that the LLM narrative was unavailable.

```python
response = requests.post(
    f"{self.llm_api_base}/chat/completions",
    headers={"Authorization": f"Bearer {self.llm_api_key}", "Content-Type": "application/json"},
    json={
        "model": self.llm_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 1500,
    },
    timeout=config.api.timeout * 3,
)
```

**6. Secrets live outside the code.** API keys are read from a git-ignored `.env` file. Passwords for remote targets are never written to disk; only the IP address, domain and user name of the last connection are remembered. The file browser viewer receives its secrets through environment variables, not its command line.

**7. The remote file browser requires a login.** Each connection creates a new FileBrowser database on the target with a random user name and a random 32-character password. Only the bcrypt hash of the password is sent to the target. The viewer window logs in automatically, so the investigator never types it, and cleanup deletes the database when the window closes.

**8. Evidence databases are opened read-only.** Browser databases are first copied and then opened with SQLite's `mode=ro&immutable=1`, so neither the original nor the working copy is modified.

#### **How Each Analysis Option Is Implemented**

The background, purpose and forensic value of each option are explained in the section "Five Forensic Analysis Options" near the top of this document. This section describes what Anubis actually does.

**1. Memory analysis** (`services/memory_analyzer.py`)
1. The investigator selects a memory image (`.raw`, `.mem`, `.dmp`, `.vmem` and others). Remote full-memory images acquired with WinPmem are stored in the case's `evidence` folder.
2. Six Volatility 3 plugins run in sequence: `windows.info`, `windows.pslist`, `windows.cmdline`, `windows.netscan`, `windows.malfind` and `windows.registry.userassist`. A failing plugin is logged and the pipeline continues.
3. Netscan output is grouped per owning process, and every remote address is classified as public, private or local.
4. A process is marked suspicious when malfind reports an executable and writable region (`PAGE_EXECUTE_READWRITE` or `PAGE_EXECUTE_WRITECOPY`) that contains an MZ header or is private memory.
5. `windows.dumpfiles` extracts the files mapped by each suspicious process, and each file is hashed with MD5 and SHA-256.
6. With a VirusTotal key, the hashes of up to 8 dumped files, and the public IP addresses contacted by suspicious processes, are looked up. Only hashes and addresses are sent; files are never uploaded. The "Check files on VirusTotal" and "Check IPs on VirusTotal" buttons repeat these look-ups for an existing case.
7. Eleven views show the results: VirusTotal files, filtered netscan with IP classification, VirusTotal IPs, malfind with hex dump and disassembly, pslist, netscan, userassist, wininfo, cmdline, dumped files, and public IP strings carved from the dumped files.

**2. Web artifact analysis** (`services/web_artifact_extractor.py`)
- **Sources**: a remote host through the `C$` share, the examiner's own profile, any profile folder, or any Windows user folder (for example an acquired copy).
- **Browsers**: Edge, Chrome, Brave, Opera (Chromium family) and Firefox.
- **Artifacts**: history (500 most recent), downloads, search terms, cookies (metadata only, values are not extracted), saved login sites and user names (passwords are not decrypted), bookmarks.
- On a remote host, running browsers are closed through PsExec first so that their databases are not locked.
- **Output**: an HTML report shown inside the application, a `summary.json` with counts, and the raw database copies.

**3. Registry analysis** (`services/registry_analyzer.py`)
- **Acquire**: copies locked hives of the local machine (`SYSTEM`, `SOFTWARE`, `SAM`, `SECURITY`, `Amcache.hve`, `SRUDB.dat`, and per-user `NTUSER.DAT` and `UsrClass.dat` with their `.LOG1`/`.LOG2` files) with RawCopy. This requires Administrator rights.
- **Analyze**: runs every regipy plugin that matches the hive type and saves the results as JSON.
- **Compare**: lists keys and values that were added, removed or modified between two hives and saves a CSV.
- **Apply transaction logs**: replays `.LOG1`/`.LOG2` into a recovered copy of the hive.
- **Parse header**: shows signature, sequence numbers, timestamps and whether the hive is dirty.

**4. USB analysis** (`services/usb_analyzer.py`)
- **Sources**: the live registry of the examiner's machine, or an acquired `SYSTEM` hive (offline evidence). For a hive, the active control set is read from `Select\Current`.
- **Data per device**: description, device type from the class GUID, serial number, hardware ID, manufacturer, driver, and the first install, last arrival and last removal times from the device property keys.
- **Triage**: storage devices are flagged when they were connected in the last 7 days, have a generic or unknown manufacturer, were removed after their last arrival, or share a serial number with another device ID.
- **Output**: a searchable table, CSV export, and an HTML forensic report stored in the case.

**5. SRUM analysis** (`services/srum_analyzer.py`)
- `SRUDB.dat` is an ESE (Extensible Storage Engine) database, not SQLite. It is parsed with `dissect.esedb`.
- Every table is read, including application resource usage, network data usage, network connectivity, energy usage, push notifications and application timeline. Table GUIDs are translated to readable names.
- Application and user IDs are resolved through `SruDbIdMapTable`. With the `SOFTWARE` hive of the same machine, SIDs are resolved to user names and Wi-Fi profile IDs to network names.
- The live database is locked by Windows, so it is acquired first with RawCopy ("Acquire from this machine") or taken from evidence collected remotely.
- **Output**: one tab per table with search, and one CSV per table in the case.

**Integration and cross-analysis.** The report correlates memory findings: suspicious processes are linked to their parent and child processes, to the public IP addresses they contacted, to the files dumped from them, and to VirusTotal verdicts for those files and addresses. Correlation across the other four options (for example linking a browser download to a USB device) is not automated yet and is listed as future work in Chapter 5.

### 4.3 Verification

Verification answers the question "was the system built correctly?". Each requirement was checked against the implementation and against the tests in section 4.4.

#### **Functional Requirements**

| Requirement | How it was verified | Status |
|-------------|--------------------|--------|
| Create cases and select existing ones | GUI test: case created, all seven sub-folders and `info.json` present, navigation to Resource | ✅ Satisfied |
| Edit or delete cases from the GUI | Not implemented; cases are folders that can be managed in Explorer | ❌ Not implemented |
| Register local evidence | Code review; evidence descriptors created with path and size | ✅ Satisfied |
| Remote connection with clear errors | GUI test: unreachable host reports "not reachable" without hanging | ✅ Error path verified |
| Remote acquisition (targeted locations, files, memory) | Requires a target VM | ⚠️ Not yet tested end-to-end |
| Memory analysis with Volatility 3 | Pipeline verified to fail gracefully on an invalid image; all 11 views verified on the sample case | ⚠️ Not yet run on a real image |
| VirusTotal enrichment | Live look-ups on the sample case (section 4.4) | ✅ Satisfied |
| Web artifact extraction | Live extraction from Chrome and Brave on the test machine | ✅ Satisfied |
| Registry analysis | Header, plugin analysis and comparison tested on `C:\Users\Default\NTUSER.DAT` | ✅ Satisfied |
| Registry acquisition and transaction logs | Requires Administrator rights and dirty hives | ⚠️ Not yet tested |
| USB analysis and triage report | Live scan of 19 devices; report saved in the case | ✅ Satisfied |
| SRUM analysis | Input validation tested; the live database is locked without Administrator rights | ⚠️ Not yet run on a real `SRUDB.dat` |
| Report with LLM narrative and export | GUI test: report generated with `gemma4:31b`; Markdown, HTML and PDF exported | ✅ Satisfied |

#### **Non-Functional Requirements**

| Requirement | Result |
|-------------|--------|
| The interface stays responsive during long work | All long operations run in background threads with progress messages |
| No secrets in the source code | Keys only in the git-ignored `.env`; the API key previously committed was removed from the history |
| Reproducible installation | `run.bat` / `run.ps1` create the virtual environment and install `requirements.txt` |
| Honest reporting | Files that no engine scanned are shown as "Not checked", never as "Clean" |
| Remote file browser not open to the network | Login required; requests without a token, with a wrong password or with FileBrowser's default `admin/admin` are refused (unit tests against the real `filebrowser.exe`) |

#### **Defects Found During Verification**

Testing found and fixed these defects. They are listed because they show what the tests are for.

| Defect | Effect | Fix |
|--------|--------|-----|
| Outdated dependencies (llama-index, PyTorch) imported at start-up | The application could not start | Replaced by a dependency-light report service |
| Shared registry analyzer used from worker threads | Any registry button closed the application silently | One analyzer per worker thread |
| Evidence table loaded only when a case was selected | New evidence was invisible until "Refresh" | Table reloads every time the page is shown |
| Files never scanned shown as "Clean" (0 of 0 engines) | The report, and the LLM, claimed malware was clean | Reported as "Not checked"; summary states that reputation is unknown |
| Evidence descriptor numbering based on file count | An existing descriptor could be overwritten | Next number taken from the highest existing number |
| Tool paths relative to the working directory | Tools not found when started from another folder | All paths resolved in `utils/paths.py` |
| FileBrowser started with `--noauth` | Anyone on the target's network could browse its `C:` drive during a session | Random per-session credentials, login required, automatic login in the viewer |

### 4.4 Validation

Validation answers the question "does the system do what an investigator needs?". It was done with automated tests, an end-to-end GUI test, and a known-infected sample case.

#### **Automated Unit Tests**

The tests run with `python -m unittest discover -v`. All 14 tests pass.

| Test file | What it checks |
|-----------|---------------|
| `tests/test_config.py` | Data, log and case paths are project-relative; the case folder structure is created; the main window fits small and large screens |
| `tests/test_filebrowser_session.py` | Sessions get unique, long passwords and their own database; `--noauth` is never used; cleanup removes the database. Against the real `filebrowser.exe` on 127.0.0.1: no access without login, wrong and default passwords refused, session credentials work |
| `tests/test_virustotal_files.py` | Selection of dumped files for VirusTotal skips JSON, empty files and duplicate hashes, orders by importance and respects the lookup limit; results are saved most-detected first (uses a fake client, no network) |

#### **End-to-End GUI Test**

A scripted run of the real application on a temporary case. Pop-up messages are recorded and closed automatically, and file dialogs receive pre-set answers. All 18 checks passed.

| Step | Check | Result |
|------|-------|--------|
| 1 | Home page shown | Pass |
| 2 | Case created with all folders and `info.json` | Pass |
| 3 | Navigation to Resource after creation | Pass |
| 4 | Connection to an unreachable host fails with a clear message | Pass |
| 5 | Remote connection page shows the host details | Pass |
| 6 | Memory view reads from the case folder | Pass |
| 7 | All 11 memory views render | Pass |
| 8 | Web extraction from this machine saved in the case | Pass |
| 9 | USB scan lists devices | Pass |
| 10 | USB forensic report saved in the case | Pass |
| 11 | Registry header parsed in the background | Pass |
| 12 | SRUM rejects a missing file with a message | Pass |
| 13 | Report generated with the LLM narrative | Pass |
| 14 | Report saved in the case | Pass |
| 15–17 | Export to Markdown, HTML and PDF | Pass |
| 18 | Evidence table lists everything recorded | Pass |

#### **Validation on a Known-Infected Sample Case**

Case `22_ezz` contains Volatility output from a Windows 10 memory image of an infected machine. Anubis was used on it as an investigator would, and its conclusions were checked against VirusTotal.

| Finding by Anubis | Independent check |
|-------------------|-------------------|
| Malfind flags `oneetx.exe` (PID 5896, parent 8844, child 7732): executable and writable region with an MZ header | Dumped image of `oneetx.exe`: **37 of 71** VirusTotal engines detect it, label `trojan.cryp/mars` (Mars Stealer) |
| `oneetx.exe` connected to `77.91.124.20:80` | VirusTotal: **16** engines rate the IP malicious; hosted in Germany |
| Malfind also flags `smartscreen.exe` (PID 7540), without an MZ header | Only small data files were dumped from it, and they were not sent to VirusTotal. Without an MZ header this region is most likely benign generated code: the tool flags it and the analyst must judge |
| Six DLLs and one other image mapped by `oneetx.exe` (for example `winhttp.dll`, `IPHLPAPI.DLL`) | All seven are clean on VirusTotal: legitimate Windows libraries loaded by the malware |

The report produced by Anubis identified the Mars Stealer infection, the malicious process, its network contact and its hash, and recommended isolating the host and blocking the IP address. This matches the independent evidence. The additional flag on `smartscreen.exe` stays visible in the report so the analyst can judge it.

### 4.5 Evaluation

#### **Comparison with Other Systems**

The competitor columns are based on publicly available product information at the time of writing. Check current vendor documentation before citing them.

| Capability | Anubis Forensics GUI | Autopsy | Magnet AXIOM Cyber |
|------------|---------------------|---------|-------------------|
| Licence | Free, source available | Free, open source | Commercial |
| Platform | Windows desktop (PyQt5) | Desktop application (Java) | Windows desktop |
| Main focus | Live and remote triage of Windows hosts | Disk image analysis | Enterprise and remote investigations |
| Remote acquisition | PsExec + SMB, targeted files, memory | Not built in | Agent-based remote collection |
| Memory analysis | Volatility 3 pipeline with malfind triage and file dumping | Through add-on modules | Supported |
| Registry, USB, browser | Yes | Yes (ingest modules) | Yes |
| SRUM | Yes | Not a core feature | Supported |
| Threat intelligence | VirusTotal file and IP look-ups | Hash sets, add-ons | Integrations available |
| AI-written report text | Yes, any OpenAI-compatible model, local or cloud | Not built in | AI assistant features in recent versions |
| Breadth and maturity | Small, focused, unvalidated in court | Mature, widely used | Mature, widely used |

Anubis does not replace either product. Its contribution is a single, small workflow that goes from remote acquisition to a correlated, explained memory report, and a design in which the LLM writes text but never produces the facts.

#### **Qualitative Assessment**

**Strengths**
- One guided workflow: case, acquisition, five analyses, report.
- Every result is stored in the case folder with hashes and timestamps.
- Findings are correlated (process, parent and child, network contact, dumped file, VirusTotal verdict) instead of being listed per tool.
- The LLM is optional and replaceable; it can run fully offline on a local model.
- Failures are reported clearly instead of crashing the application.

**Weaknesses**
- Windows only, single investigator.
- Remote acquisition and real memory images still need full end-to-end testing.
- Correlation is automatic only for memory findings.
- See section 5.3 for security and forensic-soundness limitations.

#### **Quantitative Assessment**

All values were measured on the test machine described in section 4.1 in October 2026. Values that could not be measured are listed as such instead of being estimated.

| Operation | Data | Measured time |
|-----------|------|---------------|
| Unit test suite | 14 tests, including a live FileBrowser | 0.9 s |
| Registry header parsing | Default user `NTUSER.DAT` | < 0.1 s |
| Registry plugin analysis | Default user `NTUSER.DAT`, 13 plugins | 0.1 s |
| Registry comparison | Two copies of the same hive | 0.1 s |
| USB scan, live registry | 19 devices | < 0.1 s |
| Web extraction, this machine | Chrome (385 history, 22 downloads) + Brave (500 history, 200 downloads) | 0.9 s |
| Report with LLM narrative | Sample case, `gemma4:31b` on Ollama Cloud | 2.5–3.3 s |
| VirusTotal file re-check | 8 files (free API: 4 requests per minute) | 109 s |
| Memory pipeline on an invalid image | 1 MB random data, 6 plugins, all fail cleanly | 11.7 s |
| Memory pipeline on a real image | — | Not yet measured |
| Remote acquisition | — | Not yet measured |
| SRUM on a real database | — | Not yet measured |

The VirusTotal look-ups are limited by the free API rate, not by Anubis.

### 4.6 Economic Analysis

Figures below are either real prices or are marked for the team to complete. Earlier versions of this chapter contained invented totals and revenue figures; they were removed.

#### **Economic Impact Assessment**

**Human capital.** The tool targets investigators who must triage Windows machines quickly. Its value is the time saved by not running each tool by hand, not converting outputs, and not writing the first draft of the report. It also lowers the skill needed to read memory analysis results, because suspicious findings are explained in plain language. Using it well still requires forensic training: the tool flags, the analyst decides.

**Financial capital.** All software components used are free:

| Component | Cost | Licence note |
|-----------|------|--------------|
| Python, PyQt5, regipy, dissect.esedb, mistune, requests | Free | PyQt5 is GPL v3: a closed-source commercial product would need a commercial PyQt licence |
| Volatility 3 | Free | Volatility Software License |
| Sysinternals PsExec and ProcDump, WinPmem, RawCopy, FileBrowser | Free | Check each tool's redistribution terms before shipping them inside the project |
| VirusTotal API | Free public key | Rate-limited (4 requests per minute) and not for commercial use; commercial use needs a paid licence |
| Ollama Cloud | Free tier with starter credits | Pro plan $20 per month with $60 of monthly credits; a local model costs nothing |

**Manufactured capital.** A standard Windows laptop is enough; no GPU is needed when a cloud LLM is used. Virtual machines for testing can use free hypervisors.

**Natural capital.** Remote acquisition avoids travel to the target machine. Local LLM use moves energy consumption to the investigator's workstation instead of a data centre.

#### **Project Lifecycle Costs and Benefits**

| Phase | Costs | Benefits |
|-------|-------|----------|
| Prototype (June 2025) | Team time | Working GUI and acquisition proof of concept |
| Repair and completion (September–October 2026) | Team time, API keys on free tiers | Running application, five working analyses, tests |
| Operation | API usage beyond free tiers, maintenance | Faster triage and reporting per case |

#### **Input Requirements and Costs**

| Input | Quantity | Cost |
|-------|----------|------|
| Development effort | **[fill in: team size and hours]** | **[fill in]** |
| Development and test laptop | 1 (existing) | No new purchase |
| Test virtual machines | **[fill in]** | Free hypervisor |
| Software licences | — | $0 |
| VirusTotal and Ollama Cloud | Free tiers | $0 during the project |

#### **Revenue and Who Benefits**

Anubis is an academic project and does not earn revenue. Realistic routes, if it were developed further, are training use in forensics courses, paid support or customisation for small incident-response teams, and a hosted LLM option. Any commercial route must first resolve the licence points in the table above. The beneficiaries are investigators and the organisations they serve, through shorter triage and clearer reports.

#### **Timing Analysis**

The timeline below is taken from the git history. Intermediate commits from the period in between were later consolidated, so only the milestones are shown.

| Date | Milestone |
|------|-----------|
| 18 June 2025 | First commit: PyQt5 GUI, case management, remote acquisition prototype |
| 21 June 2025 | Feature update and first version of the documentation |
| 28 September 2026 | Consolidated rework: application starts again, all five analyses working, rule-based report with LLM narrative, evidence store |
| 5 October 2026 | Registry crash and evidence table fixes, honest VirusTotal status, VirusTotal file re-check, unit tests |

**[fill in: the originally planned schedule, to compare with the actual dates above]**

---

## Chapter 5: Discussion of Results

### 5.1 Summary of Work

#### **Project Accomplishments**
- A working Windows desktop application that guides an investigator from case creation through acquisition and analysis to a report.
- Remote acquisition through PsExec and SMB: targeted artifact collection (including locked files through RawCopy), a remote file browser, full memory images with WinPmem and process dumps with ProcDump.
- Five analysis options: memory (Volatility 3), web, SRUM, registry and USB, each storing its results in the case.
- A memory pipeline that goes beyond running plugins: it selects suspicious processes, dumps and hashes their files, checks them on VirusTotal and correlates processes, network contacts and verdicts.
- A report generator in which rules produce every fact and a replaceable LLM writes only the narrative, with export to Markdown, HTML and PDF.
- Validation on a known-infected memory sample, where Anubis correctly identified Mars Stealer.
- Automated unit tests and a scripted end-to-end GUI test.

#### **Major Learning Outcomes**
- **Memory forensics in practice**: Volatility 3 plugins and their JSON output, what malfind actually detects, and why its results need an analyst (the `smartscreen.exe` false positive).
- **Windows artifacts**: registry hive structure and transaction logs, the ESE format of SRUM, USB device property keys, Chromium and Firefox database schemas.
- **Remote acquisition**: PsExec, administrative shares, locked-file copying, and the footprint these leave on the target.
- **Desktop application engineering**: Qt threading rules, learned through a real crash, and keeping the interface responsive.
- **Responsible use of AI**: separating facts from narrative, giving the model only verified data, and checking its output. The model once repeated "clean" for a file that was never scanned, which led to the "Not checked" fix.
- **Software maintenance**: pinned dependencies that stop installing, secrets committed to git, and the value of tests that find bugs before users do.

#### **Work Remaining**
- End-to-end tests on a Windows virtual machine: remote connection, targeted acquisition, memory dump and Volatility on a real image.
- SRUM and registry acquisition on a machine with Administrator rights.
- Fixture-based tests for the web, registry, USB, SRUM, memory and report services, and a continuous-integration workflow that runs them.
- The other items of the 1.0 release gate in `ROADMAP.md`.

#### **Future Plans for the Software Package**
The plan follows `ROADMAP.md`:
- **1.0**: complete the release gate above and tag a tested version.
- **1.1 Evidence integrity**: an append-only case manifest with source path, acquisition time, size and SHA-256; analyzer warnings shown in the case and the report; a visible run log with tool versions.
- **1.2 Operational hardening**: packaged application with a pinned Python runtime, safe cancellation and cleanup of long operations, documented supported Windows versions and privileges.

### 5.2 Development

#### **New Tools and Techniques Learned**

| Area | Tools and techniques |
|------|---------------------|
| GUI | PyQt5 widgets and style sheets, `QThread` workers and signals, `QWebEngineView`, PDF export with `QPdfWriter` |
| Memory forensics | Volatility 3 CLI and JSON renderer, malfind, dumpfiles, symbol tables |
| Windows artifacts | regipy, dissect.esedb, `winreg`, Chromium and Firefox SQLite schemas |
| Acquisition | PsExec, SMB administrative shares, RawCopy, WinPmem, ProcDump |
| Threat intelligence | VirusTotal API v3: file and IP reports, rate limits |
| AI | OpenAI-compatible chat APIs, prompt design for structured JSON output, local models with Ollama |
| Engineering | Virtual environments, `unittest`, scripted GUI testing, git history clean-up |

#### **Independent Learning and Research**
- Official documentation of Volatility 3, regipy, dissect, Sysinternals, VirusTotal API v3 and Ollama.
- Analysis of a public memory-forensics sample to validate the tool.
- **[fill in: courses, papers, supervisor meetings and other sources the team used]**

### 5.3 Critical Appraisal of Work

#### **Negative Aspects and Limitations**

**Security**
- The remote password is passed to PsExec and `net use` on the command line, so it is visible in the local process list while they run.
- FileBrowser now requires a login, but it is served over plain HTTP on port 8080. Its login and the files viewed travel unencrypted on the network between the investigator and the target.
- When a cloud LLM is used, findings (process names, IP addresses, hashes) leave the investigator's machine.

**Forensic soundness**
- PsExec installs a temporary service on the target, and tools are copied to its disk. This changes the evidence and must be documented in the case.
- Hashes are computed after acquisition on the investigator's side. The tool does not yet hash files on the target before copying, so it cannot prove that the copy matches the source.
- Malfind is a heuristic: on the sample case it also flagged `smartscreen.exe`, which is most likely benign.
- The LLM narrative must be reviewed by the investigator. It is generated from verified findings, but its wording can still be wrong.

**Coverage and testing**
- Remote acquisition, Volatility on a real image, SRUM on a real database and registry acquisition have not been tested end to end.
- Unit tests cover configuration and VirusTotal selection only.
- Correlation across analysis options is not automated outside the memory report.
- Live browsers lock their cookie databases (seen with Brave), so they must be closed before local extraction.

**Platform and scale**
- Windows only, one investigator, one case at a time.
- VirusTotal checks are slow on the free key (4 requests per minute).

#### **Areas for Improvement**
- Hash files on the target before copying and compare them after transfer.
- Serve FileBrowser over HTTPS, or tunnel it through the SMB session, so that its traffic is encrypted.
- Avoid passwords on the command line, for example by using an existing authenticated session.
- Record every action taken on a target in the case log, so that the tool's own footprint is documented.
- Expand automated tests to all services with small, versioned sample inputs.

### 5.4 Proposal for Enhancement or Re-design

The proposals below are limited to what fits the current architecture and a small team.

#### **Architectural Improvements**
- **Case manifest**: one append-only, hashed log per case recording every acquisition, analysis and report, as a basis for chain of custody.
- **Plugin interface for analyzers**: a common `analyze(case, inputs) -> findings` contract, so new artifact types can be added without changing the GUI.
- **Shared findings model**: all analyzers write findings in one format, which makes cross-artifact correlation and a unified report possible.

#### **Feature Enhancements**
- **Unified timeline** across memory, web, USB, registry and SRUM.
- **More artifacts**: Windows event logs (EVTX), Prefetch, Amcache and scheduled tasks, all of which can already be collected by targeted acquisition.
- **YARA scanning** of dumped files and memory images.
- **Report sections for every analysis option**, not only memory.

#### **Technology Improvements**
- **Local LLM as the default**, so that no evidence leaves the workstation, with the cloud as an option.
- **Packaging** into a single installer with a pinned Python runtime.
- **Continuous integration** that installs the dependencies and runs all tests on every change.

#### **Implementation Roadmap**

| Phase | Content |
|-------|---------|
| 1.0 | VM end-to-end tests, fixture tests for all services, CI, tagged release |
| 1.1 | Case manifest, hash-before-copy, warnings in the report, run log |
| 1.2 | Installer, safe cancellation, documented supported systems and privileges |
| 2.0 | Shared findings model, unified timeline, new artifact types, YARA, full multi-artifact report |

Multi-user collaboration, real-time monitoring and cloud deployment are separate products and are not part of this roadmap.

---

**Anubis Forensics GUI** - Advanced Digital Forensics Platform  
*Built with ❤️ for the digital forensics community* 