# 📰 Tech Newsletter

This project is a fully automated newsletter system that collects technology news, filters and scores the most relevant articles, creates visual email cards, and sends a polished daily digest to a list of employees or recipients.

It is designed for people who want a simple but powerful way to run a personalized tech newsletter without manually copying articles or formatting emails.

---

## 1. What this system does

The pipeline performs the following steps automatically:

1. Fetches news articles from RSS feeds and configured web sources.
2. Extracts article content and enriches it with full text where possible.
3. Removes poor-quality, duplicate, or irrelevant content.
4. Sends the remaining articles to an LLM for scoring.
5. Selects the highest-quality stories and assigns them to categories.
6. Generates image cards for each article and builds the email body.
7. Sends the newsletter to active recipients by email.
8. Stores information about sent emails and articles in a local database.

This makes it ideal for internal company news, team updates, or a custom daily tech digest.

---

## 2. Features

- Automatic news collection from multiple sources
- Duplicate detection and content filtering
- LLM-based scoring and category assignment
- Image-based newsletter cards for better presentation
- Email sending through SMTP
- Recipient management through a command-line tool
- Scheduling support for automatic daily delivery
- Windows auto-start support for unattended operation
- Local SQLite database for persistence

---

## 3. Requirements

Before using the system, make sure you have:

- Python 3.10 or newer
- Internet access
- A Groq API account and API keys
- SMTP email access (for example Gmail, Outlook, or another SMTP provider)

Install the dependencies:

```bash
pip install -r requirements.txt
```

---

## 4. Project structure

```text
tech_newsletter/
├── card_generator.py
├── manage_employees.py
├── pipeline.py
├── scheduler.py
├── setup_autostart.py
├── requirements.txt
├── README.md
├── image.png
├── config/
│   ├── __init__.py
│   └── settings.py
├── data/
│   └── newsletter.db
├── fetchers/
│   ├── __init__.py
│   ├── rss_fetcher.py
│   ├── scraper.py
│   └── content_enricher.py
├── filters/
│   ├── __init__.py
│   └── preflight.py
├── generated_cards/
├── llm/
│   ├── __init__.py
│   └── scorer.py
├── logs/
├── newsletter/
│   ├── __init__.py
│   ├── builder.py
│   └── sender.py
└── utils/
    ├── __init__.py
    └── database.py
```

### Important folders and files

- [config/settings.py](config/settings.py): main configuration file for schedules, limits, sources, and section labels
- [pipeline.py](pipeline.py): runs the full newsletter flow
- [scheduler.py](scheduler.py): runs the pipeline on a schedule
- [manage_employees.py](manage_employees.py): manages newsletter recipients
- [data/newsletter.db](data/newsletter.db): SQLite database used by the app
- [generated_cards/](generated_cards/): output images generated for each run
- [logs/](logs/): log files for debugging and monitoring

---

## 5. Setup instructions

### Step 1: Create the environment file

Create a file named `.env` in the project root.

Example:

```env
GROQ_API_KEY_1=your_groq_key_here
GROQ_API_KEY_2=your_groq_key_here
GROQ_API_KEY_3=your_groq_key_here

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password_here
SMTP_FROM_EMAIL=your_email@gmail.com
```

### Important notes

- The application reads these values from the `.env` file automatically.
- Never commit your `.env` file to Git.
- If you use Gmail, create an app password instead of using your normal account password.

### Step 2: Install Python dependencies

Run this from the project folder:

```bash
pip install -r requirements.txt
```

### Step 3: Add your first recipient

Before sending a newsletter, add at least one employee or recipient:

```bash
python manage_employees.py add --id EMP001 --name "Your Name" --email your@email.com --dept "IT"
```

This creates a new active recipient in the local database.

### Step 4: Run a test without sending email

This is the safest first run:

```bash
python pipeline.py --no-send
```

This will:

- fetch articles
- filter and score them
- generate cards
- build the email content
- skip the actual email delivery

### Step 5: Run the full pipeline

```bash
python pipeline.py
```

This sends the newsletter to all active recipients.

---

## 6. Employee management

Employee management is handled by [manage_employees.py](manage_employees.py). This tool lets you add, update, activate, deactivate, list, and remove recipients.

All recipient information is stored in the SQLite database at [data/newsletter.db](data/newsletter.db).

### Add a new employee

```bash
python manage_employees.py add --id EMP001 --name "Rahul Sharma" --email rahul@company.com --dept "IT"
```

Parameters:

- `--id`: unique employee ID, for example `EMP001`
- `--name`: full name
- `--email`: email address
- `--dept`: optional department name

New users are added as active by default.

### List all employees

```bash
python manage_employees.py list
```

### List only active employees

```bash
python manage_employees.py list --status active
```

### List only inactive employees

```bash
python manage_employees.py list --status inactive
```

### Deactivate an employee

Use this when you want to stop sending emails to someone without permanently deleting their record:

```bash
python manage_employees.py deactivate --id EMP001
```

### Activate an employee again

```bash
python manage_employees.py activate --id EMP001
```

### Update an employee email address

```bash
python manage_employees.py update-email --id EMP001 --email newemail@company.com
```

### Delete an employee permanently

```bash
python manage_employees.py delete --id EMP001
```

This will ask you to type `YES` to confirm.

### Show only the active email addresses

```bash
python manage_employees.py show-emails
```

### Why employee status matters

- Active employees receive the newsletter.
- Inactive employees keep their record but do not receive emails.
- This is useful when someone leaves the team, changes roles, or temporarily should not receive updates.

---

## 7. Running the pipeline

