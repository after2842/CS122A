"""
CS122A Project - ZotEvent platform
This is the command-line program that the autograder runs.

How to run:
    python3 project.py <function name> [param1] [param2] ...

The program reads command-line arguments, turns them into SQL statements,
runs them on the MySQL server, and prints the result.

Each database function takes the open connection as its
first argument so that it is easy to test.
"""

import sys
import csv
import os
import datetime

import mysql.connector


# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------

def connect():
    """Open a connection to the cs122a database.

    The autograder requires these exact user/password/database values, so I
    hard-code them here just like the project instructions say.
    """
    connection = mysql.connector.connect(
        user="test",
        password="password",
        database="cs122a",
    )
    # I turn autocommit OFF so that I control when a transaction is committed
    # or rolled back. This matters for the insert/update/delete functions.
    connection.autocommit = False
    return connection


# ---------------------------------------------------------------------------
# Small helper functions
# ---------------------------------------------------------------------------

def parse_argument(value):
    """Convert one command-line / CSV string into the value we store.

    Rule 7 of the project says the literal string "NULL" should become the
    Python None type (not the text "NULL"). Everything else stays as a string;
    MySQL will convert "101" to an int, "2024-01-05" to a date, and so on when
    it inserts into a typed column.
    """
    if value == "NULL":
        return None
    return value


def parse_boolean(value):
    """Convert a command-line boolean string into a real Python bool.

    The is_primary parameter is given as text like "true" or "false". I also
    accept "1" / "0" just to be safe. Anything else is treated as False.
    """
    lowered = value.strip().lower()
    if lowered in ("true", "1"):
        return True
    return False


def format_value(value):
    """Turn one value coming back from the database into the text we print.

    - None        -> "NULL"
    - True/False   -> "1" / "0"
    - datetime     -> "YYYY-MM-DD HH:MM:SS"
    - date         -> "YYYY-MM-DD"
    - anything else -> str(value)

    Note: datetime.datetime is a subclass of datetime.date, so I have to check
    datetime first, otherwise a datetime would be printed without its time.
    """
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, datetime.datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, datetime.date):
        return value.strftime("%Y-%m-%d")
    return str(value)


def print_table(rows):
    """Print a result table.

    Each record is printed on its own line and the columns are separated by a
    comma, exactly like the format of the dataset CSV files.
    """
    for row in rows:
        formatted_cells = [format_value(cell) for cell in row]
        print(",".join(formatted_cells))


# ---------------------------------------------------------------------------
# Schema definition (used by the import function)
# ---------------------------------------------------------------------------

# The order tables are created in. Parent tables come before child tables so
# that the foreign keys always point at something that already exists.
# I also use this same order (forward) to insert the CSV rows, and the reverse
# of this order to drop the tables.
CREATE_ORDER = [
    "User",
    "Organizer",
    "Participant",
    "Administrator",
    "Venue",
    "OnCampus",
    "OffCampus",
    "Event",
    "Slot",
    "Hosting",
    "Approval",
]

