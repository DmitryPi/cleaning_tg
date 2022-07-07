# Cleaning Telegram
> Телеграм бот для клининговой компании

## Startup
    Install virtualenvwrapper
    export WORKON_HOME=$HOME/.virtualenvs
    source /usr/local/bin/virtualenvwrapper.sh
    mkvirtualenv cleaning_tg
    workon cleaning_tg
    pip install -r requirements.txt
    pip install supervisor
    pytest -s
    python main.py

    # Stop supervisord
    supervisorctl stop all
    sudo unlink /tmp/supervisor.sock [or] sudo unlink /var/run/supervisor.sock
    # Start with supervisord daemon
    # In project directory run:
    supervisord


## Composition
    | assets
        service_account.json
        task_jobs.json
        users.json
    | modules
        bot.py
        db.py
        users.py
        utils.py
        | tests
            test_db.py
            test_users.py
            test_utils.py
    .editorconfig
    .gitignore
    config.ini
    db.sqlite3
    main.py
    requirements.txt
    supervisord.conf

## Tests
```sh
pytest (run all tests)
pytest -s (with i/o logging)
pytest modules/tests/test_db.py (run separate testcase)
pytest -v -m slow (run only decorated tag-mark: @pytest.mark.slow)
pytest -v -m "not slow" (inverse - exclude tests decorated with 'slow')
```
