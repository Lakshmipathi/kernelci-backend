# Copyright (C) Collabora Limited 2019
# Author: Guillaume Tucker <guillaume.tucker@collabora.com>
#
# Copyright (C) Linaro Limited 2016
# Author: Milo Casagrande <milo.casagrande@linaro.org>
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this library; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import logging
import mock
import mongomock
import random
import string
import unittest

import utils.boot.regressions as boot_regressions


class TestBootRegressions(unittest.TestCase):

    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.db = mongomock.Database(mongomock.MongoClient(),
                                     "kernel-ci", None)

        self.boot_id = "".join(
            [random.choice(string.digits) for x in xrange(24)])

        self.pass_boot = {
            "status": "PASS",
            "job": "job",
            "kernel": "kernel",
            "arch": "arm",
            "defconfig_full": "defconfig-full",
            "defconfig": "defconfig",
            "build_environment": "gcc",
            "compiler": "gcc",
            "compiler_version": "5.1.1",
            "lab_name": "boot-lab",
            "board": "arm-board",
            "created_on": "2016-06-29"
        }

        self.fail_boot = {
            "status": "FAIL",
            "job": "job",
            "kernel": "kernel1",
            "arch": "arm",
            "defconfig_full": "defconfig-full",
            "defconfig": "defconfig",
            "build_environment": "gcc",
            "compiler": "gcc",
            "compiler_version": "5.1.1",
            "lab_name": "boot-lab",
            "board": "arm-board",
            "created_on": "2016-06-28"
        }

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_get_regressions_by_key_wrong_index(self):
        key = "a.b.c.d"
        regressions = {
            "a": {
                "b": {
                    "c": {
                        "d": {
                            "e": {
                                "f": ["foo"]
                            }
                        }
                    }
                }
            }
        }

        regr = boot_regressions.get_regressions_by_key(key, regressions)
        self.assertListEqual([], regr)

    def test_get_regressions_by_key_wrong_key(self):
        key = "a.b.c.e.h.j"
        regressions = {
            "a": {
                "b": {
                    "c": {
                        "d": {
                            "e": {
                                "f": ["foo"]
                            }
                        }
                    }
                }
            }
        }

        regr = boot_regressions.get_regressions_by_key(key, regressions)
        self.assertListEqual([], regr)

    def test_get_regressions_by_key(self):
        key = "a.b.c.d.e.f.g"
        regressions = {
            "a": {
                "b": {
                    "c": {
                        "d": {
                            "e": {
                                "f": {
                                    "g": ["foo"]
                                }
                            }
                        }
                    }
                }
            }
        }

        regr = boot_regressions.get_regressions_by_key(key, regressions)
        self.assertListEqual(["foo"], regr)

    def test_generate_regression_keys(self):
        regressions = {
            "lab": {
                "arch": {
                    "board": {
                        "board_instance": {
                            "defconfig": {
                                "build_env": {
                                    "compiler": ["regression"]
                                }
                            }
                        }
                    }
                }
            }
        }
        expected = "lab.arch.board.board_instance.defconfig.build_env.compiler"

        for k in boot_regressions.gen_regression_keys(regressions):
            self.assertEqual(expected, k)

    def test_sanitize_key(self):
        self.assertIsNone(None, boot_regressions.sanitize_key(None))
        self.assertEqual("", boot_regressions.sanitize_key(" "))

        key = "foo"
        self.assertEqual("foo", boot_regressions.sanitize_key(key))

        key = "foo bar"
        self.assertEqual("foobar", boot_regressions.sanitize_key(key))

        key = "foo.bar"
        self.assertEqual("foo:bar", boot_regressions.sanitize_key(key))

        key = "foo bar.baz+foo"
        self.assertEqual("foobar:baz+foo", boot_regressions.sanitize_key(key))

    @mock.patch("utils.db.get_db_connection")
    def test_find_wrong_id(self, mock_db):
        results = boot_regressions.find("foo", {})
        self.assertTupleEqual((None, None), results)

    @mock.patch("utils.db.find_one3")
    @mock.patch("utils.db.get_db_connection2")
    def test_find_not_fail(self, mock_db, mock_find):
        mock_find.return_value = {"status": "PASS"}

        results = boot_regressions.find(self.boot_id, {})
        self.assertTupleEqual((None, None), results)

    @mock.patch("utils.db.find_one3")
    @mock.patch("utils.db.get_db_connection2")
    def test_find_no_old_doc(self, mock_db, mock_find):
        mock_find.side_effects = [self.fail_boot, None]

        results = boot_regressions.find(self.boot_id, {})
        self.assertTupleEqual((None, None), results)

    def test_create_regressions_key(self):
        expected = "boot-lab.arm.arm-board.none.defconfig-full.gcc.gcc-5:1:1"
        self.assertEqual(
            expected, boot_regressions.create_regressions_key(self.pass_boot))
