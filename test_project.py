"""
Tests for the CS122A ZotEvent project (project.py).

There are two kinds of tests in this file:

1. LogicTests       - pure-logic tests for the small helper functions
                      (parse_argument, parse_boolean, format_value,
                      build_insert_statement). These do NOT need a database,
                      so they always run.

2. DatabaseTests    - integration tests that run real SQL against a MySQL
                      database. These are skipped automatically if no database
                      is reachable, so the logic tests can still run on their
                      own.

How to run:
    python3 -m unittest test_project.py        (or)
    python3 test_project.py

The database connection uses the same user/password/database as the autograder
by default, but you can override them with environment variables if your local
MySQL is set up differently:
    MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE, MYSQL_HOST, MYSQL_PORT

WARNING: the integration tests DROP and recreate all the tables in the target
database before every test, so point them at a throwaway test database.
"""

import os
import shutil
import tempfile
import datetime
import unittest

import mysql.connector

import project


# ---------------------------------------------------------------------------
# Database settings for the integration tests
# ---------------------------------------------------------------------------

DB_CONFIG = {
    "user": os.environ.get("MYSQL_USER", "test"),
    "password": os.environ.get("MYSQL_PASSWORD", "password"),
    "database": os.environ.get("MYSQL_DATABASE", "cs122a"),
    "host": os.environ.get("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.environ.get("MYSQL_PORT", "3306")),
}


def database_is_available():
    """Return True if we can actually connect to the database."""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        connection.close()
        return True
    except Exception:
        return False


# Checked once when the file is imported. Used to skip the integration tests
# if there is no database to talk to.
DB_AVAILABLE = database_is_available()


# ---------------------------------------------------------------------------
# Sample data (copied from the provided CSV files)
# ---------------------------------------------------------------------------

# The integration tests write these strings out to a temporary folder and then
# call project.import_data on that folder, so every test starts from exactly
# the sample dataset.
SAMPLE_FILES = {
    "User.csv": (
        "101,alice_sample@uci.edu,alice_sample,2024-01-05\n"
        "102,bob_sample@uci.edu,bob_sample,2023-09-10\n"
        "103,carol_sample@uci.edu,carol_sample,2023-10-12\n"
        "104,dave_sample@uci.edu,dave_sample,2024-02-20\n"
        "105,eve_sample@uci.edu,eve_sample,2024-02-25\n"
        "106,frank_sample@uci.edu,frank_sample,2024-03-01\n"
        "107,grace_sample@uci.edu,grace_sample,2022-08-15\n"
        "108,henry_sample@uci.edu,henry_sample,2022-11-30\n"
        "109,ivy_sample@uci.edu,ivy_sample,2024-03-15\n"
        "110,jack_sample@uci.edu,jack_sample,2024-04-02\n"
    ),
    "Organizer.csv": (
        "102,ICS,4\n"
        "103,Student Affairs,3\n"
        "108,Engineering,6\n"
    ),
    "Participant.csv": (
        "104,student\n"
        "105,staff\n"
        "106,alumni\n"
        "109,student\n"
        "110,student\n"
    ),
    "Administrator.csv": (
        "101,Alice,Sample\n"
        "107,Grace,Sample\n"
    ),
    "Venue.csv": (
        "301,123 Ring Mall,Irvine,CA,92697\n"
        "302,456 Student Center,Irvine,CA,92697\n"
        "303,789 Engineering Quad,Irvine,CA,92697\n"
        "304,15 Ocean Ave,Newport Beach,CA,92660\n"
        "305,44 Main Plaza,Santa Ana,CA,92701\n"
    ),
    "OnCampus.csv": (
        "301,RMH\n"
        "302,STC\n"
        "303,ENG\n"
    ),
    "OffCampus.csv": (
        "304,8\n"
        "305,11\n"
    ),
    "Event.csv": (
        "501,102,Cloud Systems Talk,academic,2026-06-10 13:00:00\n"
        "502,102,Data Engineering Meetup,technical,2026-06-12 16:00:00\n"
        "503,103,Campus Club Fair,social,2026-06-15 11:00:00\n"
        "504,108,Robotics Demo,technical,2026-07-01 15:30:00\n"
        "505,103,Volunteer Day,service,2026-05-18 09:00:00\n"
        "506,108,Spring Research Review,academic,2026-04-01 10:00:00\n"
    ),
    "Slot.csv": (
        "501,1,1,104\n"
        "501,2,0,NULL\n"
        "501,3,1,105\n"
        "501,4,0,NULL\n"
        "502,1,1,106\n"
        "502,2,0,NULL\n"
        "502,3,0,NULL\n"
        "503,1,1,104\n"
        "503,2,1,109\n"
        "503,3,0,NULL\n"
        "504,1,1,110\n"
        "504,2,1,105\n"
        "504,3,0,NULL\n"
        "504,4,0,NULL\n"
        "505,1,0,NULL\n"
        "505,2,0,NULL\n"
        "506,1,1,104\n"
        "506,2,1,106\n"
    ),
    "Hosting.csv": (
        "501,301,1\n"
        "501,302,0\n"
        "502,303,1\n"
        "503,302,1\n"
        "504,304,1\n"
        "505,305,1\n"
        "506,301,1\n"
    ),
    "Approval.csv": (
        "101,304,2026-01-01,2026-12-31\n"
        "101,305,2026-02-01,2026-08-31\n"
        "107,304,2025-09-01,2026-05-31\n"
    ),
}


def format_rows(rows):
    """Turn the rows returned by a project function into the printed strings.

    This reuses project.format_value so the test checks the exact text that
    would be printed (commas between columns, NULL for None, dates formatted,
    and so on). It makes the expected values much easier to read.
    """
    formatted = []
    for row in rows:
        formatted.append(",".join(project.format_value(cell) for cell in row))
    return formatted


# ---------------------------------------------------------------------------
# Part A: pure-logic tests (no database needed)
# ---------------------------------------------------------------------------

class LogicTests(unittest.TestCase):

    def test_parse_argument_null_becomes_none(self):
        # The literal string "NULL" must become Python None.
        self.assertIsNone(project.parse_argument("NULL"))

    def test_parse_argument_keeps_normal_string(self):
        self.assertEqual(project.parse_argument("alice"), "alice")

    def test_parse_argument_keeps_number_as_text(self):
        # parse_argument does not convert numbers; MySQL converts them later.
        self.assertEqual(project.parse_argument("101"), "101")

    def test_parse_argument_lowercase_null_is_not_none(self):
        # Only the exact text "NULL" counts, not "null".
        self.assertEqual(project.parse_argument("null"), "null")

    def test_parse_boolean_true_values(self):
        self.assertTrue(project.parse_boolean("true"))
        self.assertTrue(project.parse_boolean("True"))
        self.assertTrue(project.parse_boolean("TRUE"))
        self.assertTrue(project.parse_boolean("1"))

    def test_parse_boolean_false_values(self):
        self.assertFalse(project.parse_boolean("false"))
        self.assertFalse(project.parse_boolean("False"))
        self.assertFalse(project.parse_boolean("0"))
        self.assertFalse(project.parse_boolean("something_else"))

    def test_format_value_none(self):
        self.assertEqual(project.format_value(None), "NULL")

    def test_format_value_boolean(self):
        self.assertEqual(project.format_value(True), "1")
        self.assertEqual(project.format_value(False), "0")

    def test_format_value_datetime(self):
        value = datetime.datetime(2026, 6, 10, 13, 0, 0)
        self.assertEqual(project.format_value(value), "2026-06-10 13:00:00")

    def test_format_value_date(self):
        value = datetime.date(2024, 1, 5)
        self.assertEqual(project.format_value(value), "2024-01-05")

    def test_format_value_int_and_string(self):
        self.assertEqual(project.format_value(42), "42")
        self.assertEqual(project.format_value("hello"), "hello")

    def test_build_insert_statement_quotes_columns(self):
        # The reserved words `type` and `date` must be wrapped in backticks.
        statement = project.build_insert_statement(
            "Event", ["eid", "uid", "title", "type", "date"]
        )
        expected = (
            "INSERT INTO `Event` "
            "(`eid`, `uid`, `title`, `type`, `date`) "
            "VALUES (%s, %s, %s, %s, %s)"
        )
        self.assertEqual(statement, expected)


# ---------------------------------------------------------------------------
# Part B: integration tests (need a real database)
# ---------------------------------------------------------------------------

@unittest.skipUnless(
    DB_AVAILABLE, "No MySQL server reachable with the given settings"
)
class DatabaseTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Write the sample CSV files into a temporary folder one time.
        cls.data_dir = tempfile.mkdtemp(prefix="zotevent_test_")
        for file_name, content in SAMPLE_FILES.items():
            path = os.path.join(cls.data_dir, file_name)
            with open(path, "w", newline="") as csv_file:
                csv_file.write(content)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.data_dir, ignore_errors=True)

    def setUp(self):
        # Open a fresh connection and reload the sample data before EACH test,
        # so the tests do not interfere with one another.
        self.connection = mysql.connector.connect(**DB_CONFIG)
        self.connection.autocommit = False
        imported = project.import_data(self.connection, self.data_dir)
        self.assertTrue(imported, "import_data should succeed during setUp")

    def tearDown(self):
        self.connection.close()

    # -- small helpers ------------------------------------------------------

    def query(self, sql, params=None):
        """Run a SELECT on a brand new connection and return all rows.

        I use a separate connection for checking results so that I always see
        the latest committed data instead of a stale snapshot from this test's
        own transaction.
        """
        connection = mysql.connector.connect(**DB_CONFIG)
        try:
            cursor = connection.cursor()
            cursor.execute(sql, params or ())
            rows = cursor.fetchall()
            cursor.close()
            return rows
        finally:
            connection.close()

    def execute_and_commit(self, sql, params=None):
        """Run and commit a statement on this test's main connection.

        Used to set up a specific situation before calling a project function.
        """
        cursor = self.connection.cursor()
        cursor.execute(sql, params or ())
        self.connection.commit()
        cursor.close()

    # -- Function 1: import -------------------------------------------------

    def test_import_loads_correct_row_counts(self):
        # setUp already imported, so just check a few row counts.
        self.assertEqual(self.query("SELECT COUNT(*) FROM `User`")[0][0], 10)
        self.assertEqual(self.query("SELECT COUNT(*) FROM `Event`")[0][0], 6)
        self.assertEqual(self.query("SELECT COUNT(*) FROM `Slot`")[0][0], 18)
        self.assertEqual(self.query("SELECT COUNT(*) FROM `Hosting`")[0][0], 7)

    def test_import_is_repeatable(self):
        # Importing again on top of existing tables should still work.
        self.assertTrue(project.import_data(self.connection, self.data_dir))

    # -- Function 2: insertAdmin --------------------------------------------

    def test_insert_admin_new_user(self):
        result = project.insert_admin(
            self.connection, 200, "admin200@uci.edu", "adminuser",
            "2024-04-19", "Alice", "Wong",
        )
        self.assertTrue(result)
        user_rows = self.query(
            "SELECT username FROM `User` WHERE uid = 200"
        )
        admin_rows = self.query(
            "SELECT firstname, lastname FROM `Administrator` WHERE uid = 200"
        )
        self.assertEqual(user_rows, [("adminuser",)])
        self.assertEqual(admin_rows, [("Alice", "Wong")])

    def test_insert_admin_duplicate_uid_fails(self):
        # uid 101 already exists, so this must fail and change nothing.
        result = project.insert_admin(
            self.connection, 101, "dup@uci.edu", "dup",
            "2024-01-01", "Dup", "Licate",
        )
        self.assertFalse(result)
        # The original administrator 101 should be untouched.
        admin_rows = self.query(
            "SELECT firstname, lastname FROM `Administrator` WHERE uid = 101"
        )
        self.assertEqual(admin_rows, [("Alice", "Sample")])
        # No partial user should have been left behind (still 10 users).
        self.assertEqual(self.query("SELECT COUNT(*) FROM `User`")[0][0], 10)

    # -- Function 3: addVenue -----------------------------------------------

    def test_add_venue_primary_conflict_fails(self):
        # Event 501 already has primary venue 301, so adding another primary
        # must fail.
        result = project.add_venue(self.connection, 501, 303, True)
        self.assertFalse(result)
        # Nothing new should have been inserted.
        rows = self.query(
            "SELECT COUNT(*) FROM `Hosting` WHERE eid = 501 AND vid = 303"
        )
        self.assertEqual(rows[0][0], 0)

    def test_add_venue_new_non_primary_succeeds(self):
        result = project.add_venue(self.connection, 501, 304, False)
        self.assertTrue(result)
        rows = self.query(
            "SELECT is_primary FROM `Hosting` WHERE eid = 501 AND vid = 304"
        )
        self.assertEqual(rows, [(0,)])

    def test_add_venue_duplicate_pair_fails(self):
        # (501, 301) already exists, so inserting it again must fail.
        result = project.add_venue(self.connection, 501, 301, False)
        self.assertFalse(result)
        # The existing row must keep its original is_primary value (1).
        rows = self.query(
            "SELECT is_primary FROM `Hosting` WHERE eid = 501 AND vid = 301"
        )
        self.assertEqual(rows, [(1,)])

    def test_add_venue_primary_succeeds_after_removing_old_primary(self):
        # If we first remove the existing primary, adding a new primary works.
        self.execute_and_commit(
            "DELETE FROM `Hosting` WHERE eid = 501 AND is_primary = 1"
        )
        result = project.add_venue(self.connection, 501, 304, True)
        self.assertTrue(result)
        rows = self.query(
            "SELECT is_primary FROM `Hosting` WHERE eid = 501 AND vid = 304"
        )
        self.assertEqual(rows, [(1,)])

    # -- Function 4: reserveSlot --------------------------------------------

    def test_reserve_slot_success(self):
        # Slot (501, 2) starts unreserved.
        result = project.reserve_slot(self.connection, 501, 2, 104)
        self.assertTrue(result)
        rows = self.query(
            "SELECT is_reserved, uid FROM `Slot` WHERE eid = 501 AND snum = 2"
        )
        self.assertEqual(rows, [(1, 104)])

    def test_reserve_slot_already_reserved_fails(self):
        # Slot (501, 1) is already reserved by 104, so 109 cannot take it.
        result = project.reserve_slot(self.connection, 501, 1, 109)
        self.assertFalse(result)
        rows = self.query(
            "SELECT is_reserved, uid FROM `Slot` WHERE eid = 501 AND snum = 1"
        )
        self.assertEqual(rows, [(1, 104)])

    def test_reserve_slot_twice_second_time_fails(self):
        first = project.reserve_slot(self.connection, 501, 2, 104)
        second = project.reserve_slot(self.connection, 501, 2, 104)
        self.assertTrue(first)
        self.assertFalse(second)

    # -- Function 5: cancelReservation --------------------------------------

    def test_cancel_reservation_success(self):
        # Slot (501, 1) is reserved by 104.
        result = project.cancel_reservation(self.connection, 501, 1, 104)
        self.assertTrue(result)
        rows = self.query(
            "SELECT is_reserved, uid FROM `Slot` WHERE eid = 501 AND snum = 1"
        )
        self.assertEqual(rows, [(0, None)])

    def test_cancel_reservation_wrong_participant_fails(self):
        # Slot (501, 3) is reserved by 105, so 104 cannot cancel it.
        result = project.cancel_reservation(self.connection, 501, 3, 104)
        self.assertFalse(result)
        rows = self.query(
            "SELECT is_reserved, uid FROM `Slot` WHERE eid = 501 AND snum = 3"
        )
        self.assertEqual(rows, [(1, 105)])

    def test_cancel_reservation_twice_second_time_fails(self):
        first = project.cancel_reservation(self.connection, 501, 1, 104)
        second = project.cancel_reservation(self.connection, 501, 1, 104)
        self.assertTrue(first)
        self.assertFalse(second)

    # -- Function 6: updateEvent --------------------------------------------

    def test_update_event_success(self):
        result = project.update_event(
            self.connection, 501, "New Title", "2027-01-01 10:00:00"
        )
        self.assertTrue(result)
        rows = self.query(
            "SELECT title, `date` FROM `Event` WHERE eid = 501"
        )
        self.assertEqual(
            rows,
            [("New Title", datetime.datetime(2027, 1, 1, 10, 0, 0))],
        )

    def test_update_event_missing_fails(self):
        result = project.update_event(
            self.connection, 9999, "Nope", "2027-01-01 10:00:00"
        )
        self.assertFalse(result)

    def test_update_event_with_same_values_still_succeeds(self):
        # Even when the new values match the current ones (so no row really
        # changes), the event exists, so the result should still be True.
        result = project.update_event(
            self.connection, 501, "Cloud Systems Talk", "2026-06-10 13:00:00"
        )
        self.assertTrue(result)

    # -- Function 7: deleteOrganizer ----------------------------------------

    def test_delete_organizer_cascades(self):
        # Organizer 102 owns events 501 and 502.
        result = project.delete_organizer(self.connection, 102)
        self.assertTrue(result)
        # Organizer is gone.
        self.assertEqual(
            self.query("SELECT COUNT(*) FROM `Organizer` WHERE uid = 102")[0][0],
            0,
        )
        # Their events are gone.
        self.assertEqual(
            self.query(
                "SELECT COUNT(*) FROM `Event` WHERE eid IN (501, 502)"
            )[0][0],
            0,
        )
        # The slots of those events are gone.
        self.assertEqual(
            self.query(
                "SELECT COUNT(*) FROM `Slot` WHERE eid IN (501, 502)"
            )[0][0],
            0,
        )
        # The hosting rows of those events are gone.
        self.assertEqual(
            self.query(
                "SELECT COUNT(*) FROM `Hosting` WHERE eid IN (501, 502)"
            )[0][0],
            0,
        )
        # The underlying User 102 should still exist (only the organizer role
        # was deleted).
        self.assertEqual(
            self.query("SELECT COUNT(*) FROM `User` WHERE uid = 102")[0][0],
            1,
        )
        # Other organizers' events must be untouched.
        self.assertEqual(
            self.query(
                "SELECT COUNT(*) FROM `Event` WHERE eid IN (503, 504, 505, 506)"
            )[0][0],
            4,
        )

    def test_delete_organizer_missing_fails(self):
        result = project.delete_organizer(self.connection, 9999)
        self.assertFalse(result)

    # -- Function 8: availableEvents ----------------------------------------

    def test_available_events(self):
        rows = project.available_events(self.connection, "2026-05-01")
        expected = [
            "505,Volunteer Day,service,2026-05-18 09:00:00,2",
            "501,Cloud Systems Talk,academic,2026-06-10 13:00:00,2",
            "502,Data Engineering Meetup,technical,2026-06-12 16:00:00,2",
            "503,Campus Club Fair,social,2026-06-15 11:00:00,1",
            "504,Robotics Demo,technical,2026-07-01 15:30:00,2",
        ]
        self.assertEqual(format_rows(rows), expected)

    def test_available_events_far_future_is_empty(self):
        rows = project.available_events(self.connection, "2026-12-31")
        self.assertEqual(format_rows(rows), [])

    # -- Function 9: popularEventTypes --------------------------------------

    def test_popular_event_types_threshold_two(self):
        rows = project.popular_event_types(self.connection, 2)
        expected = [
            "academic,4",
            "technical,3",
            "social,2",
        ]
        self.assertEqual(format_rows(rows), expected)

    def test_popular_event_types_high_threshold_is_empty(self):
        rows = project.popular_event_types(self.connection, 5)
        self.assertEqual(format_rows(rows), [])

    def test_popular_event_types_threshold_zero_includes_service(self):
        # With N = 0 even the "service" type (0 reserved slots) shows up.
        rows = project.popular_event_types(self.connection, 0)
        expected = [
            "academic,4",
            "technical,3",
            "social,2",
            "service,0",
        ]
        self.assertEqual(format_rows(rows), expected)

    # -- Function 10: participantSchedule -----------------------------------

    def test_participant_schedule(self):
        rows = project.participant_schedule(self.connection, 104)
        expected = [
            "506,Spring Research Review,academic,2026-04-01 10:00:00,1,"
            "301,123 Ring Mall,Irvine,CA,92697",
            "501,Cloud Systems Talk,academic,2026-06-10 13:00:00,1,"
            "301,123 Ring Mall,Irvine,CA,92697",
            "503,Campus Club Fair,social,2026-06-15 11:00:00,1,"
            "302,456 Student Center,Irvine,CA,92697",
        ]
        self.assertEqual(format_rows(rows), expected)

    def test_participant_schedule_shows_null_when_no_primary_venue(self):
        # If event 503 has no primary venue, the venue columns become NULL.
        self.execute_and_commit(
            "UPDATE `Hosting` SET is_primary = 0 WHERE eid = 503"
        )
        rows = project.participant_schedule(self.connection, 104)
        expected = [
            "506,Spring Research Review,academic,2026-04-01 10:00:00,1,"
            "301,123 Ring Mall,Irvine,CA,92697",
            "501,Cloud Systems Talk,academic,2026-06-10 13:00:00,1,"
            "301,123 Ring Mall,Irvine,CA,92697",
            "503,Campus Club Fair,social,2026-06-15 11:00:00,1,"
            "NULL,NULL,NULL,NULL,NULL",
        ]
        self.assertEqual(format_rows(rows), expected)

    def test_participant_schedule_unknown_participant_is_empty(self):
        rows = project.participant_schedule(self.connection, 999)
        self.assertEqual(format_rows(rows), [])

    # -- Function 11: organizerStats ----------------------------------------

    def test_organizer_stats_threshold_two(self):
        rows = project.organizer_stats(self.connection, 2)
        expected = [
            "102,bob_sample,ICS,2",
            "103,carol_sample,Student Affairs,2",
            "108,henry_sample,Engineering,2",
        ]
        self.assertEqual(format_rows(rows), expected)

    def test_organizer_stats_high_threshold_is_empty(self):
        rows = project.organizer_stats(self.connection, 3)
        self.assertEqual(format_rows(rows), [])

    # -- Function 12: venueEvents -------------------------------------------

    def test_venue_events_for_venue_301(self):
        rows = project.venue_events(self.connection, 301)
        expected = [
            "506,Spring Research Review,academic,2026-04-01 10:00:00,1",
            "501,Cloud Systems Talk,academic,2026-06-10 13:00:00,1",
        ]
        self.assertEqual(format_rows(rows), expected)

    def test_venue_events_for_venue_302_mixed_primary_flag(self):
        # Venue 302 is non-primary for event 501 but primary for event 503.
        rows = project.venue_events(self.connection, 302)
        expected = [
            "501,Cloud Systems Talk,academic,2026-06-10 13:00:00,0",
            "503,Campus Club Fair,social,2026-06-15 11:00:00,1",
        ]
        self.assertEqual(format_rows(rows), expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)