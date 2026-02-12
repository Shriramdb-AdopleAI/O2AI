## Quick Start

First make sure that the docker service is running in the background

After installation of the requirements in the environment

start the backend Server
with 
   ```bash
    python -B main.py
   ```
Note : Make Sure to have required Environment Variables

In Another Terminal

execute this command if you were in windows to start the redis,
    ```bash
    docker run -d -p 6379:6379 --name redis redis:latest
   ```

if in a linux Environment 
    ```bash
    sudo apt install redis-server
    sudo service redis-server start
       ```

then execute the script appropriately,
    on Windows:
       ```bash
        backend\start_celery_worker_windows.bat
           ```
    on Linux:
       ```bash
        backend\start_celery_worker.sh
            ```
then after the celery workers were active,

**For Bulk Processing (Optional):** If you need the bulk processing feature that checks Azure Blob every 5 minutes, start Celery Beat in a **new Terminal**:

    on Windows:
       ```bash
        cd backend
        celery -A core.celery_app beat --loglevel=info
           ```
    on Linux:
       ```bash
        cd backend
        celery -A core.celery_app beat --loglevel=info
            ```

**Note:** Celery Beat must run in a separate terminal on Windows. Keep both the worker and beat terminals running for bulk processing to work.

In a new Terminal,

install frontend dependencies
   ```bash
    npm install
   ```
start the dev server
    ```bash
    npm run dev
   ```
then the backend and frontend were visible on ,

    http://localhost:5173 - Frontend UI
    http://localhost:8000 - Backend Server