# ATS Tracker

Мини-ATS (Applicant Tracking System) для отбора кандидатов в команду AI-стартапа.

## Локальный запуск

```bash
# Установить зависимости
python3 -m pip install -r requirements.txt

# Указать PostgreSQL URL (нужен работающий PG)
export DATABASE_URL="postgresql://user:pass@localhost:5432/ats"

# Запустить приложение
python3 run.py
```

Открыть в браузере: **http://127.0.0.1:8000**

## Учётные записи

| Логин   | Пароль     | Роль        |
|---------|------------|-------------|
| venera  | venera123  | CEO         |
| dmitry  | dmitry123  | Founder     |

## Возможности

- Канбан-доска с drag & drop
- Таблица с поиском, сортировкой и фильтрацией
- Карточка кандидата с хронологической лентой активности
- Заметки с Markdown
- Тестовые задания с оценкой
- Встречи с записью ссылок на видео
- Загрузка файлов (резюме, документы)
- Оценка кандидатов (1-5 звёзд)
- Тёмная / светлая тема
- Адаптивный дизайн

## Деплой на Render.com

### Через render.yaml (рекомендуется)

1. Запушить репозиторий на GitHub
2. Зайти на [render.com](https://render.com) → **New** → **Blueprint**
3. Подключить репозиторий — Render найдёт `render.yaml`
4. Нажать **Apply** — создастся PostgreSQL база (free), веб-сервис и диск для файлов

### Вручную

1. На Render: **New** → **PostgreSQL** → plan **Free**, создать базу
2. **New** → **Web Service** → Docker, подключить репозиторий
3. Environment Variables:
   - `DATABASE_URL` — Internal Connection String из PostgreSQL
   - `ATS_SECRET_KEY` — сгенерировать
   - `ATS_UPLOAD_DIR` = `/data/uploads`
4. Добавить **Disk**: Mount Path `/data`, 1 GB
5. Create Web Service

## Стек

- **Backend**: Python + FastAPI
- **Database**: PostgreSQL (Render Free tier)
- **Frontend**: Vanilla HTML/CSS/JS
- Файлы: `uploads/` (локально) или `/data/uploads` (Render, Persistent Disk)