# The CREATE TABLE statement for each table.
# I wrap the table names and the columns "type"/"date" in backticks because
# those are reserved words in MySQL.
CREATE_STATEMENTS = {
    "User": (
        "CREATE TABLE `User` ("
        "    uid INT NOT NULL,"
        "    email VARCHAR(255),"
        "    username VARCHAR(255),"
        "    joined DATE,"
        "    PRIMARY KEY (uid)"
        ")"
    ),
    "Organizer": (
        "CREATE TABLE `Organizer` ("
        "    uid INT NOT NULL,"
        "    department VARCHAR(255),"
        "    experience INT,"
        "    PRIMARY KEY (uid),"
        "    FOREIGN KEY (uid) REFERENCES `User`(uid) ON DELETE CASCADE"
        ")"
    ),
    "Participant": (
        "CREATE TABLE `Participant` ("
        "    uid INT NOT NULL,"
        "    `type` VARCHAR(255),"
        "    PRIMARY KEY (uid),"
        "    FOREIGN KEY (uid) REFERENCES `User`(uid) ON DELETE CASCADE"
        ")"
    ),
    "Administrator": (
        "CREATE TABLE `Administrator` ("
        "    uid INT NOT NULL,"
        "    firstname VARCHAR(255),"
        "    lastname VARCHAR(255),"
        "    PRIMARY KEY (uid),"
        "    FOREIGN KEY (uid) REFERENCES `User`(uid) ON DELETE CASCADE"
        ")"
    ),
    "Venue": (
        "CREATE TABLE `Venue` ("
        "    vid INT NOT NULL,"
        "    street VARCHAR(255),"
        "    city VARCHAR(255),"
        "    state VARCHAR(255),"
        "    zip VARCHAR(20),"
        "    PRIMARY KEY (vid)"
        ")"
    ),
    "OnCampus": (
        "CREATE TABLE `OnCampus` ("
        "    vid INT NOT NULL,"
        "    code VARCHAR(255),"
        "    PRIMARY KEY (vid),"
        "    FOREIGN KEY (vid) REFERENCES `Venue`(vid) ON DELETE CASCADE"
        ")"
    ),
    "OffCampus": (
        "CREATE TABLE `OffCampus` ("
        "    vid INT NOT NULL,"
        "    distance INT,"
        "    PRIMARY KEY (vid),"
        "    FOREIGN KEY (vid) REFERENCES `Venue`(vid) ON DELETE CASCADE"
        ")"
    ),
    "Event": (
        "CREATE TABLE `Event` ("
        "    eid INT NOT NULL,"
        "    uid INT,"
        "    title VARCHAR(255),"
        "    `type` VARCHAR(255),"
        "    `date` DATETIME,"
        "    PRIMARY KEY (eid),"
        "    FOREIGN KEY (uid) REFERENCES `Organizer`(uid) ON DELETE CASCADE"
        ")"
    ),
    "Slot": (
        "CREATE TABLE `Slot` ("
        "    eid INT NOT NULL,"
        "    snum INT NOT NULL,"
        "    is_reserved BOOLEAN,"
        "    uid INT,"
        "    PRIMARY KEY (eid, snum),"
        "    FOREIGN KEY (eid) REFERENCES `Event`(eid) ON DELETE CASCADE,"
        "    FOREIGN KEY (uid) REFERENCES `Participant`(uid) ON DELETE SET NULL"
        ")"
    ),
    "Hosting": (
        "CREATE TABLE `Hosting` ("
        "    eid INT NOT NULL,"
        "    vid INT NOT NULL,"
        "    is_primary BOOLEAN,"
        "    PRIMARY KEY (eid, vid),"
        "    FOREIGN KEY (eid) REFERENCES `Event`(eid) ON DELETE CASCADE,"
        "    FOREIGN KEY (vid) REFERENCES `Venue`(vid) ON DELETE CASCADE"
        ")"
    ),
    "Approval": (
        "CREATE TABLE `Approval` ("
        "    uid INT NOT NULL,"
        "    vid INT NOT NULL,"
        "    valid_from DATE,"
        "    valid_until DATE,"
        "    PRIMARY KEY (uid, vid),"
        "    FOREIGN KEY (uid) REFERENCES `Administrator`(uid) ON DELETE CASCADE,"
        "    FOREIGN KEY (vid) REFERENCES `OffCampus`(vid) ON DELETE CASCADE"
        ")"
    ),
}

