## Graph-Code review

- 2026-08-13 

/home/gongai/projects/digital-duck/graph-code/apps/todo/blueprint/main.graph.yaml


### 1
root-level attributes and blueprint node have overlap, 
TODO: simplify and consolidate


### 2
introduce `settings` node

- settings:
    - key: BACKEND_FASTAPI_PORT
        value: 8000
        comment: |
        FastAPI port
    - key: FRONTEND_VITE_PORT
        value: 5173
        comment: |
        Vite port

then referenced as
- ${{ settings.BACKEND_FASTAPI_PORT }}
- ${{ settings.FRONTEND_VITE_PORT  }}

### 3
where is "tech_profile: python_fastapi" defined?

see `graph-code/spl/tech_profiles.py`

- base profile
- app-specific profile


very messy:
- duplicate entry, e.g., auth_schema

need to be dict(app_name, dict)

### 4
"todo_schema" should be renamed to "db_schema"
in graph-code/apps/todo/blueprint/backend.graph.yaml

### 5
rename "todo_orm_model" to "orm_model"

### 6
add README.md to folder - `$HOME/graph-code/spl` with index of each .spl/.py file

### 7
what are main differences between
- graph-code/spl/build_app.spl
- graph-code/spl/integrate_system.spl


## Claude responded

see `./docs/DEV/BUILD/refactoring-plan-v1.md`