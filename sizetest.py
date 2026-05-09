python -c "
import os
for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in ['.git','__pycache__','.streamlit']]
    for f in files:
        if f.endswith(('.csv','.json')):
            path = os.path.join(root, f)
            size = os.path.getsize(path)
            if size > 100000:
                print(f'{size/1024/1024:.1f}MB  {path}')
"