# The column names of each table, in the same order they appear in the CSV
# files (which follows the DDL attribute order). I use this to build the
# INSERT statements during import.
TABLE_COLUMNS = {
    "User": ["uid", "email", "username", "joined"],
    "Organizer": ["uid", "department", "experience"],
    "Participant": ["uid", "type"],
    "Administrator": ["uid", "firstname", "lastname"],
    "Venue": ["vid", "street", "city", "state", "zip"],
    "OnCampus": ["vid", "code"],
    "OffCampus": ["vid", "distance"],
    "Event": ["eid", "uid", "title", "type", "date"],
    "Slot": ["eid", "snum", "is_reserved", "uid"],
    "Hosting": ["eid", "vid", "is_primary"],
    "Approval": ["uid", "vid", "valid_from", "valid_until"],
}


def build_insert_statement(table_name, columns):
    """Build a parameterized INSERT statement for one table.

    I wrap every column name in backticks so reserved words like `type` and
    `date` are safe, and I use %s placeholders so mysql.connector handles the
    values safely.

    Example result:
        INSERT INTO `User` (`uid`, `email`, `username`, `joined`)
        VALUES (%s, %s, %s, %s)
    """
    quoted_columns = ["`" + column + "`" for column in columns]
    placeholders = ["%s"] * len(columns)
    statement = (
        "INSERT INTO `" + table_name + "` ("
        + ", ".join(quoted_columns)
        + ") VALUES ("
        + ", ".join(placeholders)
        + ")"
    )
    return statement


# ---------------------------------------------------------------------------
# Function 1: import
# ---------------------------------------------------------------------------

def import_data(connection, folder_name):
    """Drop the old tables, create fresh tables, then load every CSV file.

    Returns True if everything worked, False if something went wrong.
    """
    cursor = connection.cursor()
    try:
        # Step 1: drop the existing tables.
        # I drop in the REVERSE of the create order so that child tables are
        # removed before the parent tables they reference.
        for table_name in reversed(CREATE_ORDER):
            cursor.execute("DROP TABLE IF EXISTS `" + table_name + "`")

        # Step 2: create the tables in the normal (parent-first) order.
        for table_name in CREATE_ORDER:
            cursor.execute(CREATE_STATEMENTS[table_name])

        # Step 3: read each CSV file and insert its rows.
        for table_name in CREATE_ORDER:
            columns = TABLE_COLUMNS[table_name]
            insert_statement = build_insert_statement(table_name, columns)

            file_path = os.path.join(folder_name, table_name + ".csv")
            with open(file_path, "r", newline="") as csv_file:
                reader = csv.reader(csv_file)
                for raw_row in reader:
                    # Skip blank lines if there are any.
                    if len(raw_row) == 0:
                        continue
                    # Convert the literal "NULL" cells into Python None.
                    values = [parse_argument(cell) for cell in raw_row]
                    cursor.execute(insert_statement, values)

        # All inserts worked, so commit them.
        connection.commit()
        return True
    except Exception:
        # Something failed, undo any inserts from this transaction.
        connection.rollback()
        return False
    finally:
        cursor.close()


# ---------------------------------------------------------------------------
# Function 2: insertAdmin
# ---------------------------------------------------------------------------

def insert_admin(connection, uid, email, username, joined, firstname, lastname):
    """Insert one new User row and one new Administrator row (same uid).

    If the uid already exists, the User insert fails on the primary key, the
    error is caught, and we return False.
    """
    cursor = connection.cursor()
    try:
        cursor.execute(
            "INSERT INTO `User` (`uid`, `email`, `username`, `joined`) "
            "VALUES (%s, %s, %s, %s)",
            (uid, email, username, joined),
        )
        cursor.execute(
            "INSERT INTO `Administrator` (`uid`, `firstname`, `lastname`) "
            "VALUES (%s, %s, %s)",
            (uid, firstname, lastname),
        )
        connection.commit()
        return True
    except Exception:
        connection.rollback()
        return False
    finally:
        cursor.close()


# ---------------------------------------------------------------------------
# Function 3: addVenue
# ---------------------------------------------------------------------------

