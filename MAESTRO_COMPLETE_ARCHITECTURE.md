# 🏁 MAESTRO - Automotive Test Automation Framework
## Complete Architectural Specification & Implementation Guide

**Version**: 1.0  
**Date**: 2026-06-12  
**Status**: Enterprise-Ready Architecture (Approved)

---

## 📖 Table of Contents

1. [Quick Start](#quick-start)
2. [Project Overview](#project-overview)
3. [Technology Stack](#technology-stack)
4. [Architecture Overview](#architecture-overview)
5. [Directory Structure](#directory-structure)
6. [Database Schema](#database-schema)
7. [UI Design System](#ui-design-system)
8. [Module Breakdown](#module-breakdown)
9. [Enterprise Features](#enterprise-features)
10. [Execution Model](#execution-model)
11. [Phase 1 Deliverables](#phase-1-deliverables)
12. [Phase 2 Deliverables](#phase-2-deliverables)
13. [Phase 3 Deliverables](#phase-3-deliverables)
14. [CI/CD & Deployment](#cicd--deployment)
15. [Development Strategy](#development-strategy)

---

## 🚀 Quick Start

### Installation & Running Maestro

```bash
# 1. Clone/Extract the project
cd maestro

# 2. Install dependencies
pip install poetry
poetry install

npm install --prefix frontend

# 3. Run the entire application (backend + frontend in one command)
python app.py

# This will:
# ✅ Start FastAPI backend on http://localhost:8000
# ✅ Build and serve React frontend on http://localhost:8000
# ✅ Automatically open browser to http://localhost:8000
# ✅ Show the Maestro dashboard ready to use
```

### Single Command Startup
```bash
# From root directory
python app.py

# That's it! Browser opens automatically with the full Maestro dashboard
```

### System Requirements
- Python 3.11.9 or higher
- Node.js 18+ (for frontend)
- 4GB RAM minimum
- Windows 10+ / Linux / macOS

---

## 📋 Project Overview

### What is Maestro?

**Maestro** is a comprehensive, enterprise-ready **automotive test automation framework** that consolidates multiple testing tools (SSH, ADB, Power Scripts, ETFW, DLT, Windows Camera) into a single, user-friendly browser-based dashboard.

### Key Features

✨ **For Non-Technical Users**
- No coding required - drag-and-drop test design
- Visual 4-column test case builder
- Real-time execution monitoring
- Beautiful, modern dashboard

🔒 **Enterprise-Ready**
- AES-256 credential encryption
- Role-Based Access Control (RBAC)
- Audit logging for compliance
- Multi-project isolation

🚀 **Powerful**
- Advanced execution engine (retry, conditional, looping, parallel)
- Resource locking (prevent device conflicts)
- Hot-swappable plugin system
- Allure-like detailed reports

📊 **Observable**
- Structured JSON logging
- Prometheus metrics
- OpenTelemetry tracing
- Real-time telemetry dashboard

---

## 💻 Technology Stack

### Backend
| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Runtime** | Python 3.11.9 | Stable, performant, automotive-friendly |
| **Web Framework** | FastAPI | Async REST API, auto docs |
| **Database** | SQLite | Zero-setup, single-file, portable |
| **ORM** | SQLAlchemy | Type-safe queries, migrations |
| **Task Queue** | APScheduler | Scheduled test execution |
| **SSH** | Paramiko | SSH command execution, SCP |
| **ADB** | adb-shell | Android device communication |
| **Security** | cryptography | AES-256 encryption |
| **Logging** | structlog + json-logger | Structured JSON logs |
| **Observability** | OpenTelemetry + Prometheus | Metrics & tracing |
| **WebSocket** | FastAPI WebSocket | Real-time execution updates |

### Frontend
| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Framework** | React 18 | Modern UI, component-based |
| **Language** | TypeScript | Type-safe JavaScript |
| **Build Tool** | Vite | Lightning-fast bundling |
| **Styling** | Tailwind CSS | Utility-first, responsive |
| **UI Components** | shadcn/ui | Pre-built, accessible components |
| **Charts** | Recharts | Beautiful data visualization |
| **Tables** | TanStack Table | Multi-select, sorting, filtering |
| **Drag-Drop** | dnd-kit | Smooth drag-and-drop |
| **State** | TanStack Query | Server state management |
| **Forms** | React Hook Form + Zod | Performant form validation |
| **Icons** | Lucide React | Beautiful icon set |
| **Themes** | next-themes | Dark/Light mode |

### DevOps
| Tool | Purpose |
|------|---------|
| **Git** | Version control |
| **GitHub Actions** | CI/CD pipeline |
| **Docker** | Containerization |
| **PyInstaller** | Package backend executable |
| **Poetry** | Python dependency management |
| **npm** | Node package management |

---

## 🏗️ Architecture Overview

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    FRONTEND (React 18 + TS)                      │
│                                                                   │
│  ┌────────────────┬────────────────┬──────────────┬────────────┐ │
│  │  Dashboard     │  Test Case     │  Execution   │  Reports   │ │
│  │  (Colorful     │  Designer      │  Monitor     │  & Config  │ │
│  │   Graphs)      │  (Drag-Drop)   │  (Live)      │  (Allure)  │ │
│  └────────────────┴────────────────┴──────────────┴────────────┘ │
│                                                                   │
│  Dark Mode | Light Mode | Drag-Drop | Multi-Select | Responsive │
└─────────────────────────────────────────────────────────────────┘
              ↕ REST API + WebSocket
              ↕ localhost:8000
┌─────────────────────────────────────────────────────────────────┐
│              BACKEND (FastAPI + Python 3.11.9)                   │
├─────────────────────────────────────────────────────────────────┤
│  ┌─ SECURITY LAYER ────────────────────────────────────────────┐ │
│  │  Secrets Vault (AES-256) | RBAC | Audit Logs | JWT Auth     │ │
│  └─────────────────────────────────────────────────────────────┘ │
│  ┌─ API SERVICE LAYER ─────────────────────────────────────────┐ │
│  │  Projects | Test Cases | Execution | Scheduling | Config    │ │
│  │  Reports | Connections | WebSocket | Plugins               │ │
│  └─────────────────────────────────────────────────────────────┘ │
│  ┌─ PLUGIN SYSTEM ─────────────────────────────────────────────┐ │
│  │  Plugin Manager | Adapters (SSH,ADB,Power,ETFW,DLT,Camera)  │ │
│  │  Health Checks | Capability Discovery | Hot Reload          │ │
│  └─────────────────────────────────────────────────────────────┘ │
│  ┌─ EXECUTION ENGINE ──────────────────────────────────────────┐ │
│  │  Parallel | Serial | Conditional | Looping | Retry Logic    │ │
│  │  Resource Locking | Sandbox Isolation | Error Recovery       │ │
│  └─────────────────────────────────────────────────────────────┘ │
│  ┌─ OBSERVABILITY ─────────────────────────────────────────────┐ │
│  │  Structured JSON Logs | Prometheus Metrics | OpenTelemetry   │ │
│  │  Audit Trails | Correlation IDs | Telemetry Dashboard       │ │
│  └─────────────────────────────────────────────────────────────┘ │
│  ┌─ DATA MANAGEMENT ───────────────────────────────────────────┐ │
│  │  Versioning | Test Data Sets | Artifacts | Backup/Restore   │ │
│  └─────────────────────────────────────────────────────────────┘ │
│  ┌─ DATA LAYER ────────────────────────────────────────────────┐ │
│  │  SQLite Database | File System (logs, reports, artifacts)    │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 Directory Structure

```
maestro/
├── README.md                              # Project overview
├── MAESTRO_COMPLETE_ARCHITECTURE.md       # This file
├── LICENSE
├── app.py                                 # 🚀 Main entry point (starts everything)
├── pyproject.toml                         # Python dependencies (Poetry)
├── poetry.lock
│
├── backend/
│   ├── __init__.py
│   ├── main.py                            # FastAPI app factory
│   ├── config.py                          # Configuration loader
│   ├── database.py                        # SQLAlchemy setup, session manager
│   ├── security.py                        # Auth middleware, CORS
│   │
│   ├── security/                          # Security & RBAC modules
│   │   ├── __init__.py
│   │   ├── rbac.py                        # Role-based access control
│   │   ├── vault.py                       # Secrets encryption/decryption
│   │   ├── audit.py                       # Audit logging
│   │   └── credential_manager.py          # Windows/Linux credential mgmt
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── router.py                      # Main router aggregator
│   │   ├── projects.py                    # Project CRUD
│   │   ├── test_cases.py                  # Test case CRUD
│   │   ├── execution.py                   # Test execution control
│   │   ├── scheduling.py                  # Scheduled test management
│   │   ├── configuration.py               # Device config management
│   │   ├── reports.py                     # Report generation & retrieval
│   │   ├── connections.py                 # Connection testing
│   │   ├── plugins.py                     # Plugin management
│   │   └── websocket.py                   # WebSocket endpoints
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── project.py                     # Project, TestCase, TestStep
│   │   ├── execution.py                   # Execution, ExecutionStep
│   │   ├── device_config.py               # Device configuration
│   │   ├── report.py                      # Report data models
│   │   ├── user.py                        # User & role models
│   │   └── artifact.py                    # Artifact storage models
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── test_executor.py               # Test execution orchestration
│   │   ├── report_generator.py            # Allure-like report generation
│   │   ├── scheduler_service.py           # APScheduler wrapper
│   │   ├── connection_tester.py           # Device connection testing
│   │   ├── plugin_manager.py              # Plugin loading & management
│   │   ├── versioning_service.py          # Test case versioning
│   │   ├── test_data_manager.py           # Test data set management
│   │   ├── project_service.py             # Project isolation
│   │   ├── resource_lock_mgr.py           # Device resource locking
│   │   ├── execution_sandbox.py           # Isolated script execution
│   │   └── observability.py               # Logging, metrics, tracing
│   │
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── base_adapter.py                # Abstract adapter base
│   │   ├── adapter_registry.py            # Plugin discovery
│   │   ├── plugin_manifest.schema         # Schema definition
│   │   │
│   │   ├── ssh_adapter/
│   │   │   ├── __init__.py
│   │   │   ├── adapter.py                 # SSH execution
│   │   │   ├── capabilities.py            # Health checks
│   │   │   └── manifest.json              # Plugin metadata
│   │   │
│   │   ├── adb_adapter/
│   │   │   ├── adapter.py
│   │   │   ├── capabilities.py
│   │   │   └── manifest.json
│   │   │
│   │   ├── power_script_adapter/
│   │   ├── etfw_adapter/
│   │   ├── dlt_adapter/
│   │   ├── windows_camera_adapter/
│   │   ├── serial_console_adapter/
│   │   │
│   │   └── custom_script_loader.py        # User plugin loader
│   │
│   ├── templates/
│   │   ├── adb_templates.json
│   │   ├── ssh_templates.json
│   │   ├── power_templates.json
│   │   ├── etfw_templates.json
│   │   ├── dlt_templates.json
│   │   └── ignition_templates.json
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   └── migrations/                    # Alembic DB migrations
│   │
│   └── utils/
│       ├── __init__.py
│       ├── logger.py                      # Structured logging setup
│       ├── validators.py                  # Input validation
│       └── helpers.py                     # Utility functions
│
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   │
│   ├── public/
│   │   ├── maestro-logo.svg               # Logo (automotive theme)
│   │   └── favicon.ico
│   │
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── index.css
│   │
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── Header.tsx             # Top navigation
│   │   │   │   ├── Sidebar.tsx            # Left sidebar navigation
│   │   │   │   ├── ThemeToggle.tsx        # Dark/Light mode toggle
│   │   │   │   └── MainLayout.tsx
│   │   │   │
│   │   │   ├── dashboard/
│   │   │   │   ├── Dashboard.tsx          # Main dashboard page
│   │   │   │   ├── StatusCard.tsx         # Framework status cards
│   │   │   │   ├── ExecutionGraphs.tsx    # Pie, bar, line charts
│   │   │   │   └── TelemetryDashboard.tsx # Real-time metrics
│   │   │   │
│   │   │   ├── test-cases/
│   │   │   │   ├── TestCaseDesigner.tsx   # 4-column drag-drop
│   │   │   │   ├── ColumnTestType.tsx
│   │   │   │   ├── ColumnScenario.tsx
│   │   │   │   ├── ColumnTestCase.tsx
│   │   │   │   ├── ColumnTestSteps.tsx
│   │   │   │   ├── DraggableStep.tsx      # Step with drag handle
│   │   │   │   └── AvailableActions.tsx
│   │   │   │
│   │   │   ├── execution/
│   │   │   │   ├── ExecutionMonitor.tsx   # Live execution view
│   │   │   │   ├── ExecutionQueue.tsx     # Draggable queue
│   │   │   │   ├── ExecutionControls.tsx
│   │   │   │   ├── StepViewer.tsx
│   │   │   │   ├── LogViewer.tsx
│   │   │   │   └── ExecutionMode.tsx
│   │   │   │
│   │   │   ├── configuration/
│   │   │   │   ├── ConfigPanel.tsx        # Configuration interface
│   │   │   │   ├── DeviceConfig.tsx
│   │   │   │   ├── DeviceList.tsx
│   │   │   │   ├── PathConfig.tsx
│   │   │   │   ├── ConnectionTest.tsx
│   │   │   │   └── ProjectSelector.tsx
│   │   │   │
│   │   │   ├── reports/
│   │   │   │   ├── ReportsPage.tsx        # Reports listing
│   │   │   │   ├── ReportList.tsx
│   │   │   │   ├── ReportDetail.tsx       # Allure-like detail view
│   │   │   │   ├── ReportMetrics.tsx
│   │   │   │   └── BulkActions.tsx
│   │   │   │
│   │   │   └── common/
│   │   │       ├── Dialog.tsx
│   │   │       ├── Modal.tsx
│   │   │       ├── Spinner.tsx
│   │   │       ├── Toast.tsx
│   │   │       └── CodeHighlight.tsx
│   │   │
│   │   ├── pages/
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── TestCasesPage.tsx
│   │   │   ├── ExecutionPage.tsx
│   │   │   ├── ConfigurationPage.tsx
│   │   │   ├── ReportsPage.tsx
│   │   │   └── NotFoundPage.tsx
│   │   │
│   │   ├── hooks/
│   │   │   ├── useApi.ts                  # API calls
│   │   │   ├── useWebSocket.ts            # WebSocket connection
│   │   │   ├── useTheme.ts                # Theme management
│   │   │   └── useLocalStorage.ts         # Local persistence
│   │   │
│   │   ├── services/
│   │   │   ├── api.ts                     # Axios client
│   │   │   └── websocket.ts               # WebSocket client
│   │   │
│   │   ├── types/
│   │   │   ├── index.ts
│   │   │   ├── api.ts
│   │   │   └── domain.ts
│   │   │
│   │   └── utils/
│   │       ├── formatting.ts
│   │       ├── validation.ts
│   │       └── constants.ts
│   │
│   └── tests/
│       ├── unit/
│       └── e2e/
│
├── scripts/
│   ├── build.sh / build.ps1               # Build both backend & frontend
│   ├── run-dev.sh / run-dev.ps1           # Dev environment
│   ├── package.sh / package.ps1           # Package into ZIP
│   ├── docker-build.sh
│   ├── install-service-windows.bat
│   └── install-service-linux.sh
│
├── docker/
│   ├── Dockerfile                         # Backend container
│   ├── Dockerfile.frontend                # Frontend container
│   └── docker-compose.yml                 # Full stack
│
├── .github/
│   └── workflows/
│       ├── ci.yml                         # CI/CD pipeline
│       ├── release.yml                    # Release automation
│       └── docker.yml                     # Docker build
│
├── data/
│   ├── maestro.db                         # SQLite database
│   ├── logs/                              # Execution logs
│   ├── reports/                           # Generated reports
│   └── artifacts/                         # Screenshots, videos
│
└── docs/
    ├── USER_GUIDE.md                      # How to use Maestro
    ├── DEVELOPER_GUIDE.md                 # How to extend
    ├── API_REFERENCE.md                   # API documentation
    └── TUTORIALS.md                       # Video tutorials
```

---

## 🎨 UI Design System

### Color Palette (Dark Mode)
```
Primary:      #6366F1 (Indigo)     - Buttons, highlights
Secondary:    #8B5CF6 (Purple)     - Secondary actions
Success:      #10B981 (Green)      - Passed tests, success states
Warning:      #F59E0B (Amber)      - Warnings, pending states
Error:        #EF4444 (Red)        - Failed tests, errors
Info:         #3B82F6 (Blue)       - Information

Background:   #0F172A (Dark slate) - Main background
Surface:      #1E293B (Slate)      - Card backgrounds
Border:       #334155 (Slate)      - Borders

Text:
  Primary:    #F1F5F9 (Near white) - Main text
  Secondary:  #CBD5E1 (Light gray) - Secondary text
  Muted:      #94A3B8 (Slate)      - Muted text
```

### Color Palette (Light Mode)
```
Primary:      #4F46E5 (Indigo)
Secondary:    #7C3AED (Purple)
Success:      #059669 (Green)
Warning:      #D97706 (Amber)
Error:        #DC2626 (Red)
Info:         #2563EB (Blue)

Background:   #FFFFFF (White)
Surface:      #F8FAFC (Light slate)
Border:       #E2E8F0 (Light border)

Text:
  Primary:    #0F172A (Dark text)
  Secondary:  #475569 (Gray)
  Muted:      #94A3B8 (Light gray)
```

### Typography
- **Headings**: Inter, Bold, 28-36px
- **Body**: Inter, Regular, 14-16px
- **Code**: Fira Code, 12-14px

### Components (shadcn/ui)
- Buttons (solid, outline, ghost variants)
- Cards with shadows
- Tables with sorting & pagination
- Modals with animations
- Dropdowns & popovers
- Toast notifications
- Progress bars & spinners
- Badge components for status
- Date pickers & time inputs

### Animations
- Smooth transitions (200-300ms)
- Slide-in sidebars
- Fade-in modals
- Scale animations on hover
- Loading spinners
- Chart animations

---

## 🧩 Module Breakdown & Responsibilities

### API Layer (app/api/)

**projects.py**
- Create, read, update, delete projects
- List projects for current user
- Set active project

**test_cases.py**
- CRUD operations on test cases
- Import from templates
- Version management
- Clone test cases

**execution.py**
- Start test execution
- Get execution status
- Pause/resume/stop execution
- Stream execution logs via WebSocket

**scheduling.py**
- Create scheduled test runs
- Update schedule (cron expressions)
- List scheduled tests
- Enable/disable schedules

**configuration.py**
- Add/edit/delete device configs
- Test device connectivity
- Validate credentials
- Manage paths for scripts

**reports.py**
- Generate execution reports
- Retrieve report data
- Compare two reports
- Export to HTML/PDF

**plugins.py**
- List available plugins
- Enable/disable plugins
- Install custom plugins
- Get plugin capabilities

**websocket.py**
- Real-time execution updates
- Live log streaming
- Status notifications

### Services Layer (app/services/)

**test_executor.py** (120+ lines)
```python
class TestExecutor:
    async def execute(self, test_case_id, mode='serial')
    async def execute_step(self, step, context)
    async def handle_retry(self, step, attempt)
    async def handle_conditional(self, condition, context)
    async def handle_loop(self, step, iterations)
    def emit_progress(self, execution_id, step_num, status)
```

**report_generator.py**
- Generate Allure-style HTML reports
- Embed screenshots and videos
- Create execution timelines
- Generate metrics and charts
- Export to PDF

**scheduler_service.py**
- Wrap APScheduler
- Persist schedules to DB
- Handle job execution
- Log execution history

**connection_tester.py**
- Test SSH connection
- Test ADB devices
- Check script availability
- Report adapter health

**plugin_manager.py**
- Load plugins dynamically
- Manage plugin lifecycle
- Verify plugin compatibility
- Catalog plugin capabilities

**observability.py**
- Setup structured logging
- Initialize Prometheus metrics
- Configure OpenTelemetry tracing
- Create correlation IDs

### Adapters Layer (app/adapters/)

Each adapter implements `BaseAdapter`:

```python
class BaseAdapter(ABC):
    async def execute(self, action, params, timeout=30)
    async def health_check(self)
    def get_capabilities(self) -> dict
    async def cleanup(self)
```

**SSH Adapter**
- Execute commands
- SCP file transfer
- Mount/remount filesystems
- Capture journal/slog2info logs
- Serial console monitoring

**ADB Adapter**
- List devices
- Execute shell commands
- Push/pull APK and files
- Monitor logcat
- Screen capture

**Power Script Adapter**
- Wrapper for power.ps1/power.py
- Power on/off/cycle
- EDL mode handling

**ETFW Adapter**
- Bus sleep control
- State management

**DLT Adapter**
- Start/stop DLT capture
- Parse DLT logs
- Text pattern matching

**Windows Camera Adapter**
- Screenshot capture
- Video recording
- Frame extraction

**Serial Console Adapter**
- Monitor serial port
- Parse boot logs
- Text matching

---

## 🔐 Enterprise Features

### 1. Secrets Vault
```python
# AES-256 encryption for credentials
vault = SecretsVault()
encrypted = vault.encrypt("password123")
decrypted = vault.decrypt(encrypted)
```

### 2. RBAC (Role-Based Access Control)
```
Admin      → Full system access
Designer   → Create/edit test cases
Executor   → Run tests, view results
Viewer     → Read-only access
Auditor    → View audit logs only
```

### 3. Observability
- **Structured Logs**: JSON format with correlation IDs
- **Prometheus**: Metrics on `/metrics` endpoint
  - `test_executions_total`
  - `test_duration_seconds`
  - `adapter_health_status`
  - `queue_length`
- **OpenTelemetry**: Distributed tracing
- **Audit Logs**: All user actions logged

### 4. Plugin System
```json
// Plugin manifest
{
  "name": "my_adapter",
  "version": "1.0.0",
  "type": "adapter",
  "capabilities": ["execute_command", "health_check"],
  "dependencies": ["paramiko>=2.11.0"],
  "entry_point": "my_adapter:MyAdapter"
}
```

### 5. Advanced Execution
- **Retry Logic**: Configurable retries with backoff
- **Conditionals**: IF/THEN/ELSE branching
- **Loops**: Repeat N times or until condition
- **Parallel Groups**: Run subset in parallel
- **Resource Locking**: Prevent device conflicts
- **Timeout Management**: Per-step overrides
- **Sandbox Isolation**: User scripts isolated

### 6. Test Data Management
- Input datasets (CSV, JSON)
- Parameterized test runs
- Data versioning
- Data injection into steps

### 7. Versioning System
- Full test case history
- Diff viewer
- Rollback capability
- Execution reproducibility

---

## ⚙️ Execution Model

### Serial Execution
```
Step 1 → Wait → Step 2 → Wait → Step 3 → Complete
```

### Parallel Execution
```
Step 1 ↘
        → Execute Concurrently → Complete
Step 2 ↗

Step 3 → Wait
```

### Step-by-Step Execution
```
Step 1 → PAUSE → User clicks "Next" → Step 2 → PAUSE → Step 3 → Complete
```

### Advanced Conditional
```
Step 1 (Execute)
  ↓
Step 2 (IF output contains "error")
  ├─ YES → Step 3 (Remediate)
  └─ NO  → Step 5 (Continue)
  
Step 5 (Final)
```

### Execution with Retry
```
Attempt 1 → FAIL → Wait 2s → Attempt 2 → FAIL → Wait 4s → Attempt 3 → PASS
```

---

## 📦 Database Schema

### Core Tables

```sql
-- Projects (Multi-project isolation)
CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Test Cases
CREATE TABLE test_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    test_type TEXT,  -- adb, ssh, power, dlt, etc.
    scenario TEXT,   -- e.g., "power_on", "adb_push"
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- Test Steps
CREATE TABLE test_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_case_id INTEGER NOT NULL,
    step_number INTEGER NOT NULL,
    action TEXT NOT NULL,  -- e.g., "execute_ssh_command"
    parameters TEXT NOT NULL,  -- JSON
    timeout_seconds INTEGER DEFAULT 30,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (test_case_id) REFERENCES test_cases(id)
);

-- Executions (Test Runs)
CREATE TABLE executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_case_id INTEGER NOT NULL,
    status TEXT DEFAULT 'running',  -- running, passed, failed, error
    execution_mode TEXT DEFAULT 'serial',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    duration_seconds FLOAT,
    FOREIGN KEY (test_case_id) REFERENCES test_cases(id)
);

-- Execution Steps
CREATE TABLE execution_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id INTEGER NOT NULL,
    test_step_id INTEGER NOT NULL,
    status TEXT,  -- passed, failed, skipped
    actual_output TEXT,
    error_message TEXT,
    duration_seconds FLOAT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (execution_id) REFERENCES executions(id),
    FOREIGN KEY (test_step_id) REFERENCES test_steps(id)
);

-- Device Configuration
CREATE TABLE device_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    config_type TEXT NOT NULL,  -- ssh, adb, power, etc.
    label TEXT NOT NULL,
    credentials TEXT NOT NULL,  -- JSON (encrypted)
    is_active BOOLEAN DEFAULT 1,
    last_tested_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- Scheduled Tests
CREATE TABLE scheduled_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_case_id INTEGER NOT NULL,
    cron_expression TEXT NOT NULL,  -- "0 9 * * MON"
    enabled BOOLEAN DEFAULT 1,
    last_run_at TIMESTAMP,
    next_run_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (test_case_id) REFERENCES test_cases(id)
);

-- Test Case Versions (Versioning)
CREATE TABLE test_case_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_case_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    name TEXT NOT NULL,
    steps_json TEXT NOT NULL,  -- JSON snapshot
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_current BOOLEAN DEFAULT 0,
    FOREIGN KEY (test_case_id) REFERENCES test_cases(id)
);

-- Execution Artifacts (Reports, screenshots, videos)
CREATE TABLE execution_artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id INTEGER NOT NULL,
    artifact_type TEXT,  -- screenshot, video, log
    file_path TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    step_number INTEGER,
    FOREIGN KEY (execution_id) REFERENCES executions(id)
);

-- User Roles (RBAC)
CREATE TABLE user_roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    role TEXT NOT NULL,  -- admin, designer, executor, viewer, auditor
    project_id INTEGER,  -- NULL = system-wide
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(username, project_id),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- Audit Logs (Compliance)
CREATE TABLE audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    action TEXT NOT NULL,  -- create, update, delete, run
    resource_type TEXT,  -- test_case, execution, device
    resource_id INTEGER,
    changes TEXT,  -- JSON of changes
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address TEXT
);

-- Plugin Registry
CREATE TABLE plugin_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plugin_name TEXT UNIQUE NOT NULL,
    plugin_type TEXT,  -- adapter, validator, reporter
    version TEXT NOT NULL,
    manifest TEXT,  -- JSON
    enabled BOOLEAN DEFAULT 1,
    installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP
);

-- Credentials Vault (Encrypted)
CREATE TABLE credentials_vault (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_id INTEGER NOT NULL,
    credential_key TEXT NOT NULL,
    encrypted_value BLOB NOT NULL,  -- AES-256
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rotated_at TIMESTAMP,
    FOREIGN KEY (config_id) REFERENCES device_config(id)
);

-- Test Data Sets
CREATE TABLE test_data_sets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    data_type TEXT,  -- csv, json, database
    file_path TEXT,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);
```

---

## 🎭 UI Interaction Patterns

### Test Case Designer
- **Drag to Reorder**: Grab step handle, drag to new position
- **Drag to Add**: Drag from "Available Actions" to add step
- **Right-Click Menu**: Delete, duplicate, edit step
- **Multi-Select**: Shift+Click to select multiple steps
- **Bulk Delete**: Select multiple → Delete button
- **Keyboard**: Delete key, Ctrl+C/V for copy/paste

### Execution Queue
- **Drag to Reorder**: Reorder tests before execution
- **Multi-Select**: Checkboxes for bulk operations
- **Bulk Actions**: Run All, Pause All, Cancel All
- **Delete**: Select → Delete button with confirmation

### Reports Page
- **Table View**: Sortable, filterable columns
- **Multi-Select**: Checkboxes for each report
- **Bulk Delete**: Select reports → Delete Selected
- **Export**: Select → Export to PDF/HTML
- **Comparison**: Select 2 reports → Compare button
- **Search**: Real-time search across reports

### Configuration Panel
- **Tabs**: SSH, ADB, Power, ETFW, DLT, Camera configs
- **Device List**: Draggable to reorder
- **Multi-Select**: Checkboxes for device configs
- **Bulk Delete**: Select devices → Delete with confirmation
- **Test Connection**: Test button for each device
- **Edit Modal**: Click device to edit credentials

### Dashboard
- **Live Metrics**: Real-time execution count, pass/fail rate
- **Charts**: Pie chart (pass/fail), line chart (trend), bar chart (by type)
- **Status Cards**: Framework status, last execution, next scheduled
- **Quick Actions**: Run test, view reports, configure devices
- **Notifications**: Toast for execution events

---

## ✨ Phase 1: MVP Deliverables

### Phase 1 Timeline: 6-8 weeks | 2 developers

### 1.1 Backend Foundation
- ✅ FastAPI app with async support
- ✅ SQLite database with core schema
- ✅ Project management (CRUD)
- ✅ Test case management (CRUD, templates)
- ✅ Test execution engine (serial mode only)
- ✅ Basic RBAC (Admin, Executor, Viewer)
- ✅ Secrets vault (AES-256 encryption)
- ✅ Structured JSON logging
- ✅ WebSocket for live updates

### 1.2 Frontend Foundation
- ✅ React 18 app with TypeScript
- ✅ Dark/Light mode toggle
- ✅ Responsive Tailwind CSS layout
- ✅ Dashboard with basic graphs
- ✅ Test Case Designer (4-column + drag-drop)
- ✅ Execution Monitor (live logs, status)
- ✅ Configuration Panel (add SSH/ADB devices)
- ✅ Reports page (basic listing)
- ✅ Project selector
- ✅ Sidebar navigation

### 1.3 Adapters
- ✅ Base adapter interface
- ✅ SSH adapter (Paramiko)
  - Command execution
  - SCP file transfer
  - Log capture
- ✅ ADB adapter (adb-shell)
  - Device listing
  - Shell commands
  - Push/pull files
- ✅ Power script adapter (wrapper for power.ps1)
  - Power on/off
  - Power cycle

### 1.4 Features
- ✅ Create projects
- ✅ Design test cases (4-column drag-drop interface)
- ✅ Add test steps from templates
- ✅ Configure SSH/ADB devices
- ✅ Test device connections
- ✅ Run tests (serial execution)
- ✅ View live execution logs
- ✅ Generate basic HTML reports
- ✅ View execution history
- ✅ Drag-drop step reordering
- ✅ Multi-select test cases with bulk delete

### 1.5 Testing & Quality
- ✅ Unit tests for adapters
- ✅ Integration tests for executor
- ✅ Frontend component tests
- ✅ Manual testing checklist

### 1.6 Documentation
- ✅ README.md (quick start)
- ✅ ARCHITECTURE.md (design overview)
- ✅ USER_GUIDE.md (basic usage)
- ✅ API documentation (auto-generated)

### 1.7 Deployment
- ✅ ZIP packaging script
- ✅ One-click install (install.bat/install.sh)
- ✅ app.py startup script (launches backend + frontend)
- ✅ Browser auto-open on startup

### Phase 1 Success Criteria
- [ ] Can run `python app.py` and see Maestro dashboard
- [ ] Can create a project
- [ ] Can add SSH/ADB devices
- [ ] Can design a test case with 3+ steps
- [ ] Can execute test and see live logs
- [ ] Can generate and view reports
- [ ] Dark/Light mode works
- [ ] Drag-drop works in designer
- [ ] Multi-select and delete works

---

## 🚀 Phase 2: Rich Features Deliverables

### Phase 2 Timeline: 5-6 weeks | 2-3 developers

### 2.1 Advanced Adapters
- ✅ Power script adapter (advanced: EDL, cycles)
- ✅ ETFW adapter (bus sleep)
- ✅ DLT adapter (start, stop, capture, verify)
- ✅ Serial console adapter
- ✅ Windows camera adapter (screenshot, video)

### 2.2 Plugin System
- ✅ Plugin manager (load, enable, disable)
- ✅ Plugin manifest schema
- ✅ Capability discovery
- ✅ Health checks per adapter
- ✅ Hot reload (without restart)
- ✅ Third-party plugin support

### 2.3 Advanced Execution Engine
- ✅ Parallel execution mode
- ✅ Conditional branching (IF/THEN/ELSE)
- ✅ Looping (repeat N times)
- ✅ Parallel groups (subset parallelism)
- ✅ Retry logic with backoff
- ✅ Resource locking (prevent device conflicts)
- ✅ Execution sandbox (isolated user scripts)
- ✅ Timeout override per step

### 2.4 Versioning & Data Management
- ✅ Test case versions (history, diff, rollback)
- ✅ Test data sets (CSV, JSON input)
- ✅ Parameterized test runs
- ✅ Data versioning
- ✅ Data injection into steps

### 2.5 Observability & Monitoring
- ✅ Prometheus metrics endpoint (`/metrics`)
- ✅ OpenTelemetry tracing
- ✅ Correlation IDs per execution
- ✅ Real-time telemetry dashboard
- ✅ Adapter health monitoring
- ✅ Queue length metrics
- ✅ Performance metrics (CPU, memory)

### 2.6 Scheduling & Automation
- ✅ APScheduler integration
- ✅ Cron expression support
- ✅ Persistent schedules
- ✅ Next run calculation
- ✅ Execution history per schedule
- ✅ Enable/disable schedules

### 2.7 Advanced Reporting
- ✅ Allure-style HTML reports
- ✅ Video embedding
- ✅ Screenshot timeline
- ✅ Step-level attachments
- ✅ PDF export
- ✅ Report comparison (2 executions)
- ✅ Trend analysis over time
- ✅ Execution timeline (synchronized logs/screenshots)

### 2.8 Frontend Enhancements
- ✅ Execution Queue with drag-reorder
- ✅ Multi-select across all pages
- ✅ Bulk delete, export, archive
- ✅ Execution Mode selector (Parallel/Serial/Step-by-step)
- ✅ Live WebSocket streaming (execution updates)
- ✅ Telemetry dashboard
- ✅ Report comparison view
- ✅ Advanced filtering & search

### 2.9 Security & Compliance
- ✅ Enhanced RBAC (5 roles: Admin, Designer, Executor, Viewer, Auditor)
- ✅ Audit logging for all actions
- ✅ Windows Credential Manager integration
- ✅ API token management
- ✅ User session management
- ✅ Credential rotation support

### 2.10 DevOps
- ✅ CI/CD pipeline (GitHub Actions)
- ✅ Automated unit + integration tests
- ✅ Docker build & push
- ✅ Docker Compose (backend + frontend + DB)
- ✅ Release automation
- ✅ Changelog generation

### 2.11 Templates & Pre-built Test Cases
- ✅ SSH templates (10+ scenarios)
- ✅ ADB templates (10+ scenarios)
- ✅ Power templates (on, off, cycle, EDL)
- ✅ DLT templates (start, stop, verify)
- ✅ Ignition templates (off, lock, on, accessory, start)
- ✅ ETFW templates (bus sleep on/off)
- ✅ Camera templates (screenshot, video, analyze)

### Phase 2 Success Criteria
- [ ] Plugin system working (load/enable/disable)
- [ ] Parallel execution runs tests concurrently
- [ ] Conditional branching works
- [ ] Retry logic works with backoff
- [ ] Resource locking prevents device conflicts
- [ ] Allure-style reports with video/screenshots
- [ ] Report comparison shows differences
- [ ] Scheduling works (tests run automatically)
- [ ] Prometheus metrics accessible
- [ ] Docker Compose runs full stack
- [ ] CI/CD pipeline automated

---

## 🏆 Phase 3: Enterprise Polish Deliverables

### Phase 3 Timeline: 3-4 weeks | 1-2 developers

### 3.1 Advanced Features
- ✅ Custom plugin creation templates
- ✅ Third-party plugin marketplace/registry
- ✅ Xray/Jira integration (API-based)
  - Push test results to Xray
  - Pull test cases from Jira
  - Link executions to tickets
- ✅ Multi-tenancy support (future SaaS)
- ✅ Advanced analytics & dashboards
- ✅ Trend analysis over time
- ✅ Performance benchmarking

### 3.2 Deployment Options
- ✅ Windows service installation (NSSM)
- ✅ Linux systemd service installation
- ✅ Auto-start on system boot
- ✅ Kubernetes deployment (Helm charts)
- ✅ Load balancing configuration

### 3.3 Frontend Polish
- ✅ Offline mode (service worker, local caching)
- ✅ Undo/redo in test designer
- ✅ Keyboard shortcuts everywhere
  - Ctrl+S: Save
  - Ctrl+Z: Undo
  - Ctrl+Y: Redo
  - Delete: Delete selected
  - Enter: Execute/Confirm
- ✅ Mobile-responsive design
- ✅ Accessibility (WCAG 2.1 AA)
- ✅ Multi-tab safe editing

### 3.4 Backend Optimization
- ✅ Performance profiling
- ✅ Query optimization (N+1 queries)
- ✅ Caching strategy (Redis optional)
- ✅ Connection pooling
- ✅ Database indexing
- ✅ Async optimization

### 3.5 Testing & Documentation
- ✅ Full unit test coverage (>80%)
- ✅ Full integration test coverage
- ✅ E2E tests with Playwright
- ✅ Load testing (k6)
- ✅ Security testing (OWASP)
- ✅ User guide (comprehensive)
- ✅ Developer guide (extending Maestro)
- ✅ API reference (OpenAPI/Swagger)
- ✅ Video tutorials (5+ videos)
- ✅ Troubleshooting guide

### 3.6 Packaging & Distribution
- ✅ Windows executable (PyInstaller)
- ✅ macOS app bundle
- ✅ Linux AppImage
- ✅ Python package on PyPI
- ✅ Docker Hub images
- ✅ GitHub releases with auto-updates
- ✅ Signed executables

### 3.7 Community & Support
- ✅ GitHub Issues template
- ✅ Pull request template
- ✅ Contributing guide
- ✅ Code of conduct
- ✅ Security policy
- ✅ FAQ section
- ✅ Discord/Slack community

### Phase 3 Success Criteria
- [ ] Offline mode works
- [ ] Undo/redo in designer works
- [ ] Keyboard shortcuts work
- [ ] Windows service installs and auto-starts
- [ ] Kubernetes deployment working
- [ ] Xray integration working
- [ ] >80% test coverage
- [ ] Load test passes (1000 requests/min)
- [ ] Security audit passed
- [ ] Documentation complete and reviewed

---

## 🔄 CI/CD Pipeline

### GitHub Actions Workflows

**ci.yml** - Build & Test
```yaml
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python 3.11
        uses: actions/setup-python@v2
        with:
          python-version: 3.11.9
      - name: Install dependencies
        run: |
          pip install poetry
          poetry install
      - name: Run backend tests
        run: pytest tests/ --cov=backend
      - name: Setup Node
        uses: actions/setup-node@v2
        with:
          node-version: 18
      - name: Install frontend deps
        run: npm install --prefix frontend
      - name: Run frontend tests
        run: npm run test --prefix frontend
      - name: Build frontend
        run: npm run build --prefix frontend
```

**release.yml** - Automated Release
```yaml
on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Create Release
        uses: softprops/action-gh-release@v1
        with:
          files: maestro-*.zip
      - name: Publish to PyPI
        run: poetry publish
```

**docker.yml** - Docker Build & Push
```yaml
on: [push]

jobs:
  docker:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Build and push
        uses: docker/build-push-action@v2
        with:
          push: true
          tags: maestro:latest
```

---

## 📚 Development Strategy

### Local Development Setup

```bash
# 1. Clone repository
git clone https://github.com/yourusername/maestro.git
cd maestro

# 2. Install backend dependencies
pip install poetry
poetry install

# 3. Install frontend dependencies
npm install --prefix frontend

# 4. Create .env file
cat > .env << EOF
DATABASE_URL=sqlite:///./maestro.db
SECRET_KEY=your-secret-key-here
DEBUG=True
ENVIRONMENT=development
EOF

# 5. Run database migrations
alembic upgrade head

# 6. Start development servers (separate terminals)

# Terminal 1 - Backend
cd backend
python main.py

# Terminal 2 - Frontend
cd frontend
npm run dev

# 7. Access Maestro
# Backend: http://localhost:8000
# Frontend: http://localhost:5173
```

### Or Use app.py for Everything
```bash
# Single command startup
python app.py

# This will:
# 1. Start backend on :8000
# 2. Build frontend (if needed)
# 3. Serve frontend from backend
# 4. Open browser automatically
```

### Testing

```bash
# Backend tests
pytest tests/unit/ -v
pytest tests/integration/ -v

# Frontend tests
npm run test --prefix frontend

# E2E tests
npm run test:e2e --prefix frontend

# Coverage
pytest tests/ --cov=backend --cov-report=html
```

### Code Style

```bash
# Backend
black backend/
isort backend/
flake8 backend/

# Frontend
npm run lint --prefix frontend
npm run format --prefix frontend
```

### Git Workflow

```bash
# Feature branch
git checkout -b feature/new-feature
git commit -m "feat: add new feature"
git push origin feature/new-feature

# Create pull request
# Request review
# Merge when approved
```

---

## 📋 Implementation Checklist

### Phase 1 Checklist
- [ ] Project structure created
- [ ] Git repository initialized
- [ ] FastAPI app running
- [ ] React app running
- [ ] SQLite schema created
- [ ] SSH adapter working
- [ ] ADB adapter working
- [ ] Test executor (serial) working
- [ ] Dashboard showing metrics
- [ ] Test case designer UI complete
- [ ] Execution monitor UI complete
- [ ] Configuration panel UI complete
- [ ] Reports page UI complete
- [ ] Dark/Light mode working
- [ ] Drag-drop in designer working
- [ ] Multi-select and delete working
- [ ] app.py launches everything
- [ ] Browser opens automatically
- [ ] Tests passing
- [ ] Documentation complete

### Phase 2 Checklist
- [ ] Plugin system implemented
- [ ] All adapters as plugins
- [ ] Parallel execution working
- [ ] Conditional branching working
- [ ] Looping working
- [ ] Retry logic working
- [ ] Resource locking working
- [ ] Versioning system working
- [ ] Test data management working
- [ ] Scheduling working
- [ ] Prometheus metrics working
- [ ] Allure reports with video/screenshots
- [ ] Report comparison working
- [ ] WebSocket streaming working
- [ ] CI/CD pipeline set up
- [ ] Docker Compose working
- [ ] All templates created
- [ ] Tests passing
- [ ] Documentation complete

### Phase 3 Checklist
- [ ] Custom plugin templates
- [ ] Plugin marketplace
- [ ] Xray/Jira integration
- [ ] Windows service installation
- [ ] Linux systemd installation
- [ ] Kubernetes deployment
- [ ] Offline mode
- [ ] Undo/redo in designer
- [ ] Keyboard shortcuts
- [ ] Performance optimized
- [ ] >80% test coverage
- [ ] Load tests passing
- [ ] Security audit passed
- [ ] All documentation complete
- [ ] Video tutorials complete

---

## 🎨 Modern UI Design Approach

### Design Principles
1. **Minimalist**: Clean interfaces, remove unnecessary elements
2. **Consistent**: Same patterns everywhere
3. **Responsive**: Works on desktop, tablet, mobile
4. **Accessible**: WCAG 2.1 AA compliant
5. **Fast**: Instant feedback, no lag
6. **Beautiful**: Modern colors, smooth animations

### Component Library (shadcn/ui)
```
Buttons         → Solid, outline, ghost, loading states
Cards           → Elevation, hover effects
Tables          → Sortable, selectable, paginated
Modals          → Smooth animations, focus management
Dropdowns       → Keyboard accessible
Badges          → Status indicators
Progress Bars   → Linear and circular
Spinners        → Loading indicators
Toast           → Non-intrusive notifications
Tabs            → Organized content
Sliders         → Range input
Switches        → Toggle controls
```

### Animation Guidelines
- **Duration**: 200-300ms for transitions
- **Easing**: cubic-bezier(0.4, 0, 0.2, 1)
- **Feedback**: Visual confirmation on every action

### Dark Mode Implementation
```tsx
// hooks/useTheme.ts
export function useTheme() {
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  
  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [theme]);
  
  return { theme, setTheme };
}
```

---

## 📝 Key Design Principles

1. **Modularity**: Each adapter independent, easy to add new ones
2. **Reusability**: Test cases can be cloned, steps reused
3. **User-Friendly**: Non-technical users can use without code
4. **Scalability**: SQLite for small teams, PostgreSQL for large
5. **Extensibility**: Plugin system for third-party extensions
6. **Security**: Encryption, RBAC, audit logging
7. **Observability**: Logs, metrics, tracing
8. **Maintainability**: Clean code, comprehensive tests, good docs

---

## 🚀 Final Goal: One-Command Startup

### The Vision
```bash
# Navigate to maestro root
cd /path/to/maestro

# Single command starts everything
python app.py

# Result:
# ✅ Backend starts on http://localhost:8000
# ✅ Frontend built and served
# ✅ Browser opens automatically to dashboard
# ✅ Ready to design and run tests
# ✅ No configuration needed
# ✅ Colorful, modern dashboard loaded
# ✅ All features accessible
```

### What app.py Does
```python
# app.py
import os
import sys
import subprocess
import webbrowser
import time
from pathlib import Path

def main():
    # 1. Check Python version
    assert sys.version_info >= (3, 11, 0), "Python 3.11.9+ required"
    
    # 2. Install dependencies if needed
    if not Path("backend/.venv").exists():
        print("Installing Python dependencies...")
        os.system("poetry install")
    
    # 3. Build frontend if needed
    if not Path("frontend/dist").exists():
        print("Building frontend...")
        os.system("npm run build --prefix frontend")
    
    # 4. Start backend server
    print("Starting Maestro backend...")
    from backend.main import create_app
    app = create_app()
    
    # 5. Serve frontend from backend
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="frontend")
    
    # 6. Run server
    import uvicorn
    
    # 7. Open browser
    time.sleep(2)  # Give server time to start
    webbrowser.open("http://localhost:8000")
    
    # 8. Start server
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
```

---

## 📞 Support & Contact

- **Documentation**: See `/docs` folder
- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions
- **Email**: support@maestro-automation.dev
- **Community**: Discord/Slack channel

---

## 📄 License

Maestro is licensed under the MIT License. See LICENSE file for details.

---

## ✅ Conclusion

This is a **production-grade, enterprise-ready** automotive test automation framework designed for:
- ✨ Non-technical users (drag-drop, no coding)
- 🔒 Enterprise compliance (RBAC, audit logs, encryption)
- 🚀 Advanced testing (parallel, conditional, retry, looping)
- 📊 Observable systems (logs, metrics, tracing)
- 🔌 Extensible architecture (plugins, custom adapters)
- 💻 Modern UX (colorful dashboard, dark mode, responsive)

### Total Implementation Effort
- **Phase 1 (MVP)**: 6-8 weeks
- **Phase 2 (Enterprise)**: 5-6 weeks
- **Phase 3 (Polish)**: 3-4 weeks
- **Total**: ~14-18 weeks for full framework

### Team Requirements
- **Phase 1**: 2 full-stack developers
- **Phase 2**: 2-3 developers (backend + frontend)
- **Phase 3**: 1-2 developers (polish + optimization)

---

## Addendum — capabilities added after v1.0

These extend the architecture above; file references point at the implementation.

### Run Targets (where a test runs)
A **Run Target** is a `DeviceConfig` with `config_type="target"` whose
`settings_json` holds `{kind: local|remote, hostname, domain, username, port,
os, transport}`; the password lives in the encrypted vault. A test case stores a
`default_target_id`; the run can override it. Resolution is in
`backend/security/credential_manager.py::resolve_target`. At dispatch time
(`backend/services/test_executor.py::_dispatch` → `_dispatch_remote`) a remote
target reroutes `system.run_command` / `system.run_file` over SSH to the host,
and injects host + credentials into unbound `ssh.*` steps. Local targets behave
as before. Targets are validated by `connection_tester._probe_target` (SSH login
+ remote `adb` presence; local `adb`/`ffmpeg` presence). RDP is a screen
protocol, so remote command execution uses the SSH/WinRM channel.

### Registered scripts + subcommand palette
`backend/services/script_registry.py` stores bench scripts
(`data/registered_scripts.json`): path, interpreter and a list of subcommands.
`as_templates()` exposes each subcommand as a designer palette item; the
`system.run_registered` adapter action resolves the script at run time and runs
`<interpreter> <path> <subcommand> [args]`. Managed via `/api/scripts` and the
Template Manager page.

### User templates
`backend/services/template_store.py` (`data/user_templates.json`) holds
user-defined palette items, merged into `GET /api/test-cases/templates` under
their chosen group. CRUD via `/api/templates` + the Template Manager page.

### Aggregated suite reports
Member runs share `Execution.suite_run_id`.
`report_generator.generate_suite_report` rolls them into one
`suite_<id>.html/.json`, generated when a suite run finishes and served at
`GET /api/reports/suite/{id}[/html]`.

### Scheduler targets & windows
`ScheduledTest` gains `start_at`/`end_at`; recurring schedules map them to the
APScheduler CronTrigger's `start_date`/`end_date` and auto-disable once the
window elapses (`scheduler_service.build_trigger`). Suite/scenario scheduling
(already resolved at fire time) is now exposed in the UI.

### Authorship & edit locking
`TestCase` gains `modified_by` and `origin` (authored/imported), preserved across
export/import; the designer opens saved cases read-only until explicitly
unlocked.

### Bundled binaries & packaging
`config.BIN_DIR` / `find_bundled_binary` resolve `bin/platform-tools/adb` and
`bin/ffmpeg` across source, wheel (`backend/_bundled/bin`) and frozen modes.
`scripts/build_pypi.py` stages binaries into the wheel; `maestro.spec` +
`installer/maestro.iss` produce a self-contained one-folder Windows installer.

---

**Document Version**: 1.1  
**Last Updated**: 2026-06-18  
**Status**: ✅ Approved & Ready for Implementation
