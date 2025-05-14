"""Unit tests for send_email.py."""

import logging
import unittest

from parameterized import parameterized

from self_debug.common import send_email, utils


class TestUtils(unittest.TestCase):
    """Unit tests for send_email.py."""

    @parameterized.expand(
        (
            # Dry run: Based on `user`
            (
                "<msg>",
                "<subject>",
                None,  # user
                None,  # region
                False,  # dry_run
                # Output
                (
                    send_email.SENDER,
                    (),  # Nobody
                    "us-east-1",
                    False,  # Dry run: No emails sent.
                ),
                "\n        <p><msg></p>\n",
                "[us-east-1] BOT Email: <subject>",
            ),
            (
                "<msg>",
                "<subject>",
                "  ",  # user
                None,  # region
                False,  # dry_run
                # Output
                (
                    send_email.SENDER,
                    (),  # Nobody
                    "us-east-1",
                    False,  # Dry run: No emails sent.
                ),
                "\n        <p><msg></p>\n",
                "[us-east-1] BOT Email: <subject>",
            ),
            # Dry run: Other cases.
            (
                "<msg>",
                "<subject>",
                "ldap",
                None,  # region
                True,  # dry_run
                # Output
                (
                    send_email.SENDER,
                    ("ldap@amazon.com",),
                    "us-east-1",
                    False,  # Dry run: No emails sent.
                ),
                "\n        <p><msg></p>\n",
                "[us-east-1] BOT Email: <subject>",
            ),
            (
                "<msg again>",
                "<subject again>",
                "  ldap1, ldap2@com.com ,, ,ldap ",
                "us-west-2",
                True,  # dry_run
                # Output
                (
                    send_email.SENDER,
                    (
                        "ldap1@amazon.com",
                        "ldap2@com.com",
                        "ldap@amazon.com",
                    ),
                    "us-west-2",
                    False,  # Dry run: No emails sent.
                ),
                "\n        <p><msg again></p>\n",
                "[us-west-2] BOT Email: <subject again>",
            ),
        )
    )
    def test_email(
        self,
        msg,
        subject,
        user,
        region,
        dry_run,
        expected_result,
        expected_message,
        expected_subject,
    ):
        """Unit tests for `email`."""
        result = send_email.email(msg, user, subject, region, dry_run=dry_run)

        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 5)

        result = list(result)
        info = result.pop(2)
        self.assertEqual(tuple(result), expected_result)

        self.assertIsInstance(info, dict)
        body, subject = "Body", "Subject"
        self.assertEqual(sorted(list(info.keys())), [body, subject])
        self.assertIn(expected_message, info[body]["Html"]["Data"])
        self.assertEqual(info[subject]["Data"], expected_subject)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)

    unittest.main()