def add_venue(connection, eid, vid, is_primary):
    """Add a venue to an event by inserting into the Hosting table.

    If is_primary is True, the event is only allowed to have ONE primary
    venue, so I first check whether the event already has a primary venue. If
    it does, I return False without inserting anything.

    A duplicate (eid, vid) pair fails on the primary key and returns False.
    """
    cursor = connection.cursor()
    try:
        # If this venue is meant to be primary, make sure the event does not
        # already have another primary venue.
        if is_primary:
            cursor.execute(
                "SELECT 1 FROM `Hosting` WHERE eid = %s AND is_primary = 1",
                (eid,),
            )
            existing_primary = cursor.fetchone()
            if existing_primary is not None:
                # The event already has a primary venue -> not allowed.
                connection.rollback()
                return False

        # Insert the new hosting record.
        cursor.execute(
            "INSERT INTO `Hosting` (`eid`, `vid`, `is_primary`) "
            "VALUES (%s, %s, %s)",
            (eid, vid, is_primary),
        )
        connection.commit()
        return True
    except Exception:
        connection.rollback()
        return False
    finally:
        cursor.close()


# ---------------------------------------------------------------------------
# Function 4: reserveSlot
# ---------------------------------------------------------------------------

def reserveSlot(eid: int, snum: int, uid: int):
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()

        check_query = """
            SELECT is_reserved 
            FROM Slot 
            WHERE eid = %s AND snum = %s
        """
        cursor.execute(check_query, (eid, snum))
        result = cursor.fetchone()

        if not result or result[0] == 1:
            print("Fail")
            return
        update_query = """
            UPDATE Slot 
            SET is_reserved = 1, uid = %s 
            WHERE eid = %s AND snum = %s
        """
        cursor.execute(update_query, (uid, eid, snum))
        connection.commit()
        
        print("Success")

    except Error as e:
        if connection:
            connection.rollback()
        print("Fail")
    finally:
        if cursor: cursor.close()
        if connection: connection.close()


# ---------------------------------------------------------------------------
# Function 5: cancelReservation
# ---------------------------------------------------------------------------

def cancelReservation(eid: int, snum: int, uid: int):
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()

        check_query = """
            SELECT is_reserved 
            FROM Slot 
            WHERE eid = %s AND snum = %s AND uid = %s
        """
        cursor.execute(check_query, (eid, snum, uid))
        result = cursor.fetchone()

        if not result or result[0] == 0:
            print("Fail")
            return

        update_query = """
            UPDATE Slot 
            SET is_reserved = 0, uid = NULL 
            WHERE eid = %s AND snum = %s AND uid = %s
        """
        cursor.execute(update_query, (eid, snum, uid))
        connection.commit()
        
        print("Success")

    except Error as e:
        if connection:
            connection.rollback()
        print("Fail")
    finally:
        if cursor: cursor.close()
        if connection: connection.close()


# ---------------------------------------------------------------------------
# Function 6: updateEvent
# ---------------------------------------------------------------------------

def updateEvent(eid: int, title: str, datetime_str: str):
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()

        update_query = """
            UPDATE Event 
            SET title = %s, date = %s 
            WHERE eid = %s
        """
        cursor.execute(update_query, (title, datetime_str, eid))
        connection.commit()
        
        if cursor.rowcount > 0:
            print("Success")
        else:
            print("Fail")

    except Error as e:
        if connection:
            connection.rollback()
        print("Fail")
    finally:
        if cursor: cursor.close()
        if connection: connection.close()


# ---------------------------------------------------------------------------
# Function 7: deleteOrganizer
# ---------------------------------------------------------------------------

def delete_organizer(connection, uid):
    """Delete an organizer.

    Because of ON DELETE CASCADE, deleting the organizer also deletes their
    events, and deleting those events also deletes the related Slot and
    Hosting rows. Returns True if an organizer was actually deleted.
    """
    cursor = connection.cursor()
    try:
        cursor.execute("DELETE FROM `Organizer` WHERE uid = %s", (uid,))
        if cursor.rowcount >= 1:
            connection.commit()
            return True
        else:
            connection.rollback()
            return False
    except Exception:
        connection.rollback()
        return False
    finally:
        cursor.close()


