import os
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='[%(asctime)s]: %(message)s:')


project_name="real_interview"

list_of_files=[
    ".github/workflows/.gitkeep",
    f"app/{project_name}/__init__.py",
    f"app/{project_name}/backend/__init__.py",
	f"app/{project_name}/backend/agents/__init__.py",
	f"app/{project_name}/backend/services/__init__.py",
    f"app/{project_name}/backend/utils/__init__.py",
    f"app/{project_name}/backend/nodes/__init__.py",
    f"app/{project_name}/backend/utils/common.py",
    f"app/{project_name}/backend/llm/__init__.py",
    f"app/{project_name}/backend/config/__init__.py",
    f"app/{project_name}/backend/config/configuration.py",
    f"app/{project_name}/backend/state/__init__.py",
    f"app/{project_name}/backend/tools/__init__.py",
    f"app/{project_name}/frontend/__init__.py",
    f"app/{project_name}/data/transcripts/__init__.py",
    f"app/{project_name}/data/resume/__init__.py",
    f"app/{project_name}/data/config/__init__.py",
    f"app/{project_name}/constants/__init__.py",
    "data/.keep",
    "app.py",
    "main.py",
    "Dockerfile",
    "requirements.txt",
    "research.ipynb",
    "schema.yaml",
    "params.yaml",
    ".env"

]

for filepath in list_of_files:
    filepath = Path(filepath)
    filedir, filename = os.path.split(filepath)

    if filedir != "":
        os.makedirs(filedir, exist_ok=True)
        logging.info(f"Creating directory:{filedir} for the file {filename}")

    
    if (not os.path.exists(filepath)) or (os.path.getsize(filepath) == 0):
        with open(filepath,'w') as f:
            pass
            logging.info(f"Creating empty file: {filepath}")


    
    else:
        logging.info(f"{filename}  already exists")