### Run a dry test

```bash
python pipeline.py --dry-run
```

This checks how many articles are found and shortlisted without sending emails.

### Run without actually sending email

```bash
python pipeline.py --no-send
```

This generates the newsletter assets and prepares the email content without dispatching the message.

### Run normally

```bash
python pipeline.py
```

### Run with debugging output

```bash
python pipeline.py --debug
```

This writes more detailed logs to the logs folder.

---

## 8. Scheduled execution

The scheduler runs the newsletter automatically at the times configured in [config/settings.py](config/settings.py).

### Start the scheduler manually

```bash
python scheduler.py
```

### Run immediately and then continue scheduling

```bash
python scheduler.py --run-now
```

This is useful when you want to test the schedule without waiting for the next planned time.

---

## 9. Auto-start on Windows

The file [setup_autostart.py](setup_autostart.py) creates a Windows Task Scheduler task so the newsletter can run automatically after system boot.

### Install the auto-start task

Run the following command as Administrator:

```bash
python setup_autostart.py
```

### Check task status

```bash
python setup_autostart.py --status
```

### Remove the task

```bash
python setup_autostart.py --remove
```

### Why Administrator is recommended

If you run it as Administrator, the task can start even when no user is logged in. If you do not use Administrator privileges, it may only run while your user account is active.

---

## 10. Configuration guide

Most important settings are located in [config/settings.py](config/settings.py).

### Schedule settings

```python
SCHEDULE_TIMES = ["08:00"]
TIMEZONE = "Asia/Kolkata"
```

You can change the delivery time here.

### Newsletter limits

```python
MAX_ARTICLES_IN_EMAIL = 7
MAX_ARTICLES_TO_LLM = 35
NEWS_LOOKBACK_HOURS = 24
CONTENT_SIMILARITY_THRESHOLD = 0.72
```

These values control:

- how many articles appear in the final email
- how many articles are sent to the LLM
- how far back the system looks for new news
- how strict duplicate detection is

### RSS feeds and web sources

The app uses:

- RSS feeds from [config/settings.py](config/settings.py)
- scrape targets from [config/settings.py](config/settings.py)

You can add or remove sources by editing the lists there.

### Section categories

Sections such as AI, Cloud, Cybersecurity, Startups, and Big Tech are also configured in [config/settings.py](config/settings.py).

These are used to group the final newsletter content.

---

## 11. How the pipeline works

When you run [pipeline.py](pipeline.py), the system follows this flow:

1. Initializes the database.
2. Removes old sent article records.
3. Loads active recipients from the database.
4. Fetches news from RSS and scrape targets.
5. Enriches article content.
6. Runs the preflight filter to remove poor-quality content.
7. Sends the remaining articles to the LLM for scoring.
8. Selects the best articles.
9. Generates newsletter cards and assets.
10. Builds the HTML and plain-text email content.
11. Sends the email to recipients.
12. Stores the run results and sent article history.

This is the complete end-to-end workflow.

---

## 12. LLM scoring

The system uses Groq and the LLM to evaluate each article before it is included.

The LLM returns values such as:

- `KEEP` or `REJECT`
- a score or pass count
- a short summary for the card
- a category label

The top articles are then chosen and placed into the newsletter.

The project uses multiple Groq API keys in rotation so that one key failing or hitting limits does not stop the system completely.

---

## 13. Database and storage

The database file is [data/newsletter.db](data/newsletter.db).

It stores:

- employee and recipient information
- sent article history
- pipeline run logs

This helps prevent duplicate emails and provides a history of newsletter activity.

---

## 14. Output files generated

Each run may generate:

- image cards in [generated_cards/](generated_cards/)
- logs in [logs/](logs/)
- database updates in [data/newsletter.db](data/newsletter.db)

These files are useful for debugging and for reviewing what the system sent.

---

## 15. Troubleshooting

### No emails are sent

Check:

- your SMTP credentials in `.env`
- your recipient list
- the pipeline logs in [logs/](logs/)

### No recipients found

If the system says there are no active recipients, add one with:

```bash
python manage_employees.py add --id EMP001 --name "Name" --email name@example.com
```

### Articles are being rejected by the LLM

Possible causes:

- invalid or rate-limited Groq keys
- network issues
- poor article content quality

Check the logs for more detail.

### Cards are not being generated

Make sure the project dependencies are installed correctly:

```bash
pip install -r requirements.txt
```

### Gmail sending fails

Use an app password instead of your normal Gmail password.

### Auto-start task does not work

Try:

- running [setup_autostart.py](setup_autostart.py) again as Administrator
- checking Windows Task Scheduler for the task named `TechNewsletterScheduler`

---

## 16. Customization ideas

You can customize the system by editing:

- [config/settings.py](config/settings.py) for schedules, sources, and sections
- [card_generator.py](card_generator.py) for card appearance
- [newsletter/builder.py](newsletter/builder.py) for email layout
- [newsletter/sender.py](newsletter/sender.py) for subject and sending behavior

---

## 17. Quick start summary

If you want the fastest way to get started:

```bash
pip install -r requirements.txt
python manage_employees.py add --id EMP001 --name "Your Name" --email your@email.com
python pipeline.py --no-send
python pipeline.py
```

This gives you a working basic setup very quickly.

---

## 18. Notes

- The system is designed to be run repeatedly and automatically.
- It stores important information locally, so it can continue working even without a remote backend.
- For production use, make sure your environment variables, SMTP account, and recipients are set correctly.

If you follow the steps in this README carefully, you should be able to understand the complete flow of the project and manage it confidently.