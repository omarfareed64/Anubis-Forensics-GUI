# Anubis Forensics - Forensic Analysis Platform

A comprehensive forensic analysis platform with a PyQt5-based GUI frontend designed for seamless backend integration.

## 🏗️ Architecture Overview

### Frontend (PyQt5 GUI)
- **Technology**: PyQt5 with custom styling
- **Architecture**: MVC pattern with service layer abstraction
- **State Management**: Centralized through service layer
- **Async Support**: Non-blocking backend operations

### Backend Integration
- **API Client**: Abstracted HTTP communication layer
- **Data Models**: Structured dataclasses for type safety
- **Configuration**: Environment-based configuration management
- **Logging**: Centralized logging with file rotation

## 📁 Project Structure

```
Grad gui/
├── assets/                 # UI assets and images
├── config.py              # Centralized configuration
├── main.py                # Application entry point
├── models/                # Data models and structures
│   ├── __init__.py
│   └── data_models.py     # Core data models
├── pages/                 # PyQt5 UI pages
│   ├── base_page.py       # Base page with common UI elements
│   ├── case_creation_page.py
│   ├── home_page.py
│   ├── main_window.py     # Main application window
│   ├── remote_acquisition_page.py
│   ├── remote_connection_page.py
│   ├── resource_page.py
│   └── splash_screen.py
├── services/              # Business logic and API layer
│   ├── __init__.py
│   └── api_client.py      # Backend API client
├── utils/                 # Utility functions
│   └── logger.py          # Logging utilities
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- pip package manager

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd "Grad gui"
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables** (optional)
   ```bash
   # Create .env file or set environment variables
   export API_BASE_URL="http://localhost:8000/api/v1"
   export DB_HOST="localhost"
   export DB_PORT="5432"
   export LOG_LEVEL="INFO"
   ```

4. **Run the application**
   ```bash
   python main.py
   ```

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_BASE_URL` | `http://localhost:8000/api/v1` | Backend API base URL |
| `API_TIMEOUT` | `30` | API request timeout (seconds) |
| `API_RETRY_ATTEMPTS` | `3` | Number of API retry attempts |
| `API_KEY_HEADER` | `X-API-Key` | API key header name |
| `DB_HOST` | `localhost` | Database host |
| `DB_PORT` | `5432` | Database port |
| `DB_NAME` | `anubis_forensics` | Database name |
| `DB_USER` | `postgres` | Database username |
| `DB_PASSWORD` | `` | Database password |
| `LOG_LEVEL` | `INFO` | Logging level |
| `LOG_FILE` | `logs/app.log` | Log file path |
| `DEBUG` | `False` | Debug mode |
| `DATA_DIR` | `data` | Data directory |
| `TEMP_DIR` | `temp` | Temporary files directory |

### Configuration Usage

```python
from config import config

# Access configuration
api_url = config.api.base_url
db_host = config.database.host
log_level = config.logging.level
```

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

### Data Models

The application uses structured data models for type safety:

```python
from models.data_models import Case, Evidence, Location, CaseStatus, EvidenceType

# Create a case
case = Case(
    number="CASE-001",
    name="Digital Investigation",
    status=CaseStatus.ACTIVE,
    description="Forensic analysis case"
)

# Create evidence
evidence = Evidence(
    name="System Memory Dump",
    type=EvidenceType.MEMORY,
    locations=[
        Location(
            path="/path/to/memory.dmp",
            type="file",
            size=1073741824,  # 1GB
            hash="sha256:abc123..."
        )
    ]
)
```

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

## 🔧 Backend Requirements

### API Response Format

The backend should return responses in this format:

```json
{
  "success": true,
  "data": {
    // Response data here
  },
  "message": "Operation completed successfully",
  "error_code": null,
  "timestamp": "2024-01-01T12:00:00Z",
  "metadata": {
    // Additional metadata
  }
}
```

### Error Response Format

```json
{
  "success": false,
  "data": null,
  "message": "Error description",
  "error_code": "VALIDATION_ERROR",
  "timestamp": "2024-01-01T12:00:00Z",
  "metadata": {
    "field": "field_name",
    "details": "Additional error details"
  }
}
```

### Required Backend Features

1. **Authentication**: API key or token-based authentication
2. **CORS**: Enable cross-origin requests for web integration
3. **File Upload**: Support for large file uploads with progress tracking
4. **Real-time Updates**: WebSocket support for live progress updates
5. **Search & Filtering**: Full-text search and advanced filtering
6. **Pagination**: Support for paginated results
7. **Validation**: Input validation with detailed error messages

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

---

**Note**: This application is designed for forensic analysis and should be used in accordance with legal and ethical guidelines. Ensure proper authorization before conducting any forensic investigations. 