# ---------------------------------------------------------------------------
# Function 8: availableEvents
# ---------------------------------------------------------------------------

def available_events(connection, date_value):
    """List future events that still have at least one unreserved slot.

    For each such event I also count how many slots are still available.
    "Future" means the event datetime is after the given date (the date is
    treated as midnight of that day). Sorted by datetime, then event id.
    Returns a list of rows.
    """
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT e.eid, e.title, e.`type`, e.`date`, "
            "       COUNT(*) AS availableSlots "
            "FROM `Event` e "
            "JOIN `Slot` s ON e.eid = s.eid "
            "WHERE e.`date` > %s AND s.is_reserved = 0 "
            "GROUP BY e.eid, e.title, e.`type`, e.`date` "
            "ORDER BY e.`date` ASC, e.eid ASC",
            (date_value,),
        )
        rows = cursor.fetchall()
        return rows
    except Exception:
        return []
    finally:
        cursor.close()


# ---------------------------------------------------------------------------
# Function 9: popularEventTypes
# ---------------------------------------------------------------------------

def popular_event_types(connection, n):
    """For each event type, count the total reserved slots across all events.

    Only return event types whose reserved count is at least N. I use a LEFT
    JOIN so that a type still shows up (with a count) even if it has events
    with no slots, and I CAST the SUM to a signed integer so it prints as a
    plain number. Sorted by reserved count descending, then type ascending.
    """
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT e.`type`, "
            "       CAST(SUM(CASE WHEN s.is_reserved = 1 THEN 1 ELSE 0 END) "
            "            AS SIGNED) AS reservedCount "
            "FROM `Event` e "
            "LEFT JOIN `Slot` s ON e.eid = s.eid "
            "GROUP BY e.`type` "
            "HAVING reservedCount >= %s "
            "ORDER BY reservedCount DESC, e.`type` ASC",
            (n,),
        )
        rows = cursor.fetchall()
        return rows
    except Exception:
        return []
    finally:
        cursor.close()


# ---------------------------------------------------------------------------
# Function 10: participantSchedule
# ---------------------------------------------------------------------------

def participant_schedule(connection, uid):
    """List every event the participant has reserved a slot for.

    Each row also includes the slot number and the primary venue information
    (if the event has a primary venue). If there is no primary venue, the
    venue columns come back as NULL. Sorted by event datetime ascending.
    """
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT e.eid, e.title, e.`type`, e.`date`, s.snum, "
            "       v.vid, v.street, v.city, v.state, v.zip "
            "FROM `Slot` s "
            "JOIN `Event` e ON s.eid = e.eid "
            "LEFT JOIN `Hosting` h ON e.eid = h.eid AND h.is_primary = 1 "
            "LEFT JOIN `Venue` v ON h.vid = v.vid "
            "WHERE s.uid = %s AND s.is_reserved = 1 "
            "ORDER BY e.`date` ASC",
            (uid,),
        )
        rows = cursor.fetchall()
        return rows
    except Exception:
        return []
    finally:
        cursor.close()


# ---------------------------------------------------------------------------
# Function 11: organizerStats
# ---------------------------------------------------------------------------

def organizer_stats(connection, n):
    """List organizers who have created at least N events.

    I use a LEFT JOIN to Event so an organizer with zero events still gets a
    count of 0 (they just won't pass the HAVING unless N is 0). Sorted by event
    count descending, then organizer uid ascending.
    """
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT o.uid, u.username, o.department, "
            "       COUNT(ev.eid) AS eventCount "
            "FROM `Organizer` o "
            "JOIN `User` u ON o.uid = u.uid "
            "LEFT JOIN `Event` ev ON o.uid = ev.uid "
            "GROUP BY o.uid, u.username, o.department "
            "HAVING eventCount >= %s "
            "ORDER BY eventCount DESC, o.uid ASC",
            (n,),
        )
        rows = cursor.fetchall()
        return rows
    except Exception:
        return []
    finally:
        cursor.close()


