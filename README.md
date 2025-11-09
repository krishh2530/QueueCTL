# QueueCTL — CLI-Based Background Job Queue Manager

QueueCTL is a command-line interface (CLI) tool for managing background job queues.
It allows you to enqueue jobs, start/stop workers, monitor job status, and manage a Dead Letter Queue (DLQ) for failed jobs that exceed their retry attempts.

The project consists of:

- A **Flask-based backend (server.py)** that manages job execution, retries, and persistence.
- A **CLI tool (queuectl.py)** built using _Click_, which communicates with the backend API.

### Video Demo Link
https://drive.google.com/file/d/1jTvJTJNAJt7RKI2Pm5T8ItLtne1qHiJK/view?usp=drive_link

### Features
- Enqueue and manage jobs
- Start/stop worker threads for job execution
- View job statuses and filter by state
- Retry failed jobs from the Dead Letter Queue (DLQ)
- Update runtime configuration parameters like retry limits
- Persistent job tracking through a MySQL-backed database


```graphql
QueueCTL/
│
├── queuectl.py            # CLI entry point for job queue control
├── server.py              # Flask backend handling queue logic
├── setup.py               # Module installation script
├── requirements.txt       # Python dependencies
├── README.md              # Project documentation
└── (other supporting files like database schema, etc.)
```

### Local Setup Guide

1. Clone the repository
```bash
git clone ...
cd QueueCTL
```

2. Create environment and install dependencies  

create a python virtual environment with all the libraries required for the application.
```bash
python -m venv qctl
qctl\Scripts\activate.bat    #on windows
qctl/Scripts/activate        #on MacOS/linux

pip install -r requirements.txt
```

3. Local Module Installation  

install the QueueCTL application as a local editable module that can be accessed from the command line
```bash
pip install -e .
```

### Database Setup
1. Create a mysql database
```sql
CREATE DATABASE QueueCTL
```

2. Update the database credentials in `server.py`
```python
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://<username>:<password>@localhost/QueueCTL'
```

3. Create 2 tables using the following SQL script
```sql
CREATE TABLE jobs (
    id VARCHAR(255) PRIMARY KEY,
    command TEXT NOT NULL,
    state VARCHAR(50) NOT NULL DEFAULT 'pending',
    attempts INT DEFAULT 0,
    max_retries INT DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
CREATE TABLE dlq (
    id VARCHAR(255) PRIMARY KEY,
    command TEXT NOT NULL,
    state VARCHAR(50) NOT NULL DEFAULT 'failed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
This will create 2 tables `jobs` and `dlq`

### Running The Application
1. Start the backend server
```bash
cd queuectl
python server.py
```
2. Open another terminal (keep the server terminal running)
```bash
queuectl --help
```
This will provide help regarding the commands in the queuectl application

### Command Reference
1. Main commands

| Command | Description |
|----------|-------------|
| `queuectl status` | Display the status of all jobs and workers. |
| `queuectl list --state <state>` | List all jobs, optionally filtered by state (e.g., pending, completed). |
| `queuectl enqueue --id <id> --command "<cmd>"` | Enqueue a new job with a given command. |

#### Example:
```bash
queuectl enqueue --id 1 --command "python test_script.py"
```

2. Worker Commands

| Command | Description |
|----------|-------------|
| `queuectl worker start --count <num>` | Start background workers (default = 2). |
| `queuectl worker stop` | Stops all active workers gracefully |

#### Example
```bash
queuectl worker start --count 3
```

3. Dead Letter Queue

| Command | Description |
|----------|-------------|
| `queuectl dlq list` | List all failed jobs in the DLQ. |
| `queuectl dlq retry <job_id>` | Retry a specific job from the DLQ. |

#### Example
```bash
queuectl dlq retry 14
```

4. Configuration Management

| Command | Description |
|----------|-------------|
| `queuectl config set <param> <new_value>` | Update a specific parameter (max_retries or base_time) |

#### Example
```bash
queuectl config set max_retries 5
queuectl config set base_time 3
```

