# Copyright (C) Linaro Limited 2014,2015
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

"""Test module for the BisectHandler handler."""

import mock
import tornado

import urls

from handlers.tests.test_handler_base import TestHandlerBase


class TestBisectHandler(TestHandlerBase):

    def setUp(self):
        super(TestBisectHandler, self).setUp()

        self.task_return_value = mock.MagicMock()
        self.task_ready = mock.MagicMock()
        self.task_ready.return_value = True
        self.task_return_value.ready = self.task_ready
        self.task_return_value.get = mock.MagicMock()
        self.task_return_value.get.return_value = 200, []

        patched_boot_bisect_func = mock.patch(
            "taskqueue.tasks.bisect.boot_bisect")
        self.boot_bisect = patched_boot_bisect_func.start()
        self.boot_bisect.apply_async = mock.MagicMock()
        self.boot_bisect.apply_async.return_value = self.task_return_value

        self.addCleanup(patched_boot_bisect_func.stop)

    def get_app(self):
        return tornado.web.Application([urls._BISECT_URL], **self.settings)

    def test_bisect_wrong_collection(self):
        headers = {"Authorization": "foo"}

        response = self.fetch("/bisect/bisect_id", headers=headers)
        self.assertEqual(response.code, 400)

    def test_boot_bisect_no_token(self):
        self.find_token.return_value = None

        response = self.fetch("/bisect/bisect_id")
        self.assertEqual(response.code, 403)

    def test_boot_bisect_wrong_url(self):
        headers = {"Authorization": "foo"}

        response = self.fetch("/bisect/boot/", headers=headers)
        self.assertEqual(response.code, 400)

    @mock.patch("bson.objectid.ObjectId")
    def test_boot_bisect_no_id(self, mock_id):
        mock_id.return_value = "foo"
        headers = {"Authorization": "foo"}

        self.task_return_value.get.return_value = 404, []

        response = self.fetch("/bisect/foo", headers=headers)
        self.assertEqual(response.code, 404)

    def test_boot_bisect_no_failed(self):
        headers = {"Authorization": "foo"}

        self.task_return_value.get.return_value = 400, None

        response = self.fetch("/bisect/foo", headers=headers)
        self.assertEqual(response.code, 400)

    @mock.patch("bson.objectid.ObjectId")
    @mock.patch("utils.db.find_one2")
    def test_boot_bisect_with_result(self, mocked_find, mock_id):
        mock_id.return_value = "foo"
        headers = {"Authorization": "foo"}

        mocked_find.return_value = [{"foo": "bar"}]

        response = self.fetch("/bisect/foo", headers=headers)
        self.assertEqual(response.code, 200)
