# Copyright (C) Collabora Limited 2017
# Author: Guillaume Tucker <guillaume.tucker@collabora.com>
#
# Copyright (C) Linaro Limited 2015,2016
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

"""All delta/compare related celery tasks."""

import taskqueue.celery as taskc
import utils.build
import utils.compare.boot
import utils.compare.build
import utils.compare.job


@taskc.app.task(name="job-delta", ignore_result=False)
def calculate_job_delta(json_obj, db_options=None):
    """Perform the job delta calculations.

    Wrapper around the real function to provide a task-based access.

    :param json_obj: The JSON data with the values.
    :type json_obj: dict
    :param db_options: The database connection parameters.
    :type db_options: dict
    :return a 4-tuple: status code, result, doc_id, errors.
    """
    return utils.compare.job.execute_job_delta(json_obj, db_options)


@taskc.app.task(name="build-delta", ignore_result=False)
def calculate_build_delta(json_obj, db_options=None):
    """Perform the build delta calculations.

    Wrapper around the real function to provide a task-based access.

    :param json_obj: The JSON data with the values.
    :type json_obj: dict
    :param db_options: The database connection parameters.
    :type db_options: dict
    :return A 4-tuple: status code, result, doc_id and errors.
    :rtype tuple
    """
    return utils.compare.build.execute_delta(json_obj, db_options)


@taskc.app.task(name="boot-delta", ignore_result=False)
def calculate_boot_delta(json_obj, db_options=None):
    """Perform the boot delta calculations.

    Wrapper around the real function to provide a task-based access.

    :param json_obj: The JSON data with the values.
    :type json_obj: dict
    :param db_options: The database connection parameters.
    :type db_options: dict
    :return A 4-tuple: status code, result, doc_id and errors.
    :rtype tuple
    """
    return utils.compare.boot.execute_delta(json_obj, db_options)
