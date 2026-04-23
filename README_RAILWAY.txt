Подготовка к Railway:
1. Загрузите проект в GitHub.
2. В Railway создайте New Project -> Deploy from GitHub Repo.
3. Добавьте Variables:
   BOT_TOKEN=...
   API_ID=...
   API_HASH=...
4. Railway сам запустит команду из Procfile / railway.json: python main.py

Важно:
- Сессии Telegram, сохранённые в файлах, на Railway не будут надёжно храниться без volume.
- Для постоянного хранения sessions/ и data/ лучше подключить Railway Volume.
