# ZotEvent (CS122A Project)

A command-line program that manages the **ZotEvent** event platform using
Python and a MySQL database. It loads sample data from CSV files and supports
operations like adding admins/venues, reserving and cancelling event slots,
updating events, and running queries (available events, popular event types,
participant schedules, organizer stats, and venue events).

```bash
python3 project.py <function_name> [params...]

# examples
python3 project.py import sample_data
python3 project.py availableEvents 2026-05-01
python3 project.py reserveSlot 501 2 104
```

## Dependencies

- Python 3
- `mysql-connector-python`
- A running MySQL server with a `cs122a` database and a `test` / `password`
  account (these credentials are required by the grader and are hardcoded in
  `project.py`).

```bash
pip3 install mysql-connector-python
```

## Running the unit tests

```bash
python3 -m unittest test_project.py -v
```

The test file includes its own copy of the sample data, so no CSV folder is
needed to run it.

- The pure-logic tests always run.
- The database tests connect to MySQL and are **skipped automatically** if no
  server is reachable. They default to `test` / `password` / `cs122a` on
  `127.0.0.1:3306`, which can be overridden with the `MYSQL_USER`,
  `MYSQL_PASSWORD`, `MYSQL_DATABASE`, `MYSQL_HOST`, and `MYSQL_PORT`
  environment variables.