# ---------------------------------------------------------------------------
# Function 12: venueEvents
# ---------------------------------------------------------------------------

def venue_events(connection, vid):
    """List every event hosted at a given venue.

    Each row also shows whether the venue is the primary venue for that event.
    Sorted by event datetime ascending, then event id ascending.
    """
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT e.eid, e.title, e.`type`, e.`date`, h.is_primary "
            "FROM `Hosting` h "
            "JOIN `Event` e ON h.eid = e.eid "
            "WHERE h.vid = %s "
            "ORDER BY e.`date` ASC, e.eid ASC",
            (vid,),
        )
        rows = cursor.fetchall()
        return rows
    except Exception:
        return []
    finally:
        cursor.close()


# ---------------------------------------------------------------------------
# main: read the command line and call the matching function
# ---------------------------------------------------------------------------

def main():
    # sys.argv[0] is "project.py", sys.argv[1] is the function name, and the
    # rest are the parameters for that function.
    if len(sys.argv) < 2:
        return

    command = sys.argv[1]
    arguments = sys.argv[2:]

    connection = connect()
    try:
        if command == "import":
            folder_name = arguments[0]
            result = import_data(connection, folder_name)
            print("Success" if result else "Fail")

        elif command == "insertAdmin":
            uid = int(arguments[0])
            email = parse_argument(arguments[1])
            username = parse_argument(arguments[2])
            joined = parse_argument(arguments[3])
            firstname = parse_argument(arguments[4])
            lastname = parse_argument(arguments[5])
            result = insert_admin(
                connection, uid, email, username, joined, firstname, lastname
            )
            print("Success" if result else "Fail")

        elif command == "addVenue":
            eid = int(arguments[0])
            vid = int(arguments[1])
            is_primary = parse_boolean(arguments[2])
            result = add_venue(connection, eid, vid, is_primary)
            print("Success" if result else "Fail")

        elif command == "reserveSlot":
            eid = int(arguments[0])
            snum = int(arguments[1])
            uid = int(arguments[2])
            result = reserve_slot(connection, eid, snum, uid)
            print("Success" if result else "Fail")

        elif command == "cancelReservation":
            eid = int(arguments[0])
            snum = int(arguments[1])
            uid = int(arguments[2])
            result = cancel_reservation(connection, eid, snum, uid)
            print("Success" if result else "Fail")

        elif command == "updateEvent":
            eid = int(arguments[0])
            title = parse_argument(arguments[1])
            datetime_value = parse_argument(arguments[2])
            result = update_event(connection, eid, title, datetime_value)
            print("Success" if result else "Fail")

        elif command == "deleteOrganizer":
            uid = int(arguments[0])
            result = delete_organizer(connection, uid)
            print("Success" if result else "Fail")

        elif command == "availableEvents":
            date_value = parse_argument(arguments[0])
            rows = available_events(connection, date_value)
            print_table(rows)

        elif command == "popularEventTypes":
            n = int(arguments[0])
            rows = popular_event_types(connection, n)
            print_table(rows)

        elif command == "participantSchedule":
            uid = int(arguments[0])
            rows = participant_schedule(connection, uid)
            print_table(rows)

        elif command == "organizerStats":
            n = int(arguments[0])
            rows = organizer_stats(connection, n)
            print_table(rows)

        elif command == "venueEvents":
            vid = int(arguments[0])
            rows = venue_events(connection, vid)
            print_table(rows)

    finally:
        # Always close the connection, even if something above failed.
        connection.close()


# Only run main() when this file is executed directly. This guard lets the
# test file import the functions without running the whole program.
if __name__ == "__main__":
    main()
