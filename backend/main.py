"""
Task Manager API - FastAPI Server
CRUD операции для управления задачами
"""
import json
import os
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from models import Task, TaskCreate, TaskUpdate, Priority, Category

# Инициализация приложения
app = FastAPI(
    title="Task Manager API",
    description="REST API для управления задачами",
    version="1.0.0"
)

# Настройка CORS для работы с Vue фронтендом
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Путь к файлу с данными
DATA_FILE = "tasks.json"


def load_tasks() -> List[dict]:
    """Загрузка задач из JSON файла"""
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_tasks(tasks: List[dict]) -> None:
    """Сохранение задач в JSON файл"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2, default=str)


def get_next_id(tasks: List[dict]) -> int:
    """Получение следующего ID для новой задачи"""
    if not tasks:
        return 1
    return max(task["id"] for task in tasks) + 1


@app.get("/")
async def root():
    """Корневой эндпоинт"""
    return {"message": "Task Manager API", "version": "1.0.0"}


@app.get("/api/tasks", response_model=List[Task])
async def get_tasks(
    status: Optional[str] = Query(None, description="Фильтр по статусу: all, completed, pending"),
    sort_by: Optional[str] = Query(None, description="Сортировка: date, title"),
    sort_order: Optional[str] = Query("asc", description="Порядок сортировки: asc, desc")
):
    """
    Получение списка всех задач с возможностью фильтрации и сортировки
    """
    tasks = load_tasks()
    
    # Фильтрация по статусу
    if status == "completed":
        tasks = [t for t in tasks if t.get("is_completed", False)]
    elif status == "pending":
        tasks = [t for t in tasks if not t.get("is_completed", False)]
    
    # Сортировка
    reverse = sort_order == "desc"
    if sort_by == "title":
        tasks = sorted(tasks, key=lambda x: x.get("title", "").lower(), reverse=reverse)
    elif sort_by == "date":
        tasks = sorted(tasks, key=lambda x: x.get("created_at", ""), reverse=reverse)
    elif sort_by == "priority":
        priority_order = {"high": 0, "medium": 1, "low": 2}
        tasks = sorted(tasks, key=lambda x: priority_order.get(x.get("priority", "medium"), 1), reverse=reverse)
    
    return tasks


@app.get("/api/tasks/{task_id}", response_model=Task)
async def get_task(task_id: int):
    """
    Получение задачи по ID
    """
    tasks = load_tasks()
    for task in tasks:
        if task["id"] == task_id:
            return task
    raise HTTPException(status_code=404, detail=f"Задача с ID {task_id} не найдена")


@app.post("/api/tasks", response_model=Task, status_code=201)
async def create_task(task_data: TaskCreate):
    """
    Создание новой задачи
    """
    tasks = load_tasks()
    
    now = datetime.now().isoformat()
    new_task = {
        "id": get_next_id(tasks),
        "title": task_data.title,
        "description": task_data.description,
        "priority": task_data.priority.value,
        "category": task_data.category.value,
        "is_important": task_data.is_important,
        "is_completed": task_data.is_completed,
        "created_at": now,
        "updated_at": now
    }
    
    tasks.append(new_task)
    save_tasks(tasks)
    
    return new_task


@app.put("/api/tasks/{task_id}", response_model=Task)
async def update_task(task_id: int, task_data: TaskUpdate):
    """
    Обновление существующей задачи
    """
    tasks = load_tasks()
    
    for i, task in enumerate(tasks):
        if task["id"] == task_id:
            # Обновляем только переданные поля
            update_dict = task_data.model_dump(exclude_unset=True)
            
            for key, value in update_dict.items():
                if value is not None:
                    if isinstance(value, (Priority, Category)):
                        task[key] = value.value
                    else:
                        task[key] = value
            
            task["updated_at"] = datetime.now().isoformat()
            tasks[i] = task
            save_tasks(tasks)
            return task
    
    raise HTTPException(status_code=404, detail=f"Задача с ID {task_id} не найдена")


@app.patch("/api/tasks/{task_id}/toggle", response_model=Task)
async def toggle_task_status(task_id: int):
    """
    Переключение статуса выполнения задачи
    """
    tasks = load_tasks()
    
    for i, task in enumerate(tasks):
        if task["id"] == task_id:
            task["is_completed"] = not task.get("is_completed", False)
            task["updated_at"] = datetime.now().isoformat()
            tasks[i] = task
            save_tasks(tasks)
            return task
    
    raise HTTPException(status_code=404, detail=f"Задача с ID {task_id} не найдена")


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: int):
    """
    Удаление задачи по ID
    """
    tasks = load_tasks()
    
    for i, task in enumerate(tasks):
        if task["id"] == task_id:
            deleted_task = tasks.pop(i)
            save_tasks(tasks)
            return {"message": f"Задача '{deleted_task['title']}' успешно удалена", "id": task_id}
    
    raise HTTPException(status_code=404, detail=f"Задача с ID {task_id} не найдена")


@app.get("/api/stats")
async def get_stats():
    """
    Получение статистики по задачам
    """
    tasks = load_tasks()
    
    total = len(tasks)
    completed = sum(1 for t in tasks if t.get("is_completed", False))
    pending = total - completed
    important = sum(1 for t in tasks if t.get("is_important", False))
    
    # Статистика по категориям
    categories = {}
    for task in tasks:
        cat = task.get("category", "other")
        categories[cat] = categories.get(cat, 0) + 1
    
    # Статистика по приоритетам
    priorities = {}
    for task in tasks:
        pri = task.get("priority", "medium")
        priorities[pri] = priorities.get(pri, 0) + 1
    
    return {
        "total": total,
        "completed": completed,
        "pending": pending,
        "important": important,
        "by_category": categories,
        "by_priority": priorities
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
    # uvicorn.run(app, host="127.0.0.1", port=8000) # loopback
