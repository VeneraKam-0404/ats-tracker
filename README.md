# ATS Tracker

Мини-ATS (Applicant Tracking System) для отбора кандидатов в команду AI-стартапа.

## Запуск

```bash
# Установить зависимости
python3 -m pip install -r requirements.txt

# Запустить приложение
python3 run.py
```

Открыть в браузере: **http://127.0.0.1:8000**

## Учётные записи

| Логин   | Пароль     | Роль        |
|---------|------------|-------------|
| venera  | venera123  | CEO         |
| alexey  | alexey123  | Founder/CTO |

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

### Вариант 1: Через render.yaml (рекомендуется)

1. Запушить репозиторий на GitHub
2. Зайти на [render.com](https://render.com) → **New** → **Blueprint**
3. Подключить репозиторий — Render автоматически найдёт `render.yaml`
4. Нажать **Apply** — сервис создастся с Persistent Disk для данных

### Вариант 2: Вручную

1. Запушить репозиторий на GitHub
2. На Render: **New** → **Web Service** → подключить репозиторий
3. Настройки:
   - **Runtime**: Docker
   - **Plan**: Starter ($7/мес — нужен для Persistent Disk)
   - **Region**: Frankfurt (или ближайший)
4. Добавить **Disk**:
   - **Mount Path**: `/data`
   - **Size**: 1 GB
5. Добавить **Environment Variables**:
   - `ATS_SECRET_KEY` — любая случайная строка (Render может сгенерировать)
   - `ATS_DATA_DIR` = `/data/db`
   - `ATS_UPLOAD_DIR` = `/data/uploads`
   - `ATS_RELOAD` = `false`
6. Нажать **Create Web Service**

### Важно

- **Persistent Disk обязателен** — без него SQLite база и загруженные файлы
  будут удаляться при каждом редеплое (Render Free tier не поддерживает диски)
- Минимальный план: **Starter** ($7/мес)
- После деплоя приложение будет доступно по адресу `https://ats-tracker.onrender.com`

## Стек

- **Backend**: Python + FastAPI
- **Database**: SQLite
- **Frontend**: Vanilla HTML/CSS/JS
- Файлы хранятся в `uploads/` (локально) или `/data/uploads` (Render)
- База данных: `data/ats.db` (локально) или `/data/db/ats.db` (Render)
